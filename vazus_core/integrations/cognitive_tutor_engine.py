"""
vazus_core/cognitive_tutor_engine.py
Active Learning SM-2 Spaced Repetition Engine & Socratic Tutor for vazus SuperGraph OS.

Milestone 4 (R4) Implementation.
Provides:
1. SuperMemo SM-2 algorithm calculation with EF lower bound (1.3) and milestone intervals (1, 3, 7, 21 days).
2. Socratic active recall question generator for ThesisNode, ProtocolNode, and Zettelkasten Markdown notes.
3. Hybrid 768D embedding response evaluator (cosine similarity + key term recall + sequence matching).
4. SQLite persistence for tutor_cards and tutor_reviews tables in vazus.db (with kg_flashcards / kg_review_logs aliases).
"""

import sys
import re
import uuid
import sqlite3
import datetime
import difflib
from contextlib import contextmanager
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union

# Attempt import of UnifiedEmbeddingManager from vazus_core.memory.embeddings
try:
    from vazus_core.memory.embeddings import UnifiedEmbeddingManager
except ImportError:
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from vazus_core.memory.embeddings import UnifiedEmbeddingManager
    except ImportError:
        UnifiedEmbeddingManager = None


DEFAULT_DB_PATH = r"C:\vazus\services\memory\vazus.db"
DEFAULT_WIKI_DIR = r"C:\vazus\services\memory\semantic\wiki"


def map_score_to_q(score_percent: float) -> int:
    """
    Maps continuous accuracy score S in [0, 100]% to SM-2 Quality rating Q in [0..5].
    Q=5: S >= 90%
    Q=4: 80% <= S < 90%
    Q=3: 65% <= S < 80%
    Q=2: 50% <= S < 65%
    Q=1: 30% <= S < 50%
    Q=0: S < 30%
    """
    s = float(score_percent)
    if s >= 90.0:
        return 5
    elif s >= 80.0:
        return 4
    elif s >= 65.0:
        return 3
    elif s >= 50.0:
        return 2
    elif s >= 30.0:
        return 1
    else:
        return 0


def calculate_sm2_update(
    repetitions: int,
    ease_factor: float,
    interval_days: float,
    quality_rating: int
) -> Tuple[int, float, float]:
    """
    Computes updated SuperMemo SM-2 state (n', EF', I').
    
    Formula:
    EF' = max(1.3, EF + (0.1 - (5 - Q) * (0.08 + (5 - Q) * 0.02)))
    
    Interval I(n'):
    - Q >= 3 (Successful Review / Pass):
        n' = repetitions + 1
        I(1) = 1.0 day
        I(2) = 3.0 days
        I(3) = 7.0 days
        I(4) = 21.0 days
        I(n' > 4) = round(I(n'-1) * EF')
    - Q < 3 (Failed Review / Lapse):
        n' = 0
        I' = 1.0 day
    
    Returns:
        Tuple[int, float, float]: (new_repetitions, new_ease_factor, new_interval_days)
    """
    q = max(0, min(5, int(quality_rating)))
    ef = max(1.3, float(ease_factor))
    n = max(0, int(repetitions))
    cur_i = max(0.0, float(interval_days))

    # Calculate Ease Factor update
    delta_ef = 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)
    new_ef = max(1.3, round(ef + delta_ef, 4))

    if q >= 3:
        new_n = n + 1
        if new_n == 1:
            new_interval = 1.0
        elif new_n == 2:
            new_interval = 3.0
        elif new_n == 3:
            new_interval = 7.0
        elif new_n == 4:
            new_interval = 21.0
        else:
            new_interval = float(round(cur_i * new_ef))
    else:
        new_n = 0
        new_interval = 1.0

    return new_n, new_ef, float(new_interval)


def extract_keywords(text: str) -> List[str]:
    """Extracts normalized key terms (>= 4 chars, excluding common stopwords)."""
    if not text:
        return []
    words = re.findall(r'\b[a-zA-Zа-яА-Я0-9_-]{4,}\b', text.lower())
    stopwords = {
        "with", "that", "this", "from", "have", "been", "were", "what", "when",
        "where", "which", "about", "could", "would", "should", "there", "their",
        "into", "than", "then", "them", "these", "those", "also", "your", "does",
        "какой", "такой", "который", "быть", "если", "когда", "чтобы", "этого"
    }
    return sorted(list(set(w for w in words if w not in stopwords)))


