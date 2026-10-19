"""
vazus_core/kgb_analytical_extractor.py
KGB/FSB ИАД + ACH Analytical Extractor Engine for vazus SuperGraph OS.

Implements:
1. ИАД (Information-Analytical Diagnostics) scene/text decomposition into ThesisNode (facts, claims)
   and ProtocolNode (rules, procedures).
2. ACH (Analysis of Competing Hypotheses) matrix evaluation calculating weighted inconsistency scores
   and identifying conflicting statements (CONTRADICTS).
3. Edge relation detection: CAUSES, REQUIRES, CONTRADICTS, and BELONGS_TO.
4. 768D vector embedding persistence via UnifiedEmbeddingManager into kg_nodes and kg_edges in vazus.db.
"""

import os
import sys
import re
import json
import sqlite3
import hashlib
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Set, Union

# Import UnifiedEmbeddingManager from vazus_core.memory.embeddings
try:
    from vazus_core.memory.embeddings import UnifiedEmbeddingManager
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from vazus_core.memory.embeddings import UnifiedEmbeddingManager

# Import text normalization from multimodal_knowledge if available
try:
    from vazus_core.memory.multimodal_knowledge import normalize_russian_text
except ImportError:
    def normalize_russian_text(text: str) -> str:
        if not text:
            return ""
        text = re.sub(r'\[[^\]]*\]', ' ', text)
        text = re.sub(r'\(\s*(?:музыка|смех|аплодисменты|шум|кашель|вздох|пауза|тишина|laughter|music|applause)\s*\)', ' ', text, flags=re.I)
        text = text.replace('\xa0', ' ').replace('\u200b', '')
        return re.sub(r'\s+', ' ', text).strip()


DEFAULT_DB_PATH = os.environ.get("VAZUS_DB_PATH", r"/home/tarhes/Проекты/vazus/services/memory/vazus.db")
SECONDARY_DB_PATH = os.environ.get("VAZUS_DB_PATH", r"/home/tarhes/Проекты/vazus/services/memory/vazus.db")
TERTIARY_DB_PATH = os.environ.get("VAZUS_DB_PATH", r"/home/tarhes/Проекты/vazus/services/memory/vazus.db")


class ThesisNode:
    """Represents an analytical claim, factual assertion, hypothesis, or scientific thesis."""
    def __init__(
        self,
        id: str,
        name: str,
        statement: str,
        *,
        confidence: float = 0.85,
        confidence_score: Optional[float] = None,
        domain: str = "kgb_analytics",
        node_type: str = "ThesisNode",
        ach_status: str = "HYPOTHESIS",
        evidence_sources: Optional[List[str]] = None,
        source_file: str = "",
        scene_id: str = "",
        start_sec: float = 0.0,
        end_sec: float = 0.0,
        tags: Union[str, List[str]] = "iad,thesis",
        properties: Optional[Dict[str, Any]] = None,
        embedding_json: Optional[str] = None,
        node_id: Optional[str] = None
    ):
        self.id = node_id or id
        self.node_id = self.id
        self.name = name
        self.statement = statement
        self.confidence = confidence_score if confidence_score is not None else confidence
        self.confidence_score = self.confidence
        self.domain = domain
        self.node_type = "ThesisNode"
        self.ach_status = ach_status
        self.evidence_sources = evidence_sources or []
        self.source_file = source_file
        self.scene_id = scene_id
        self.start_sec = start_sec
        self.end_sec = end_sec
        self.tags = tags if isinstance(tags, str) else ",".join(tags)
        self.properties = properties or {}
        self.embedding_json = embedding_json

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "node_id": self.id,
            "name": self.name,
            "statement": self.statement,
            "confidence": self.confidence,
            "confidence_score": self.confidence_score,
            "domain": self.domain,
            "node_type": "ThesisNode",
            "ach_status": self.ach_status,
            "evidence_sources": self.evidence_sources,
            "source_file": self.source_file,
            "scene_id": self.scene_id,
            "start_sec": self.start_sec,
            "end_sec": self.end_sec,
            "tags": self.tags,
            "properties": self.properties,
            "embedding_json": self.embedding_json
        }