def generate_active_recall_question(entity_dict: Union[Dict[str, Any], Any]) -> Dict[str, Any]:
    """
    Generates a Socratic active recall question dictionary from a ThesisNode,
    ProtocolNode, or Zettelkasten Markdown note representation.
    """
    # Normalize object to dict if needed
    if not isinstance(entity_dict, dict):
        if hasattr(entity_dict, "to_dict"):
            entity_dict = entity_dict.to_dict()
        elif hasattr(entity_dict, "__dict__"):
            entity_dict = vars(entity_dict)
        else:
            entity_dict = {"statement": str(entity_dict)}

    node_type = str(entity_dict.get("node_type") or entity_dict.get("type") or "ThesisNode")
    ent_id = str(entity_dict.get("id") or entity_dict.get("node_id") or entity_dict.get("zettel_id") or f"entity_{uuid.uuid4().hex[:8]}")

    # Determine archetype and generate question
    question_type = "CONCEPT_EXPLANATION"
    question_text = ""
    target_answer = ""

    # Protocol Node
    if node_type in ("ProtocolNode", "protocol") or "steps" in entity_dict or "prerequisites" in entity_dict:
        name = entity_dict.get("name") or entity_dict.get("title") or "Protocol Directive"
        steps = entity_dict.get("steps") or []
        prereqs = entity_dict.get("prerequisites") or []
        warnings = entity_dict.get("safety_warnings") or entity_dict.get("warnings") or []

        if isinstance(steps, str):
            steps = [s.strip() for s in steps.split(";") if s.strip()]
        if isinstance(prereqs, str):
            prereqs = [p.strip() for p in prereqs.split(",") if p.strip()]
        if isinstance(warnings, str):
            warnings = [w.strip() for w in warnings.split(",") if w.strip()]

        if prereqs:
            question_type = "PREREQUISITE_CHECK"
            question_text = f"Before executing protocol '{name}', what operational prerequisites and co-factors must be verified?"
            target_answer = ", ".join(prereqs)
        elif len(steps) >= 2:
            question_type = "SEQUENCE_ORDERING"
            question_text = f"Arrange the following required steps for protocol '{name}' in correct sequential order."
            target_answer = " -> ".join(steps)
        elif warnings:
            question_type = "SAFETY_WARNING"
            question_text = f"What critical safety and risk warnings apply when running protocol '{name}'?"
            target_answer = ", ".join(warnings)
        else:
            question_type = "CONCEPT_EXPLANATION"
            stmt = entity_dict.get("statement") or entity_dict.get("description") or name
            question_text = f"Describe the operational objective and steps for protocol '{name}': {stmt}"
            target_answer = str(stmt)

    # Zettel Note
    elif node_type in ("ZettelNote", "zettel") or "wikilinks" in entity_dict:
        title = entity_dict.get("title") or entity_dict.get("name") or "Zettel Note"
        wikilinks = entity_dict.get("wikilinks") or []
        content = entity_dict.get("core_claim") or entity_dict.get("content") or entity_dict.get("statement") or title

        if wikilinks and isinstance(wikilinks, list) and len(wikilinks) > 0:
            target_link = wikilinks[0]
            question_type = "WIKILINK_SYNTHESIS"
            question_text = f"How does Zettel note '{title}' relate to concept [[{target_link}]]? Describe the structural relationship."
            target_answer = f"Connects '{title}' to concept [[{target_link}]]: {content}"
        else:
            question_type = "CONCEPT_EXPLANATION"
            question_text = f"Summarize the core claim and analytical significance of Zettel note '{title}': {content}"
            target_answer = str(content)

    # Thesis Node (Default)
    else:
        name = entity_dict.get("name") or entity_dict.get("title") or "Thesis Assertion"
        stmt = entity_dict.get("statement") or entity_dict.get("core_claim") or entity_dict.get("text") or name
        stmt_str = str(stmt)

        # Decide between FILL_IN_BLANK and CONCEPT_EXPLANATION
        keywords = extract_keywords(stmt_str)
        if len(keywords) >= 3 and len(stmt_str.split()) >= 4:
            # Pick key target term
            target_term = max(keywords, key=len)
            # Create regex to replace target term safely
            pattern = re.compile(re.escape(target_term), re.IGNORECASE)
            cloze_stmt = pattern.sub("[______]", stmt_str, count=1)
            question_type = "FILL_IN_BLANK"
            question_text = f"Complete the thesis assertion: '{cloze_stmt}'"
            target_answer = target_term
        else:
            evidence = entity_dict.get("evidence_sources") or entity_dict.get("evidence") or []
            ev_str = f" (Evidence: {', '.join(evidence)})" if evidence else ""
            question_type = "CONCEPT_EXPLANATION"
            question_text = f"Explain the core claim and rationale for thesis '{name}': {stmt_str}"
            target_answer = f"{stmt_str}{ev_str}"

    card_id = f"card_{uuid.uuid4().hex[:12]}"
    return {
        "id": card_id,
        "card_id": card_id,
        "entity_id": ent_id,
        "entity_type": node_type,
        "question_type": question_type,
        "question_text": question_text,
        "target_answer": target_answer,
        "repetition_n": 0,
        "ease_factor": 2.5,
        "interval_days": 0.0,
        "lapses": 0
    }


def generate_all_questions_for_entity(entity_dict: Union[Dict[str, Any], Any]) -> List[Dict[str, Any]]:
    """Generates all applicable Socratic active recall questions for an entity."""
    if not isinstance(entity_dict, dict):
        if hasattr(entity_dict, "to_dict"):
            entity_dict = entity_dict.to_dict()
        elif hasattr(entity_dict, "__dict__"):
            entity_dict = vars(entity_dict)
        else:
            entity_dict = {"statement": str(entity_dict)}

    node_type = str(entity_dict.get("node_type") or entity_dict.get("type") or "ThesisNode")
    ent_id = str(entity_dict.get("id") or entity_dict.get("node_id") or f"entity_{uuid.uuid4().hex[:8]}")
    results = []

    if node_type in ("ProtocolNode", "protocol") or "steps" in entity_dict:
        name = entity_dict.get("name") or "Protocol Directive"
        steps = entity_dict.get("steps") or []
        prereqs = entity_dict.get("prerequisites") or []
        warnings = entity_dict.get("safety_warnings") or []

        if prereqs:
            results.append({
                "id": f"card_{uuid.uuid4().hex[:12]}",
                "entity_id": ent_id,
                "entity_type": node_type,
                "question_type": "PREREQUISITE_CHECK",
                "question_text": f"What prerequisites must be satisfied before executing protocol '{name}'?",
                "target_answer": ", ".join(prereqs) if isinstance(prereqs, list) else str(prereqs),
                "repetition_n": 0, "ease_factor": 2.5, "interval_days": 0.0, "lapses": 0
            })
        if len(steps) >= 2:
            results.append({
                "id": f"card_{uuid.uuid4().hex[:12]}",
                "entity_id": ent_id,
                "entity_type": node_type,
                "question_type": "SEQUENCE_ORDERING",
                "question_text": f"Arrange the steps for protocol '{name}' in correct sequential order.",
                "target_answer": " -> ".join(steps) if isinstance(steps, list) else str(steps),
                "repetition_n": 0, "ease_factor": 2.5, "interval_days": 0.0, "lapses": 0
            })
        if warnings:
            results.append({
                "id": f"card_{uuid.uuid4().hex[:12]}",
                "entity_id": ent_id,
                "entity_type": node_type,
                "question_type": "SAFETY_WARNING",
                "question_text": f"What critical safety warnings apply when running protocol '{name}'?",
                "target_answer": ", ".join(warnings) if isinstance(warnings, list) else str(warnings),
                "repetition_n": 0, "ease_factor": 2.5, "interval_days": 0.0, "lapses": 0
            })
    else:
        results.append(generate_active_recall_question(entity_dict))

    if not results:
        results.append(generate_active_recall_question(entity_dict))

    return results