class ProtocolNode:
    """Represents an operational directive, protocol, step-by-step algorithm, or procedure."""
    def __init__(
        self,
        id: str,
        name: str,
        action_instruction: str = "",
        *,
        steps: Optional[List[str]] = None,
        prerequisites: Optional[List[str]] = None,
        sequence_order: int = 1,
        target_outcome: str = "",
        frequency_periodicity: str = "",
        safety_warnings: Optional[List[str]] = None,
        domain: str = "kgb_analytics",
        node_type: str = "ProtocolNode",
        source_file: str = "",
        scene_id: str = "",
        start_sec: float = 0.0,
        end_sec: float = 0.0,
        tags: Union[str, List[str]] = "iad,protocol",
        properties: Optional[Dict[str, Any]] = None,
        embedding_json: Optional[str] = None,
        node_id: Optional[str] = None
    ):
        self.id = node_id or id
        self.node_id = self.id
        self.name = name
        self.action_instruction = action_instruction or (steps[0] if steps else name)
        self.steps = steps or ([self.action_instruction] if self.action_instruction else [])
        self.prerequisites = prerequisites or []
        self.sequence_order = sequence_order
        self.target_outcome = target_outcome
        self.frequency_periodicity = frequency_periodicity
        self.safety_warnings = safety_warnings or []
        self.domain = domain
        self.node_type = "ProtocolNode"
        self.source_file = source_file
        self.scene_id = scene_id
        self.start_sec = start_sec
        self.end_sec = end_sec
        self.tags = tags if isinstance(tags, str) else ",".join(tags)
        self.properties = properties or {}
        self.embedding_json = embedding_json

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "node_id": self.id,
            "name": self.name,
            "action_instruction": self.action_instruction,
            "steps": self.steps,
            "prerequisites": self.prerequisites,
            "sequence_order": self.sequence_order,
            "target_outcome": self.target_outcome,
            "frequency_periodicity": self.frequency_periodicity,
            "safety_warnings": self.safety_warnings,
            "domain": self.domain,
            "node_type": "ProtocolNode",
            "source_file": self.source_file,
            "scene_id": self.scene_id,
            "start_sec": self.start_sec,
            "end_sec": self.end_sec,
            "tags": self.tags,
            "properties": self.properties,
            "embedding_json": self.embedding_json
        }


class KGBAnalyticalExtractor:
    """
    KGB/FSB ИАД (Information-Analytical Diagnostics) + ACH (Analysis of Competing Hypotheses) Engine.
    Processes scene dicts or raw text, decomposes into ThesisNode and ProtocolNode entities,
    detects CAUSES, REQUIRES, CONTRADICTS, and BELONGS_TO edges, computes ACH matrices,
    generates 768D Gemini embeddings, and persists into SQLite SuperGraph databases.
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH, vector_dim: int = 768):
        self.db_path = db_path
        self.embedder = UnifiedEmbeddingManager(dimension=vector_dim)
        self._ensure_tables(self.db_path)

    def _ensure_tables(self, db_path: str):
        """Ensures kg_nodes and kg_edges tables exist in the specified SQLite database."""
        try:
            p = Path(db_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(db_path) as conn:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS kg_nodes (
                        id TEXT PRIMARY KEY,
                        name TEXT,
                        domain TEXT,
                        node_type TEXT,
                        description TEXT,
                        tags TEXT,
                        properties TEXT,
                        embedding_json TEXT
                    );

                    CREATE TABLE IF NOT EXISTS kg_edges (
                        source_id TEXT,
                        target_id TEXT,
                        relation TEXT,
                        strength REAL,
                        properties TEXT,
                        PRIMARY KEY (source_id, target_id, relation)
                    );
                """)
                conn.commit()
        except Exception as e:
            sys.stderr.write(f"[KGB Extractor] DB table initialization note for {db_path}: {e}\n")

    def _create_protocol_from_sentence(
        self, sent_clean: str, node_hash: str, idx: int,
        *, source_file: str, scene_id: str, start_sec: float, end_sec: float, freq_pattern: str
    ) -> ProtocolNode:
        freq_match = re.findall(freq_pattern, sent_clean, re.IGNORECASE)
        periodicity = ", ".join(freq_match) if freq_match else ""
        safety_match = re.findall(r'(?:предотвращения|во избежание|опасно|риск|побочн|осторожно)[^.!?]*', sent_clean, re.IGNORECASE)
        name_title = sent_clean[:50] + ("..." if len(sent_clean) > 50 else "")
        return ProtocolNode(
            id=f"protocol_{node_hash}", name=name_title, action_instruction=sent_clean,
            steps=[sent_clean], sequence_order=idx + 1, frequency_periodicity=periodicity,
            safety_warnings=safety_match, source_file=source_file, scene_id=scene_id,
            start_sec=start_sec, end_sec=end_sec, tags="iad,protocol",
            properties={"raw_sentence": sent_clean, "step_index": idx + 1}
        )

    def _create_thesis_from_sentence(
        self, sent_clean: str, node_hash: str, idx: int,
        *, source_file: str, scene_id: str, start_sec: float, end_sec: float
    ) -> ThesisNode:
        conf = 0.85
        if re.search(r'\b(подтверждают|доказано|установлено|точно|100%|исследования)\b', sent_clean, re.I):
            conf = 0.95
        elif re.search(r'\b(возможно|предположительно|вероятно|может|гипотеза)\b', sent_clean, re.I):
            conf = 0.65
        name_title = sent_clean[:50] + ("..." if len(sent_clean) > 50 else "")
        return ThesisNode(
            id=f"thesis_{node_hash}", name=name_title, statement=sent_clean, confidence=conf,
            source_file=source_file, scene_id=scene_id, start_sec=start_sec, end_sec=end_sec,
            tags="iad,thesis", properties={"raw_sentence": sent_clean, "sentence_index": idx + 1}
        )

    def decompose_text(
        self, text: str, source_file: str = "", scene_id: str = "", start_sec: float = 0.0, end_sec: float = 0.0
    ) -> Tuple[List[ThesisNode], List[ProtocolNode]]:
        """Decomposes transcript / text into atomic ThesisNode and ProtocolNode entities using ИАД principles."""
        theses: List[ThesisNode] = []
        protocols: List[ProtocolNode] = []
        if not text:
            return theses, protocols
        normalized = normalize_russian_text(" ".join(str(i) for i in text if i) if isinstance(text, (list, tuple)) else str(text))
        if not normalized:
            return theses, protocols

        sentences = re.split(r'(?<=[.!?])\s+|\n+', normalized)
        protocol_patterns = [
            r'\bнеобходимо\b', r'\bследует\b', r'\bобязательно\b', r'\bшаг\b', r'\bправило\b', r'\bинструкция\b',
            r'\bрекомендуется\b', r'\bсделайте\b', r'\bпринимать\b', r'\bвыполните\b', r'\bиспользуйте\b',
            r'\bпротокол\b', r'\bдозировка\b', r'\bприменяйте\b', r'\bпринимайте\b', r'\bциклировани[ея]\b',
            r'\bmust\b', r'\bshould\b', r'\balways\b', r'\bprotocol\b', r'\bstep\b'
        ]
        freq_pattern = r'(\d+\s*(?:мг|г|мкг|МЕ|табл|капс|раз|недели|дней|минут|часов)\s*(?:в\s*день|ежедневно|перед\s*сном|в\s*течение|день|сутки|через)?|[0-9]+\s*недел[ьи]|\d+\s*дн[ейя])'

        for idx, sent in enumerate(sentences):
            sent_clean = sent.strip()
            if len(sent_clean) < 8:
                continue
            node_hash = hashlib.md5(f"{scene_id}:{sent_clean}".encode('utf-8')).hexdigest()[:8]
            is_protocol = any(re.search(pat, sent_clean, re.IGNORECASE) for pat in protocol_patterns)
            if is_protocol:
                protocols.append(self._create_protocol_from_sentence(sent_clean, node_hash, idx, source_file=source_file, scene_id=scene_id, start_sec=start_sec, end_sec=end_sec, freq_pattern=freq_pattern))
            if not is_protocol or re.search(r'\b(стимулирует|вызывает|приводит|снижает|повышает|является|подтверждают)\b', sent_clean, re.I):
                theses.append(self._create_thesis_from_sentence(sent_clean, node_hash, idx, source_file=source_file, scene_id=scene_id, start_sec=start_sec, end_sec=end_sec))

        return theses, protocols

    def _extract_single_node_subrelations(
        self, all_nodes: list, real_nodes: list, theses: list, protocols: list,
        *, scene_id: str, requires_edges: list, causes_edges: list, belongs_to_edges: list,
        requires_regex: re.Pattern, causal_regex: re.Pattern
    ) -> None:
        for i, n1 in enumerate(all_nodes):
            text1 = n1.statement if isinstance(n1, ThesisNode) else n1.action_instruction
            if requires_regex.search(text1):
                found_match = False
                for j, n2 in enumerate(all_nodes):
                    if i != j:
                        text2 = n2.statement if isinstance(n2, ThesisNode) else n2.action_instruction
                        words2 = [w.lower() for w in re.findall(r'\b[А-Яа-яA-Za-z0-9]{3,}\b', text2) if w.lower() not in ("для", "при", "или", "что", "как", "без", "этом")]
                        if any(w in text1.lower() for w in words2):
                            requires_edges.append({"source_id": n1.id, "target_id": n2.id, "relation": "REQUIRES", "strength": 0.85, "properties": {"prerequisite_statement": text2}})
                            found_match = True
                if not found_match or len(all_nodes) == 1:
                    parts = requires_regex.split(text1)
                    if len(parts) >= 3:
                        target_part, trigger, prereq_part = parts[0].strip(), parts[1].strip(), parts[2].strip()
                        prereq_id = f"protocol_{hashlib.md5(f'{scene_id}:{prereq_part}'.encode('utf-8')).hexdigest()[:8]}"
                        if not any(p.id == prereq_id for p in protocols) and not any(t.id == prereq_id for t in theses):
                            p_virt = ProtocolNode(id=prereq_id, name=prereq_part[:50] + ("..." if len(prereq_part) > 50 else ""), action_instruction=prereq_part, steps=[prereq_part], source_file=n1.source_file, scene_id=scene_id, start_sec=n1.start_sec, end_sec=n1.end_sec, tags="iad,protocol,virtual", properties={"raw_sentence": prereq_part, "virtual": True})
                            protocols.append(p_virt)
                            if scene_id:
                                belongs_to_edges.append({"source_id": p_virt.id, "target_id": scene_id, "relation": "BELONGS_TO", "strength": 1.0, "properties": {"scene_id": scene_id, "node_type": p_virt.node_type}})
                        requires_edges.append({"source_id": n1.id, "target_id": prereq_id, "relation": "REQUIRES", "strength": 0.90, "properties": {"target": target_part, "trigger": trigger, "prerequisite": prereq_part}})

            if causal_regex.search(text1) and (len(all_nodes) == 1 or len(real_nodes) <= 1):
                parts = causal_regex.split(text1)
                if len(parts) >= 3:
                    cause_part, trigger, effect_part = parts[0].strip(), parts[1].strip(), parts[2].strip()
                    c_id = f"thesis_{hashlib.md5(f'{scene_id}:{cause_part}'.encode('utf-8')).hexdigest()[:8]}"
                    e_id = f"thesis_{hashlib.md5(f'{scene_id}:{effect_part}'.encode('utf-8')).hexdigest()[:8]}"
                    for n_id, n_part in [(c_id, cause_part), (e_id, effect_part)]:
                        if not any(t.id == n_id for t in theses) and not any(p.id == n_id for p in protocols):
                            t_v = ThesisNode(id=n_id, name=n_part[:50] + ("..." if len(n_part) > 50 else ""), statement=n_part, confidence=0.85, source_file=n1.source_file, scene_id=scene_id, start_sec=n1.start_sec, end_sec=n1.end_sec, tags="iad,thesis,virtual", properties={"raw_sentence": n_part, "virtual": True})
                            theses.append(t_v)
                            if scene_id:
                                belongs_to_edges.append({"source_id": t_v.id, "target_id": scene_id, "relation": "BELONGS_TO", "strength": 1.0, "properties": {"scene_id": scene_id, "node_type": t_v.node_type}})
                    causes_edges.append({"source_id": c_id, "target_id": e_id, "relation": "CAUSES", "strength": 0.90, "properties": {"cause": cause_part, "trigger": trigger, "effect": effect_part}})

    def _extract_pairwise_relations(
        self, all_nodes: list, scene_id: str,
        *, causes_edges: list, contradicts_edges: list,
        causal_regex: re.Pattern, contradict_regex: re.Pattern, causal_adj: dict, has_path_fn
    ) -> None:
        for i, n1 in enumerate(all_nodes):
            text1 = n1.statement if isinstance(n1, ThesisNode) else n1.action_instruction
            for j, n2 in enumerate(all_nodes):
                if i >= j or getattr(n1, 'properties', {}).get('container') or getattr(n2, 'properties', {}).get('container') or n1.id == scene_id or n2.id == scene_id:
                    continue
                text2 = n2.statement if isinstance(n2, ThesisNode) else n2.action_instruction
                if causal_regex.search(text1) or causal_regex.search(text2):
                    src_node, dst_node = (n1, n2) if causal_regex.search(text1) else (n2, n1)
                    if not has_path_fn(dst_node.id, src_node.id):
                        causes_edges.append({"source_id": src_node.id, "target_id": dst_node.id, "relation": "CAUSES", "strength": 0.85, "properties": {"trigger": "causal_keyword"}})
                        causal_adj.setdefault(src_node.id, set()).add(dst_node.id)

                words1 = set(w.lower() for w in re.findall(r'\b[А-Яа-яA-Za-z0-9]{4,}\b', text1))
                words2 = set(w.lower() for w in re.findall(r'\b[А-Яа-яA-Za-z0-9]{4,}\b', text2))
                overlap = words1.intersection(words2)
                is_contradiction = False
                if contradict_regex.search(text1) or contradict_regex.search(text2):
                    is_contradiction = len(overlap) >= 1 or len(all_nodes) <= 3
                elif len(overlap) >= 2:
                    neg1 = bool(re.search(r'\b(не|без|отсутствие|ошибочно|заблуждение|опасно|противоречит)\b', text1, re.I))
                    neg2 = bool(re.search(r'\b(не|без|отсутствие|ошибочно|заблуждение|опасно|противоречит)\b', text2, re.I))
                    is_contradiction = neg1 != neg2

                if is_contradiction:
                    c_src, c_dst = (n2.id, n1.id) if contradict_regex.search(text2) and not contradict_regex.search(text1) else (n1.id, n2.id)
                    contradicts_edges.append({"source_id": c_src, "target_id": c_dst, "relation": "CONTRADICTS", "strength": 0.95, "properties": {"reason": "opposing_claims_or_negation"}})

    def extract_graph_edges(
        self, theses: List[ThesisNode], protocols: List[ProtocolNode], scene_id: str = ""
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Extracts graph relations: BELONGS_TO, CAUSES, REQUIRES, CONTRADICTS."""
        causes_edges, requires_edges, contradicts_edges, belongs_to_edges = [], [], [], []
        if scene_id and (theses or protocols):
            if not any(t.id == scene_id for t in theses) and not any(p.id == scene_id for p in protocols):
                theses.append(ThesisNode(id=scene_id, name=scene_id, statement=f"Scene container {scene_id}", confidence=1.0, source_file=scene_id, scene_id=scene_id, tags="iad,scene", properties={"scene_id": scene_id, "container": True}))

        all_nodes = theses + protocols
        real_nodes = [n for n in all_nodes if not (getattr(n, 'properties', {}).get('container') or n.id == scene_id)]
        if scene_id:
            for node in all_nodes:
                if node.id != scene_id:
                    belongs_to_edges.append({"source_id": node.id, "target_id": scene_id, "relation": "BELONGS_TO", "strength": 1.0, "properties": {"scene_id": scene_id, "node_type": node.node_type}})

        for prev_p, next_p in zip(protocols, protocols[1:]):
            requires_edges.append({"source_id": next_p.id, "target_id": prev_p.id, "relation": "REQUIRES", "strength": 0.90, "properties": {"type": "sequential_step", "prerequisite": prev_p.name}})

        causal_regex = re.compile(r'\b(приводит к|вызывает|вызывают|из-за|результатом является|способствует|влечет за собой|causes|leads to|results in|stimulates)\b', re.I)
        requires_regex = re.compile(r'\b(требует|необходимо|сопроводительный прием|предполагает наличие|при условии|обязательным условием|requires|prerequisite|depends on)\b', re.I)
        contradict_regex = re.compile(r'\b(в отличие от|ошибочно|заблуждение|противоречит|напротив|опровергает|наоборот|вместо того чтобы|contradicts|opposes|inconsistent)\b', re.I)

        causal_adj: Dict[str, Set[str]] = {}

        def has_path(src: str, dst: str, visited: Optional[Set[str]] = None) -> bool:
            vis = visited if visited is not None else set()
            if src == dst:
                return True
            vis.add(src)
            return any(nxt not in vis and has_path(nxt, dst, vis) for nxt in causal_adj.get(src, set()))

        self._extract_single_node_subrelations(
            all_nodes, real_nodes, theses, protocols,
            scene_id=scene_id, requires_edges=requires_edges, causes_edges=causes_edges,
            belongs_to_edges=belongs_to_edges, requires_regex=requires_regex, causal_regex=causal_regex
        )
        self._extract_pairwise_relations(
            all_nodes, scene_id,
            causes_edges=causes_edges, contradicts_edges=contradicts_edges,
            causal_regex=causal_regex, contradict_regex=contradict_regex, causal_adj=causal_adj, has_path_fn=has_path
        )
        return causes_edges, requires_edges, contradicts_edges, belongs_to_edges

    def _parse_extract_input(self, data: Any) -> Tuple[str, str, float, float, str]:
        d = {"transcript": data} if isinstance(data, str) else (data if isinstance(data, dict) else {"transcript": str(data or "")})
        raw_id = d.get("scene_id")
        scene_id = str(raw_id) if raw_id else f"scene_{hashlib.md5(str(time.time()).encode()).hexdigest()[:8]}"
        src_file = str(d.get("source_file", "") or "")
        try:
            s_sec = float(d.get("start_sec", 0.0))
        except (TypeError, ValueError):
            s_sec = 0.0
        try:
            e_sec = float(d.get("end_sec", 0.0))
        except (TypeError, ValueError):
            e_sec = 0.0
        text = d.get("transcript") or d.get("text") or d.get("content") or ""
        return scene_id, src_file, s_sec, e_sec, text

    def _resolve_hypotheses_and_ach(
        self, data: Any, theses: List[ThesisNode], scene_id: str, contradicts_edges: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        d = data if isinstance(data, dict) else {}
        input_h = d.get("hypotheses", [])
        if not isinstance(input_h, list):
            input_h = [{"id": "H1", "label": input_h}] if isinstance(input_h, str) else ([input_h] if isinstance(input_h, dict) else [])
        if not input_h and theses:
            valid_t = [t for t in theses if not (getattr(t, 'properties', {}).get('container') or t.id == scene_id or "scene" in getattr(t, 'tags', ''))]
            input_h = [{"id": t.id, "label": t.statement} for t in (valid_t[:5] if valid_t else theses[:5])]

        ach_summary = evaluate_ach_hypotheses(hypotheses=input_h, evidence=theses)
        status_map = {r["hypothesis_id"]: r["ach_status"] for r in ach_summary.get("ranked_hypotheses", [])}
        for t in theses:
            if t.id in status_map:
                t.ach_status = status_map[t.id]

        for edge in contradicts_edges:
            src_node = next((t for t in theses if t.id == edge.get("source_id")), None)
            dst_node = next((t for t in theses if t.id == edge.get("target_id")), None)
            if src_node and dst_node:
                if src_node.confidence >= dst_node.confidence:
                    dst_node.ach_status = "REJECTED"
                    if src_node.ach_status in ("REJECTED", "HYPOTHESIS"):
                        src_node.ach_status = "ACCEPTED"
                else:
                    src_node.ach_status = "REJECTED"
                    if dst_node.ach_status in ("REJECTED", "HYPOTHESIS"):
                        dst_node.ach_status = "ACCEPTED"
            elif dst_node:
                dst_node.ach_status = "REJECTED"

        return ach_summary

    def extract(self, scene_or_text_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Processes input scene / text dictionary and executes ИАД + ACH extraction pipeline."""
        scene_id, source_file, start_sec, end_sec, text = self._parse_extract_input(scene_or_text_dict)
        theses, protocols = self.decompose_text(text=text, source_file=source_file, scene_id=scene_id, start_sec=start_sec, end_sec=end_sec)
        causes_edges, requires_edges, contradicts_edges, belongs_to_edges = self.extract_graph_edges(theses=theses, protocols=protocols, scene_id=scene_id)
        ach_summary = self._resolve_hypotheses_and_ach(scene_or_text_dict, theses, scene_id, contradicts_edges)

        all_nodes = [t.to_dict() for t in theses] + [p.to_dict() for p in protocols]
        all_edges = causes_edges + requires_edges + contradicts_edges + belongs_to_edges
        result = {
            "scene_id": scene_id, "source_file": source_file,
            "theses_extracted": len(theses), "protocols_extracted": len(protocols), "edges_extracted": len(all_edges),
            "thesis_nodes": [t.to_dict() for t in theses], "protocol_nodes": [p.to_dict() for p in protocols],
            "causes_edges": causes_edges, "requires_edges": requires_edges, "contradicts_edges": contradicts_edges,
            "belongs_to_edges": belongs_to_edges, "nodes": all_nodes, "edges": all_edges,
            "ach_matrix_summary": ach_summary, "status": "SUCCESS"
        }
        result["persisted_counts"] = {"total_entities": self.persist(result)}
        return result

    def persist(self, extraction_result: Dict[str, Any], db_path: Optional[str] = None) -> int:
        target_path = db_path or self.db_path
        return persist_kgb_analytics_to_supergraph(extraction_result, db_path=target_path)


def _sanitize_hypotheses_list(hypotheses: Any) -> List[Dict[str, Any]]:
    raw = [{"id": "H1", "label": hypotheses}] if isinstance(hypotheses, str) else ([hypotheses] if isinstance(hypotheses, dict) else (hypotheses if isinstance(hypotheses, list) else []))
    res = []
    for i, h in enumerate(raw):
        if isinstance(h, str):
            res.append({"id": f"H{i+1}", "label": h})
        elif isinstance(h, dict):
            hc = dict(h)
            hc.setdefault("id", f"H{i+1}")
            hc.setdefault("label", str(hc.get("statement") or hc.get("name") or str(hc)))
            res.append(hc)
        else:
            res.append({"id": f"H{i+1}", "label": str(h)})
    return res

def _calculate_evidence_inconsistency(
    ev_list: list, hypotheses: list, scores: dict, contradictions_detected: list, neg_words: re.Pattern
) -> list:
    matrix = []
    for ev in ev_list:
        ev_id = ev.get("id") or ev.get("node_id", "E_unknown")
        ev_stmt = ev.get("statement") or ev.get("name") or ev.get("description") or ""
        ev_conf = float(ev.get("confidence") or ev.get("confidence_score") or 0.85)
        row = {"evidence_id": ev_id, "evidence_statement": ev_stmt, "confidence": ev_conf, "ratings": {}}
        ev_words = set(w.lower() for w in re.findall(r'\b[А-Яа-яA-Za-z0-9]{4,}\b', ev_stmt))

        for h in hypotheses:
            h_id = h.get("id") or h.get("label", "H_unknown")
            h_label = h.get("label") or h.get("statement") or h.get("name") or ""
            h_words = set(w.lower() for w in re.findall(r'\b[А-Яа-яA-Za-z0-9]{4,}\b', h_label))
            if ev_words.intersection(h_words):
                if bool(neg_words.search(ev_stmt)) != bool(neg_words.search(h_label)):
                    rating = -1.0
                    scores[h_id] += ev_conf * 1.0
                    contradictions_detected.append({"evidence_id": ev_id, "hypothesis_id": h_id, "evidence_statement": ev_stmt, "hypothesis_label": h_label, "inconsistency_weight": ev_conf})
                else:
                    rating = 1.0
            else:
                rating = 0.0
            row["ratings"][h_id] = rating
        matrix.append(row)
    return matrix

def evaluate_ach_hypotheses(
    hypotheses: List[Dict[str, Any]], evidence: List[Union[Dict[str, Any], ThesisNode]]
) -> Dict[str, Any]:
    """Evaluates an Analysis of Competing Hypotheses (ACH) matrix."""
    scores: Dict[str, float] = {}
    contradictions_detected: List[Dict[str, Any]] = []
    hypotheses = _sanitize_hypotheses_list(hypotheses)
    ev_list = [ev.to_dict() if isinstance(ev, ThesisNode) else ev for ev in (evidence if isinstance(evidence, list) else []) if isinstance(ev, (dict, ThesisNode))]

    for h in hypotheses:
        scores[h.get("id") or h.get("label", "H_unknown")] = 0.0

    neg_words = re.compile(r'\b(не|без|отсутствие|против|опасн\w*|ошибочн\w*|заблужден\w*|неэффективн\w*|противореч\w*|опроверг\w*|вредн\w*|not|no|harmful|inconsistent|contradict\w*)\b', re.I)
    matrix = _calculate_evidence_inconsistency(ev_list, hypotheses, scores, contradictions_detected, neg_words)

    sorted_h = sorted(scores.items(), key=lambda x: x[1])
    min_score = sorted_h[0][1] if sorted_h else 0.0
    max_score = sorted_h[-1][1] if sorted_h else 0.0

    ranked = []
    first_accepted = False
    for h_id, score in sorted_h:
        if score == min_score:
            status = "ACCEPTED" if (not first_accepted or min_score == 0.0) else "REJECTED"
            first_accepted = True
        elif score == max_score and len(sorted_h) > 1 and max_score > min_score:
            status = "DISPROVED"
        else:
            status = "REJECTED"
        ranked.append({"hypothesis_id": h_id, "inconsistency_score": round(score, 4), "ach_status": status})

    return {"matrix": matrix, "inconsistency_scores": {k: round(v, 4) for k, v in scores.items()}, "ranked_hypotheses": ranked, "contradictions_detected": contradictions_detected}


def extract_kgb_analytics(
    scene_or_text_dict: Dict[str, Any],
    db_path: str = DEFAULT_DB_PATH
) -> Dict[str, Any]:
    """Main export function: extracts KGB/FSB ИАД analytics and ACH matrix evaluations."""
    if isinstance(scene_or_text_dict, str):
        scene_or_text_dict = {"transcript": scene_or_text_dict}
    extractor = KGBAnalyticalExtractor(db_path=db_path)
    return extractor.extract(scene_or_text_dict)


def _insert_supergraph_nodes(conn: sqlite3.Connection, nodes: list, embedder: UnifiedEmbeddingManager) -> int:
    inserted = 0
    for n in nodes:
        node_id = n.get("id") or n.get("node_id")
        name = n.get("name") or node_id
        domain = n.get("domain", "kgb_analytics")
        node_type = n.get("node_type", "ThesisNode")
        desc = n.get("statement") or n.get("action_instruction") or name
        tags = ",".join(n.get("tags")) if isinstance(n.get("tags"), list) else n.get("tags")

        emb = embedder.get_embedding(f"{name} {desc}")
        emb_json = json.dumps(emb)
        props = n.get("properties") or {}
        props["confidence"] = n.get("confidence") or n.get("confidence_score")
        props["ach_status"] = n.get("ach_status")
        props["steps"] = n.get("steps")
        props["frequency_periodicity"] = n.get("frequency_periodicity")
        props_json = json.dumps(props, ensure_ascii=False)

        conn.execute("""
            INSERT OR REPLACE INTO kg_nodes (id, name, domain, node_type, description, tags, properties, embedding_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (node_id, name, domain, node_type, desc, tags, props_json, emb_json))
        inserted += 1
    return inserted

def _insert_supergraph_edges(conn: sqlite3.Connection, edges: list) -> int:
    inserted = 0
    for e in edges:
        src = e.get("source_id")
        dst = e.get("target_id")
        rel = e.get("relation")
        strength = float(e.get("strength", 1.0))
        eprops = e.get("properties") or {}
        eprops_json = json.dumps(eprops, ensure_ascii=False)
        if src and dst and rel:
            conn.execute("""
                INSERT OR REPLACE INTO kg_edges (source_id, target_id, relation, strength, properties)
                VALUES (?, ?, ?, ?, ?)
            """, (src, dst, rel, strength, eprops_json))
            inserted += 1
    return inserted

def persist_kgb_analytics_to_supergraph(
    extraction_result: Dict[str, Any],
    db_path: str = DEFAULT_DB_PATH
) -> int:
    """Persists extracted entities into SQLite tables kg_nodes and kg_edges in vazus.db."""
    embedder = UnifiedEmbeddingManager(dimension=768)
    nodes = extraction_result.get("nodes") or (extraction_result.get("thesis_nodes", []) + extraction_result.get("protocol_nodes", []))
    edges = extraction_result.get("edges") or (
        extraction_result.get("causes_edges", []) + extraction_result.get("requires_edges", []) +
        extraction_result.get("contradicts_edges", []) + extraction_result.get("belongs_to_edges", [])
    )

    target_dbs = [db_path, SECONDARY_DB_PATH]
    if Path(TERTIARY_DB_PATH).parent.exists():
        target_dbs.append(TERTIARY_DB_PATH)

    total_inserted = 0
    for dbp in set(target_dbs):
        try:
            Path(dbp).parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(dbp) as conn:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS kg_nodes (
                        id TEXT PRIMARY KEY, name TEXT, domain TEXT, node_type TEXT,
                        description TEXT, tags TEXT, properties TEXT, embedding_json TEXT
                    );
                    CREATE TABLE IF NOT EXISTS kg_edges (
                        source_id TEXT, target_id TEXT, relation TEXT, strength REAL,
                        properties TEXT, PRIMARY KEY (source_id, target_id, relation)
                    );
                """)
                total_inserted += _insert_supergraph_nodes(conn, nodes, embedder)
                total_inserted += _insert_supergraph_edges(conn, edges)
                conn.commit()
        except Exception as err:
            sys.stderr.write(f"[KGB Extractor] Persistence warning for {dbp}: {err}\n")
    return total_inserted


if __name__ == "__main__":
    sample_data = {
        "scene_id": "scene_demo_01",
        "transcript": "Высокие дозы Витамина D3 стимулируют синтез остеокальцина. Приём Витамина D3 требует обязательного приёма Витамина K2 и Магния.",
        "hypotheses": [
            {"id": "H1", "label": "Витамин D3 стимулирует остеокальцин"},
            {"id": "H2", "label": "Витамин D3 не стимулирует остеокальцин"}
        ]
    }
    output = extract_kgb_analytics(sample_data)
    print("Extracted output status:", output["status"])
    print("Theses count:", output["theses_extracted"])
    print("Protocols count:", output["protocols_extracted"])
    print("Edges count:", output["edges_extracted"])
    print("Persisted count:", output["persisted_counts"])