class ResponseEvaluator:
    """Hybrid evaluator for active recall answers combining 768D embeddings, keywords, and sequence matching."""

    def __init__(self, embedder: Optional[Any] = None):
        if embedder is not None:
            self.embedder = embedder
        elif UnifiedEmbeddingManager is not None:
            try:
                self.embedder = UnifiedEmbeddingManager(dimension=768)
            except Exception:
                self.embedder = None
        else:
            self.embedder = None

    def evaluate_response(self, user_response: str, target_answer: str) -> Dict[str, Any]:
        u_clean = (user_response or "").strip()
        t_clean = (target_answer or "").strip()

        if not u_clean:
            target_kw = extract_keywords(t_clean)
            return {
                "score_percent": 0.0,
                "q_rating": 0,
                "feedback_rationale": "No answer provided. Zero accuracy.",
                "feedback": "No answer provided. Zero accuracy.",
                "matched_concepts": [],
                "missing_concepts": target_kw,
                "metrics": {"semantic_similarity": 0.0, "keyword_recall": 0.0, "sequence_match": 0.0}
            }

        # 1. Semantic Cosine Similarity (Weight 0.50)
        sem_sim = 0.0
        is_fallback_embedding = False
        if self.embedder is not None:
            try:
                v_user = self.embedder.get_embedding(u_clean)
                v_target = self.embedder.get_embedding(t_clean)
                sem_sim = max(0.0, float(self.embedder.compute_similarity(v_user, v_target)))
                if (
                    getattr(self.embedder, "fallback_mode", False) or
                    getattr(self.embedder, "use_fallback", False) or
                    getattr(self.embedder, "_genai_client", None) is False or
                    getattr(self.embedder, "_genai_client", None) is None or
                    all(x == 0.0 for x in v_user) or all(x == 0.0 for x in v_target)
                ):
                    is_fallback_embedding = True
            except Exception:
                sem_sim = 0.5
                is_fallback_embedding = True
        else:
            is_fallback_embedding = True

        # 2. Key Term Recall (Weight 0.35)
        target_kw = extract_keywords(t_clean)
        user_kw = extract_keywords(u_clean)

        matched = [k for k in target_kw if k in user_kw or any(k in u for u in user_kw)]
        missing = [k for k in target_kw if k not in matched]

        kw_recall = (len(matched) / len(target_kw)) if target_kw else 1.0

        # 3. Sequence Token Matcher (Weight 0.15)
        seq_ratio = difflib.SequenceMatcher(None, u_clean.lower(), t_clean.lower()).ratio()

        # If embedding is in fallback/offline mode (SHA-256 hashes), floor sem_sim with lexical overlap
        if is_fallback_embedding:
            text_sim = 0.6 * kw_recall + 0.4 * seq_ratio
            if len(matched) == 0 and kw_recall == 0.0 and seq_ratio < 0.25:
                sem_sim = 0.0
            else:
                sem_sim = max(sem_sim, text_sim)

        # Composite Score S
        composite = (0.50 * sem_sim) + (0.35 * kw_recall) + (0.15 * seq_ratio)
        score_percent = round(max(0.0, min(100.0, composite * 100.0)), 2)
        q_rating = map_score_to_q(score_percent)

        # Generate Feedback Rationale
        if q_rating == 5:
            rationale = "Outstanding active recall! Complete semantic accuracy."
        elif q_rating == 4:
            rationale = f"Solid response with high accuracy. Minor missing terms: {', '.join(missing[:3]) if missing else 'none'}."
        elif q_rating == 3:
            rationale = f"Passable recall, but missing core concepts: {', '.join(missing[:4]) if missing else 'partial detail'}."
        elif q_rating in (1, 2):
            rationale = f"Incomplete or incorrect response. Missing key concepts: {', '.join(missing[:5]) if missing else 'core terms'}."
        else:
            rationale = f"Incorrect recall blackout. Expected ground truth: '{t_clean}'."

        return {
            "score_percent": score_percent,
            "q_rating": q_rating,
            "feedback_rationale": rationale,
            "feedback": rationale,
            "matched_concepts": matched,
            "missing_concepts": missing,
            "metrics": {
                "semantic_similarity": round(sem_sim, 4),
                "keyword_recall": round(kw_recall, 4),
                "sequence_match": round(seq_ratio, 4)
            }
        }


def evaluate_answer(question_dict: Dict[str, Any], user_answer: str) -> Dict[str, Any]:
    """
    Evaluates user answer against a question dict.
    Calculates accuracy score (0-100%), Q rating (0-5), feedback, and SM-2 update.
    """
    target = question_dict.get("target_answer") or question_dict.get("answer") or ""
    evaluator = ResponseEvaluator()
    res = evaluator.evaluate_response(user_answer, target)

    # Extract SM-2 state if present in question_dict
    cur_n = int(question_dict.get("repetition_n", 0))
    cur_ef = float(question_dict.get("ease_factor", 2.5))
    cur_interval = float(question_dict.get("interval_days", 0.0))
    q_rating = res["q_rating"]

    new_n, new_ef, new_interval = calculate_sm2_update(cur_n, cur_ef, cur_interval, q_rating)

    res["sm2_update"] = {
        "repetition_n": new_n,
        "ease_factor": new_ef,
        "interval_days": new_interval,
        "q_rating": q_rating
    }
    res["updated_sm2_tuple"] = (new_n, new_ef, new_interval)
    return res


def parse_zettel_markdown(file_path: Union[str, Path]) -> Dict[str, Any]:
    """Parses an Obsidian Zettelkasten markdown note file into an entity dict."""
    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"Markdown file not found: {file_path}")

    text = p.read_text(encoding="utf-8", errors="ignore")
    title = p.stem

    # Extract frontmatter if present
    yaml_match = re.search(r'^---\s*\n(.*?)\n---', text, re.DOTALL)
    z_id = f"Zettel_{p.stem}"
    _tags = []
    if yaml_match:
        yaml_text = yaml_match.group(1)
        id_match = re.search(r'^id:\s*(.+)$', yaml_text, re.MULTILINE)
        if id_match:
            z_id = id_match.group(1).strip()
        title_match = re.search(r'^title:\s*(.+)$', yaml_text, re.MULTILINE)
        if title_match:
            title = title_match.group(1).strip()

    # Extract H1 title if present
    h1_match = re.search(r'^#\s+(.+)$', text, re.MULTILINE)
    if h1_match:
        title = h1_match.group(1).strip()

    # Extract Core Claim / Content section
    claim_match = re.search(r'##\s+Core Claim[^\n]*\n(.*?)(?=\n##|\Z)', text, re.DOTALL | re.IGNORECASE)
    core_claim = claim_match.group(1).strip() if claim_match else text[:300].strip()

    # Extract Wikilinks [[Link]]
    wikilinks = re.findall(r'\[\[(.*?)\]\]', text)

    return {
        "id": z_id,
        "node_id": z_id,
        "node_type": "ZettelNote",
        "title": title,
        "name": title,
        "core_claim": core_claim,
        "statement": core_claim,
        "content": text,
        "wikilinks": list(set(wikilinks)),
        "source_file": str(p)
    }


class CognitiveTutorEngine:
    """Manager for Spaced Repetition tutor cards and review persistence in SQLite."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH, wiki_dir: str = DEFAULT_WIKI_DIR):
        self.db_path = db_path
        self.wiki_dir = wiki_dir
        self.evaluator = ResponseEvaluator()
        self._ensure_tables()

    @contextmanager
    def _get_connection(self):
        p = Path(self.db_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=30000;")
        except Exception:
            pass
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _ensure_tables(self):
        p = Path(self.db_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with self._get_connection() as conn:
            # Create tutor_cards table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tutor_cards (
                    id TEXT PRIMARY KEY,
                    entity_id TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    question_type TEXT NOT NULL,
                    question_text TEXT NOT NULL,
                    target_answer TEXT NOT NULL,
                    repetition_n INTEGER DEFAULT 0,
                    ease_factor REAL DEFAULT 2.5,
                    interval_days REAL DEFAULT 0.0,
                    lapses INTEGER DEFAULT 0,
                    last_review_at TEXT,
                    next_review_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)
            # Create tutor_reviews table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tutor_reviews (
                    id TEXT PRIMARY KEY,
                    card_id TEXT NOT NULL,
                    score_percent REAL NOT NULL,
                    q_rating INTEGER NOT NULL,
                    user_response TEXT NOT NULL,
                    feedback_rationale TEXT NOT NULL,
                    response_time_sec REAL DEFAULT 0,
                    reviewed_at TEXT NOT NULL,
                    FOREIGN KEY (card_id) REFERENCES tutor_cards(id) ON DELETE CASCADE
                );
            """)
            # Create index for fast due queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_tutor_cards_due
                ON tutor_cards (next_review_at, ease_factor);
            """)

            # Create alias views for kg_flashcards and kg_review_logs for backwards compatibility
            conn.execute("DROP VIEW IF EXISTS kg_flashcards;")
            conn.execute("CREATE VIEW IF NOT EXISTS kg_flashcards AS SELECT * FROM tutor_cards;")

            conn.execute("DROP VIEW IF EXISTS kg_review_logs;")
            conn.execute("CREATE VIEW IF NOT EXISTS kg_review_logs AS SELECT * FROM tutor_reviews;")

            conn.commit()

    def save_card(self, card_dict: Dict[str, Any]) -> str:
        """Saves or updates a tutor card in SQLite persistence."""
        cid = str(card_dict.get("id") or card_dict.get("card_id") or f"card_{uuid.uuid4().hex[:12]}")
        ent_id = str(card_dict.get("entity_id") or "unknown_entity")
        ent_type = str(card_dict.get("entity_type") or "ThesisNode")
        q_type = str(card_dict.get("question_type") or "CONCEPT_EXPLANATION")
        q_text = str(card_dict.get("question_text") or "")
        t_ans = str(card_dict.get("target_answer") or "")

        rep_n = int(card_dict.get("repetition_n", 0))
        ef = float(card_dict.get("ease_factor", 2.5))
        interval = float(card_dict.get("interval_days", 0.0))
        lapses = int(card_dict.get("lapses", 0))

        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        last_rev = card_dict.get("last_review_at")
        next_rev = card_dict.get("next_review_at") or now_str

        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO tutor_cards (
                    id, entity_id, entity_type, question_type, question_text,
                    target_answer, repetition_n, ease_factor, interval_days,
                    lapses, last_review_at, next_review_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    entity_id=excluded.entity_id,
                    entity_type=excluded.entity_type,
                    question_type=excluded.question_type,
                    question_text=excluded.question_text,
                    target_answer=excluded.target_answer,
                    repetition_n=excluded.repetition_n,
                    ease_factor=excluded.ease_factor,
                    interval_days=excluded.interval_days,
                    lapses=excluded.lapses,
                    last_review_at=excluded.last_review_at,
                    next_review_at=excluded.next_review_at,
                    updated_at=excluded.updated_at
            """, (cid, ent_id, ent_type, q_type, q_text, t_ans, rep_n, ef, interval, lapses, last_rev, next_rev, now_str, now_str))
            conn.commit()

        return cid

    def create_cards_from_entity(self, entity_dict: Dict[str, Any]) -> List[str]:
        """Generates active recall questions for an entity and persists them to SQLite."""
        q_objs = generate_all_questions_for_entity(entity_dict)
        created_ids = []
        for q in q_objs:
            cid = self.save_card(q)
            created_ids.append(cid)
        return created_ids

    def get_card(self, card_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single card by ID."""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM tutor_cards WHERE id = ?", (card_id,)).fetchone()
            return dict(row) if row else None

    def get_due_cards(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Retrieves cards due for review (next_review_at <= NOW or next_review_at IS NULL)."""
        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT * FROM tutor_cards
                WHERE next_review_at IS NULL OR next_review_at <= ?
                ORDER BY next_review_at ASC
                LIMIT ?
            """, (now_str, limit)).fetchall()
            return [dict(r) for r in rows]

    def get_all_cards(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieves all flashcards."""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM tutor_cards ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
            return [dict(r) for r in rows]

    def process_review(self, card_id: str, user_answer: str, response_time_sec: float = 0.0) -> Dict[str, Any]:
        """Evaluates review, updates SM-2 card state, logs review attempt, and persists in SQLite."""
        card = self.get_card(card_id)
        if not card:
            raise ValueError(f"Tutor card with ID '{card_id}' not found.")

        eval_res = evaluate_answer(card, user_answer)

        score = eval_res["score_percent"]
        q_rating = eval_res["q_rating"]
        feedback = eval_res["feedback_rationale"]

        cur_n = card["repetition_n"]
        cur_ef = card["ease_factor"]
        cur_interval = card["interval_days"]
        cur_lapses = card["lapses"]

        new_n, new_ef, new_interval = calculate_sm2_update(cur_n, cur_ef, cur_interval, q_rating)
        new_lapses = cur_lapses + (1 if q_rating < 3 else 0)

        now_dt = datetime.datetime.now(datetime.timezone.utc)
        next_dt = now_dt + datetime.timedelta(days=new_interval)

        now_str = now_dt.isoformat()
        next_str = next_dt.isoformat()

        # Update card in SQLite
        card["repetition_n"] = new_n
        card["ease_factor"] = new_ef
        card["interval_days"] = new_interval
        card["lapses"] = new_lapses
        card["last_review_at"] = now_str
        card["next_review_at"] = next_str
        self.save_card(card)

        # Log review attempt
        review_id = f"review_{uuid.uuid4().hex[:12]}"
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO tutor_reviews (
                    id, card_id, score_percent, q_rating, user_response,
                    feedback_rationale, response_time_sec, reviewed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (review_id, card_id, score, q_rating, user_answer, feedback, response_time_sec, now_str))
            conn.commit()

        return {
            "review_id": review_id,
            "card_id": card_id,
            "score_percent": score,
            "q_rating": q_rating,
            "feedback_rationale": feedback,
            "feedback": feedback,
            "sm2_update": {
                "repetition_n": new_n,
                "ease_factor": new_ef,
                "interval_days": new_interval,
                "lapses": new_lapses,
                "next_review_at": next_str
            }
        }

    def get_mastery_stats(self) -> Dict[str, Any]:
        """Calculates mastery statistics across cards and historical review logs."""
        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row

            total_cards = conn.execute("SELECT COUNT(*) FROM tutor_cards").fetchone()[0]
            due_cards = conn.execute("SELECT COUNT(*) FROM tutor_cards WHERE next_review_at IS NULL OR next_review_at <= ?", (now_str,)).fetchone()[0]
            total_reviews = conn.execute("SELECT COUNT(*) FROM tutor_reviews").fetchone()[0]

            avg_score_row = conn.execute("SELECT AVG(score_percent) FROM tutor_reviews").fetchone()
            avg_score = round(avg_score_row[0], 2) if avg_score_row and avg_score_row[0] is not None else 0.0

            avg_q_row = conn.execute("SELECT AVG(q_rating) FROM tutor_reviews").fetchone()
            avg_q = round(avg_q_row[0], 2) if avg_q_row and avg_q_row[0] is not None else 0.0

            q_dist_rows = conn.execute("SELECT q_rating, COUNT(*) as cnt FROM tutor_reviews GROUP BY q_rating").fetchall()
            q_distribution = {i: 0 for i in range(6)}
            for r in q_dist_rows:
                q_distribution[r["q_rating"]] = r["cnt"]

            mastery_level = "Novice"
            if total_cards > 0:
                mastered_cards = conn.execute("SELECT COUNT(*) FROM tutor_cards WHERE repetition_n >= 3 AND ease_factor >= 2.3").fetchone()[0]
                ratio = mastered_cards / float(total_cards)
                if ratio >= 0.8:
                    mastery_level = "Master"
                elif ratio >= 0.5:
                    mastery_level = "Proficient"
                elif ratio >= 0.2:
                    mastery_level = "Apprentice"

            return {
                "total_cards": total_cards,
                "due_cards": due_cards,
                "total_reviews": total_reviews,
                "average_score_percent": avg_score,
                "average_q_rating": avg_q,
                "q_distribution": q_distribution,
                "mastery_level": mastery_level
            }

    def sync_zettelkasten_notes(self, wiki_dir: Optional[str] = None) -> int:
        """Parses Markdown notes from Zettelkasten directory and generates cards for new notes."""
        target_dir = Path(wiki_dir or self.wiki_dir)
        if not target_dir.exists():
            return 0

        count = 0
        for md_file in target_dir.glob("*.md"):
            try:
                z_entity = parse_zettel_markdown(md_file)
                self.create_cards_from_entity(z_entity)
                count += 1
            except Exception:
                continue

        return count
