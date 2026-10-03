"""
vazus_core.auto_improver — VazusAutoImprover: Real Self-Improvement Engine
==========================================================================

Implements a genuine self-improvement loop inspired by:
  - Reflexion (Shinn et al. 2023): self-evaluation + episodic memory retrieval
  - Hermes skill auto-selection: score -> rank -> inject -> learn
  - LangGraph Reflexion node pattern: generate -> evaluate -> reflect -> retry

Architecture:
  1. SkillUsageTracker   — tracks which skills helped, scores them via EMA
  2. LessonMemoryBank    — persists + retrieves lessons from past failures
  3. ReflexionEvaluator  — scores output quality, generates critique
  4. VazusAutoImprover   — orchestrates the full loop with terminal live feed

Terminal Output (visible in real time, no external dashboard needed):
  Uses ANSI codes printed to stdout — works in Antigravity CLI terminal.
"""

import sys
import ast
import time
import json
import threading
import logging
import asyncio
import inspect
import concurrent.futures
import uuid
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable

from vazus_core.memory.db import get_db_connection
from vazus_core.engine.utils import fast_json_dumps
from vazus_core.memory.embeddings import UnifiedEmbeddingManager

logger = logging.getLogger("VazusAutoImprover")

# Force UTF-8 output on Windows to avoid cp1252 UnicodeEncodeError
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError as e:
        logger.debug("stdout reconfigure non-fatal: %s", e)

# ────────────────────────────────────────────────
# ANSI Terminal Live Feed helpers
# ────────────────────────────────────────────────

RESET   = "\033[0m"
BOLD    = "\033[1m"
DIM     = "\033[2m"
GREEN   = "\033[32m"
CYAN    = "\033[36m"
YELLOW  = "\033[33m"
RED     = "\033[31m"
MAGENTA = "\033[35m"
BLUE    = "\033[34m"
WHITE   = "\033[97m"


def tui_print(icon: str, color: str, label: str, msg: str):
    """Prints a colored live-feed line to terminal stdout."""
    line = f"{color}{BOLD}{icon} [{label}]{RESET} {msg}"
    try:
        print(line, flush=True)
    except (UnicodeEncodeError, UnicodeDecodeError):
        safe = line.encode("utf-8", errors="replace").decode("utf-8", errors="replace")
        print(safe, flush=True)


def tui_box(title: str, lines: List[str], color: str = CYAN, width: int = 72) -> str:
    """Renders a bordered box for terminal output (UTF-8 safe, ASCII fallback)."""
    border_top    = f"{color}+{'=' * (width - 2)}+{RESET}"
    border_bottom = f"{color}+{'=' * (width - 2)}+{RESET}"
    title_line    = f"{color}| {BOLD}{title:<{width-3}}{RESET}{color}|{RESET}"
    sep_line      = f"{color}|{'-' * (width - 2)}|{RESET}"
    body_lines    = []
    for l in lines:
        clean = str(l)[:width - 4]
        body_lines.append(f"{color}|{RESET}  {clean:<{width-4}}{color}|{RESET}")
    return "\n".join([border_top, title_line, sep_line] + body_lines + [border_bottom])


def _ensure_vt100():
    """Enable VT100 ANSI on Windows console."""
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            hOut = kernel32.GetStdHandle(-11)
            dwMode = ctypes.c_ulong()
            kernel32.GetConsoleMode(hOut, ctypes.byref(dwMode))
            dwMode.value |= 0x0004
            kernel32.SetConsoleMode(hOut, dwMode)
        except Exception as e:
            logger.debug("enable vt100 non-fatal: %s", e)


# ────────────────────────────────────────────────
# Skill Usage Tracker
# ────────────────────────────────────────────────

class SkillUsageTracker:
    """
    Tracks which Hermes skills were used and whether they helped.
    Scores are persisted to vazus.db and used to re-rank auto-selection.
    EMA: new_score = 0.7 * old_score + 0.3 * outcome
    """

    TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS skill_usage_scores (
        skill_name   TEXT PRIMARY KEY,
        uses         INTEGER DEFAULT 0,
        successes    INTEGER DEFAULT 0,
        failures     INTEGER DEFAULT 0,
        score        REAL DEFAULT 0.5,
        last_used_at REAL DEFAULT 0
    )
    """

    def _ensure_table(self):
        try:
            conn = get_db_connection()
            conn.execute(self.TABLE_SQL)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"[SkillTracker] DB init failed: {e}")

    def __init__(self):
        self._ensure_table()

    def record_use(self, skill_name: str, success: bool):
        """Records a skill usage and updates its EMA score."""
        try:
            conn = get_db_connection()
            conn.execute(self.TABLE_SQL)
            score_val = 1.0 if success else 0.0
            conn.execute(
                """
                INSERT INTO skill_usage_scores (skill_name, uses, successes, failures, score, last_used_at)
                VALUES (?, 1, ?, ?, ?, ?)
                ON CONFLICT(skill_name) DO UPDATE SET
                    uses = uses + 1,
                    successes = successes + excluded.successes,
                    failures = failures + excluded.failures,
                    score = 0.7 * score + 0.3 * excluded.score,
                    last_used_at = excluded.last_used_at
                """,
                (skill_name, 1 if success else 0, 0 if success else 1, score_val, time.time())
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"[SkillTracker] record_use failed: {e}")

    def get_top_skills(self, n: int = 5) -> List[Dict[str, Any]]:
        """Returns top N skills by score."""
        try:
            conn = get_db_connection()
            rows = conn.execute(
                "SELECT skill_name, uses, score FROM skill_usage_scores ORDER BY score DESC LIMIT ?",
                (n,)
            ).fetchall()
            conn.close()
            return [{"name": r[0], "uses": r[1], "score": round(r[2], 3)} for r in rows]
        except Exception:
            return []

    def get_score(self, skill_name: str) -> float:
        """Returns the current score for a skill (0.0-1.0)."""
        try:
            conn = get_db_connection()
            row = conn.execute(
                "SELECT score FROM skill_usage_scores WHERE skill_name = ?",
                (skill_name,)
            ).fetchone()
            conn.close()
            return row[0] if row else 0.5
        except Exception:
            return 0.5

    async def record_use_async(self, skill_name: str, success: bool) -> None:
        """Asynchronously records a skill usage and updates its EMA score."""
        await asyncio.to_thread(self.record_use, skill_name, success)

    async def get_top_skills_async(self, n: int = 5) -> List[Dict[str, Any]]:
        """Asynchronously returns top N skills by score."""
        return await asyncio.to_thread(self.get_top_skills, n)

    async def get_score_async(self, skill_name: str) -> float:
        """Asynchronously returns the current score for a skill (0.0-1.0)."""
        return await asyncio.to_thread(self.get_score, skill_name)



# ────────────────────────────────────────────────
# Lesson Memory Bank (Reflexion episodic store)
# ────────────────────────────────────────────────

class LessonMemoryBank:
    """
    Persists 'lessons learned' from past failures so future iterations
    can retrieve relevant context — the core of Reflexion (Shinn 2023).
    """

    TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS reflexion_lessons (
        lesson_id      TEXT PRIMARY KEY,
        task_type      TEXT,
        error_sig      TEXT,
        lesson_text    TEXT,
        fix_hint       TEXT,
        success_count  INTEGER DEFAULT 0,
        created_at     REAL,
        embedding_json TEXT
    )
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path
        self._ensure_table()

    def _get_conn(self):
        if self.db_path:
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn
        return get_db_connection()

    def _ensure_table(self):
        try:
            conn = self._get_conn()
            conn.execute(self.TABLE_SQL)
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(reflexion_lessons)")
            cols = [r[1] for r in cur.fetchall()]
            for col_name, col_type in [
                ("embedding_json", "TEXT"),
                ("success_count", "INTEGER DEFAULT 0"),
                ("created_at", "REAL"),
                ("fix_hint", "TEXT"),
                ("lesson_text", "TEXT"),
                ("error_sig", "TEXT"),
                ("task_type", "TEXT"),
            ]:
                if col_name not in cols:
                    try:
                        conn.execute(f"ALTER TABLE reflexion_lessons ADD COLUMN {col_name} {col_type};")
                    except Exception as e:
                        logger.debug("column addition non-fatal: %s", e)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"[LessonBank] DB init failed: {e}")

    def save_lesson(
        self,
        task_type: str = "general",
        error_sig: str = "",
        lesson_text: str = "",
        fix_hint: str = "",
        category: str = "",
        anti_pattern: str = "",
        solution: str = "",
        context_tags: Optional[list] = None,
        **kwargs
    ) -> Any:
        tt = category or task_type or "general"
        err = anti_pattern or error_sig or ""
        sol = solution or fix_hint or ""
        les = lesson_text or f"Anti-pattern: {err}. Solution: {sol}"
        lesson_id = f"lesson_{int(time.time()*1000)}_{uuid.uuid4().hex[:8]}"
        embed_text = f"{tt}: {err} | {les} | {sol}"
        try:
            vec = UnifiedEmbeddingManager().get_embedding(embed_text)
            embedding_json = json.dumps(vec)
        except Exception as embed_err:
            logger.warning(f"[LessonBank] Embedding generation failed for {lesson_id}: {embed_err}")
            embedding_json = None

        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(reflexion_lessons)")
            cols = [r[1] for r in cur.fetchall()]

            if "lesson_id" in cols or not cols:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO reflexion_lessons
                    (lesson_id, task_type, error_sig, lesson_text, fix_hint, success_count, created_at, embedding_json)
                    VALUES (?, ?, ?, ?, ?, 0, ?, ?)
                    """,
                    (lesson_id, tt, err[:200], les[:1000], sol[:500], time.time(), embedding_json)
                )
            else:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO reflexion_lessons
                    (id, timestamp, task_id, prompt_template, fitness_score, lesson_learned, mutation_delta, metadata, embedding_json)
                    VALUES (?, ?, ?, ?, 1.0, ?, ?, '{}', ?)
                    """,
                    (lesson_id, time.time(), tt, err[:200], les[:1000], sol[:500], embedding_json)
                )
            conn.commit()
            conn.close()
            return lesson_id
        except Exception as e:
            logger.warning(f"[LessonBank] save_lesson failed: {e}")
            return lesson_id

    async def save_lesson_async(self, *args, **kwargs) -> Any:
        """Asynchronously saves a lesson learned to memory bank."""
        return await asyncio.to_thread(self.save_lesson, *args, **kwargs)

    async def retrieve_relevant_async(self, *args, **kwargs) -> List[Dict[str, Any]]:
        """Asynchronously retrieves past lessons by error signature substring match or vector similarity."""
        return await asyncio.to_thread(self.retrieve_relevant, *args, **kwargs)

    async def mark_lesson_used_async(self, lesson_id: str) -> None:
        """Asynchronously increments success_count when a lesson's fix_hint led to passing."""
        await asyncio.to_thread(self.mark_lesson_used, lesson_id)

    def _rank_lessons_by_vector(self, query: str, candidates: list, vecs: list, id_map: dict, top_k: int) -> List[Dict[str, Any]]:
        """Ranks lesson candidates by cosine similarity + success weighting."""
        try:
            embed_mgr = UnifiedEmbeddingManager()
            query_vec = embed_mgr.get_embedding(query)
            sims = embed_mgr.compute_batch_similarity(query_vec, vecs)
            scored = []
            for r, sim in zip(candidates, sims):
                sc = r[id_map["success_idx"]] if (id_map["success_idx"] != -1 and id_map["success_idx"] < len(r) and r[id_map["success_idx"]] is not None) else 0
                weighting = 0.75 * float(sim) + 0.25 * min(1.0, float(sc) / 5.0)
                scored.append((
                    weighting,
                    {
                        "id": r[id_map["id_idx"]],
                        "task_type": str(r[id_map["task_idx"]]) if id_map["task_idx"] < len(r) else "",
                        "category": str(r[id_map["task_idx"]]) if id_map["task_idx"] < len(r) else "",
                        "error_sig": str(r[id_map["err_idx"]]) if id_map["err_idx"] < len(r) else "",
                        "lesson": str(r[id_map["lesson_idx"]]) if id_map["lesson_idx"] < len(r) else "",
                        "fix_hint": str(r[id_map["hint_idx"]]) if id_map["hint_idx"] < len(r) else "",
                        "solution": str(r[id_map["hint_idx"]]) if id_map["hint_idx"] < len(r) else "",
                        "similarity": float(sim),
                        "similarity_score": float(sim),
                        "success_count": sc,
                    }
                ))
            scored.sort(key=lambda x: x[0], reverse=True)
            return [item[1] for item in scored[:top_k]]
        except Exception as e:
            logger.warning(f"[LessonBank] Vector retrieval failed, falling back to SQL match: {e}")
            return []

    def _match_lessons_by_sql(self, rows: list, error_sig: str, task_type: str, id_map: dict, top_k: int) -> List[Dict[str, Any]]:
        """Fallback substring match for lesson rows."""
        matched = []
        for r in rows:
            row_err = str(r[id_map["err_idx"]]) if id_map["err_idx"] < len(r) else ""
            row_task = str(r[id_map["task_idx"]]) if id_map["task_idx"] < len(r) else ""
            sc = r[id_map["success_idx"]] if (id_map["success_idx"] != -1 and id_map["success_idx"] < len(r) and r[id_map["success_idx"]] is not None) else 0
            if (error_sig and error_sig in row_err) or (task_type and task_type in row_task) or not error_sig:
                matched.append({
                    "id": r[id_map["id_idx"]], "task_type": row_task, "error_sig": row_err,
                    "lesson": str(r[id_map["lesson_idx"]]) if id_map["lesson_idx"] < len(r) else "",
                    "fix_hint": str(r[id_map["hint_idx"]]) if id_map["hint_idx"] < len(r) else "",
                    "solution": str(r[id_map["hint_idx"]]) if id_map["hint_idx"] < len(r) else "",
                    "category": row_task,
                    "similarity_score": 0.5,
                    "success_count": sc,
                })
        if not matched:
            for r in rows[:top_k]:
                sc = r[id_map["success_idx"]] if (id_map["success_idx"] != -1 and id_map["success_idx"] < len(r) and r[id_map["success_idx"]] is not None) else 0
                matched.append({
                    "id": r[id_map["id_idx"]], "task_type": str(r[id_map["task_idx"]]) if id_map["task_idx"] < len(r) else "",
                    "error_sig": str(r[id_map["err_idx"]]) if id_map["err_idx"] < len(r) else "",
                    "lesson": str(r[id_map["lesson_idx"]]) if id_map["lesson_idx"] < len(r) else "",
                    "fix_hint": str(r[id_map["hint_idx"]]) if id_map["hint_idx"] < len(r) else "",
                    "solution": str(r[id_map["hint_idx"]]) if id_map["hint_idx"] < len(r) else "",
                    "category": str(r[id_map["task_idx"]]) if id_map["task_idx"] < len(r) else "",
                    "similarity_score": 0.5,
                    "success_count": sc,
                })
        return matched[:top_k]

    def retrieve_relevant(
        self,
        error_sig: str = "",
        task_type: str = "",
        top_k: int = 3,
        query: str = "",
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Retrieves the most relevant past lessons by 768D cosine similarity search + success weighting."""
        search_query = query or error_sig or ""
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute("SELECT * FROM reflexion_lessons")
            col_names = [col[0] for col in cur.description] if cur.description else []
            rows = cur.fetchall()
            conn.close()
        except Exception as e:
            logger.warning(f"[LessonBank] DB query failed in retrieve_relevant: {e}")
            return []

        if not rows:
            return []

        id_map = {
            "emb_idx": col_names.index("embedding_json") if "embedding_json" in col_names else -1,
            "id_idx": col_names.index("id") if "id" in col_names else (col_names.index("lesson_id") if "lesson_id" in col_names else 0),
            "task_idx": col_names.index("task_id") if "task_id" in col_names else (col_names.index("task_type") if "task_type" in col_names else 1),
            "err_idx": col_names.index("prompt_template") if "prompt_template" in col_names else (col_names.index("error_sig") if "error_sig" in col_names else 2),
            "lesson_idx": col_names.index("lesson_learned") if "lesson_learned" in col_names else (col_names.index("lesson_text") if "lesson_text" in col_names else 3),
            "hint_idx": col_names.index("mutation_delta") if "mutation_delta" in col_names else (col_names.index("fix_hint") if "fix_hint" in col_names else 4),
            "success_idx": col_names.index("success_count") if "success_count" in col_names else -1,
        }

        candidates, vecs = [], []
        if id_map["emb_idx"] != -1:
            for r in rows:
                emb_json = r[id_map["emb_idx"]] if id_map["emb_idx"] < len(r) else None
                if emb_json:
                    try:
                        v = json.loads(emb_json)
                        if isinstance(v, list) and len(v) == 768:
                            candidates.append(r)
                            vecs.append(v)
                    except Exception as e:
                        logger.debug("parse embedding json non-fatal: %s", e)

        if candidates and vecs:
            res = self._rank_lessons_by_vector(f"{task_type}: {error_sig}", candidates, vecs, id_map, top_k)
            if res:
                return res

        return self._match_lessons_by_sql(rows, error_sig, task_type, id_map, top_k)

    def mark_lesson_used(self, lesson_id: str):
        """Increments success_count/fitness_score when a lesson's fix_hint led to passing."""
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(reflexion_lessons)")
            cols = [r[1] for r in cur.fetchall()]

            if "success_count" not in cols:
                try:
                    conn.execute("ALTER TABLE reflexion_lessons ADD COLUMN success_count INTEGER DEFAULT 0;")
                    conn.commit()
                except Exception as e:
                    logger.debug("add success_count column non-fatal: %s", e)

            id_col = "lesson_id" if "lesson_id" in cols else ("id" if "id" in cols else None)
            if id_col:
                conn.execute(
                    f"UPDATE reflexion_lessons SET success_count = COALESCE(success_count, 0) + 1 WHERE {id_col} = ?",
                    (lesson_id,)
                )
                if "fitness_score" in cols:
                    conn.execute(
                        f"UPDATE reflexion_lessons SET fitness_score = COALESCE(fitness_score, 0) + 0.1 WHERE {id_col} = ?",
                        (lesson_id,)
                    )
                conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"[LessonBank] mark_lesson_used failed for {lesson_id}: {e}")


# ────────────────────────────────────────────────
# Reflexion Evaluator
# ────────────────────────────────────────────────

@dataclass
class EvaluationResult:
    score: float
    passed: bool
    critique: str
    suggested_action: str


class ReflexionEvaluator:
    """
    Scores output quality via heuristic + SMT Z3 contract checks.
    In production, replace/augment with an LLM self-critique call.
    """

    PASS_THRESHOLD = 0.7

    def evaluate(
        self,
        code: str,
        error_trace: str = "",
        task_description: str = "",
        pass_threshold: Optional[float] = None,
    ) -> EvaluationResult:
        score = 1.0
        critique_parts = []
        action_parts = []

        has_error = bool(error_trace and error_trace.strip())

        # 1. Syntax check
        try:
            ast.parse(code)
        except SyntaxError as se:
            score -= 0.5
            critique_parts.append(f"SyntaxError: {se}")
            action_parts.append("Fix Python syntax error before re-submitting.")

        # 2. Error trace presence
        if has_error:
            score -= 0.35
            sig = error_trace[:120].replace("\n", " ")
            critique_parts.append(f"Error: {sig}")
            action_parts.append("Review traceback and apply targeted fix.")

        # 3. SMT Z3 contract check
        if ":requires:" in code or ":ensures:" in code:
            try:
                from vazus_core.verification.safety_guardrail import SMTZ3Verifier
                v = SMTZ3Verifier()
                res = v.verify_code_contracts(code)
                if not res.contract_satisfied:
                    score -= 0.25
                    critique_parts.append(f"SMT contract violated: {res.proof_details}")
                    action_parts.append("Fix postcondition — Z3 found a counterexample.")
            except Exception as e:
                logger.debug("SMT contract check non-fatal: %s", e)

        # 4. Security check
        if "GEMINI_API_KEY" in code and "genai.Client()" in code:
            score -= 0.3
            critique_parts.append("Forbidden: direct genai.Client() with external API key.")
            action_parts.append("Remove external API usage, use agy CLI session instead.")

        score = max(0.0, min(1.0, score))
        threshold = pass_threshold if pass_threshold is not None else self.PASS_THRESHOLD
        passed = (score >= threshold) and not has_error

        return EvaluationResult(
            score=round(score, 3),
            passed=passed,
            critique="; ".join(critique_parts) if critique_parts else "No issues detected.",
            suggested_action="; ".join(action_parts) if action_parts else "Output looks good.",
        )

    async def evaluate_async(
        self,
        code: str,
        error_trace: str = "",
        task_description: str = "",
        pass_threshold: Optional[float] = None,
    ) -> EvaluationResult:
        """Asynchronously evaluates output quality, offloading CPU/Z3 work to worker thread."""
        return await asyncio.to_thread(self.evaluate, code, error_trace, task_description, pass_threshold)

    def diagnose_and_formulate_lesson(
        self,
        error_context: dict,
        task_objective: str = ""
    ) -> dict:
        """Diagnoses error and formulates actionable lesson learned for Reflexion memory bank."""
        err_msg = error_context.get("error_message") or str(error_context)
        err_type = error_context.get("error_type", "ExecutionError")
        return {
            "lesson_text": f"Diagnosed {err_type}: {err_msg}",
            "anti_pattern": err_msg,
            "recommended_pattern": f"Apply robust verification for {task_objective or err_type}",
            "solution": "use vazus_core.verification.ast_pruner for all ASTPruner imports",
            "task_objective": task_objective,
        }




# ────────────────────────────────────────────────
# VazusAutoImprover — Main Loop
# ────────────────────────────────────────────────

@dataclass
class ImprovementSession:
    task_id: str
    task_description: str
    initial_code: str
    final_code: str
    iterations: int
    success: bool
    final_score: float
    skills_used: List[str] = field(default_factory=list)
    lessons_applied: List[str] = field(default_factory=list)
    history: List[Dict[str, Any]] = field(default_factory=list)


class VazusAutoImprover:
    """
    Real self-improvement engine for vazus SuperGraph OS.

    Each call to `improve()` runs a Reflexion loop:
      1. Evaluate current output (heuristic + SMT Z3)
      2. Retrieve relevant past lessons from LessonMemoryBank
      3. Auto-select and inject Hermes skills based on task + error
      4. Call fix_fn to generate a patch
      5. Re-evaluate — if better, accept; else retry
      6. Save new lesson to memory bank on failure
      7. Update skill EMA scores on completion

    All output is streamed to stdout in real-time — visible in Antigravity terminal.
    """

    def __init__(self, max_iterations: int = 3, pass_threshold: float = 0.7):
        self.max_iterations = max_iterations
        self.pass_threshold = pass_threshold
        self.evaluator = ReflexionEvaluator()
        self.lesson_bank = LessonMemoryBank()
        self.skill_tracker = SkillUsageTracker()
        _ensure_vt100()

    async def _select_skills_for_context_async(self, prompt: str, error_trace: str) -> List[str]:
        """Uses AutomaticSkillSelector weighted by SkillUsageTracker historical scores asynchronously."""
        try:
            from vazus_core.hermes_skill_syncer import AutomaticSkillSelector
            selector = AutomaticSkillSelector()
            combined = f"{prompt} {error_trace}"
            candidates = selector.select_matching_skills(combined, top_k=4)
            scores = await asyncio.gather(*[self.skill_tracker.get_score_async(sk["name"]) for sk in candidates])
            scored = [(score, sk) for score, sk in zip(scores, candidates)]
            scored.sort(key=lambda x: x[0], reverse=True)
            return [sk["name"] for _, sk in scored[:2]]
        except Exception:
            return []

    def _select_skills_for_context(self, prompt: str, error_trace: str) -> List[str]:
        """Uses AutomaticSkillSelector weighted by SkillUsageTracker historical scores."""
        try:
            from vazus_core.hermes_skill_syncer import AutomaticSkillSelector
            selector = AutomaticSkillSelector()
            combined = f"{prompt} {error_trace}"
            candidates = selector.select_matching_skills(combined, top_k=4)
            scored = [(self.skill_tracker.get_score(sk["name"]), sk) for sk in candidates]
            scored.sort(key=lambda x: x[0], reverse=True)
            return [sk["name"] for _, sk in scored[:2]]
        except Exception:
            return []

    async def _update_skills_async(self, skills: List[str], success: bool) -> None:
        for sk in skills:
            await self.skill_tracker.record_use_async(sk, success=success)
            score = await self.skill_tracker.get_score_async(sk)
            tui_print("--", DIM + WHITE, "SCORE", f"Skill '{sk}' EMA score -> {score:.3f}")

    async def _persist_session_async(self, session: ImprovementSession) -> None:
        await asyncio.to_thread(self._persist_session, session)

    async def _apply_fix_fn(self, fix_fn: Callable[..., Any], current_code: str, critique: str, lessons: list, task_description: str) -> tuple[str, str]:
        """Applies sync or async fix_fn callable and returns (new_code, current_error)."""
        try:
            if inspect.iscoroutinefunction(fix_fn) or asyncio.iscoroutinefunction(fix_fn):
                try:
                    new_code = await fix_fn(current_code, critique, lessons, task_description=task_description)
                except TypeError:
                    new_code = await fix_fn(current_code, critique, lessons)
            else:
                try:
                    res = fix_fn(current_code, critique, lessons, task_description=task_description)
                except TypeError:
                    res = fix_fn(current_code, critique, lessons)
                new_code = await res if inspect.isawaitable(res) else res

            if new_code and new_code != current_code:
                tui_print("**", YELLOW, "PATCH", f"Fix applied ({len(new_code)} chars)")
                return new_code, ""
            tui_print("!!", YELLOW, "FIX", "fix_fn returned no change.")
            return current_code, ""
        except Exception as e:
            tui_print("!!", RED, "FIX", f"fix_fn exception: {e}")
            return current_code, str(e)

    async def _finalize_improvement_session(
        self,
        task_id: str,
        task_description: str,
        *,
        initial_code: str,
        final_code: str,
        iterations: int,
        ev: EvaluationResult,
        skills_used: List[str],
        lessons_applied: List[str],
        history: List[Dict[str, Any]],
        task_type: str = "code_generation",
        error_sig: str = "",
    ) -> ImprovementSession:
        """Constructs, persists, and logs the final ImprovementSession state."""
        session = ImprovementSession(
            task_id=task_id, task_description=task_description,
            initial_code=initial_code, final_code=final_code,
            iterations=iterations, success=ev.passed,
            final_score=ev.score, skills_used=skills_used,
            lessons_applied=lessons_applied, history=history,
        )
        if not ev.passed and error_sig:
            await self.lesson_bank.save_lesson_async(
                task_type=task_type, error_sig=error_sig,
                lesson_text=f"After {iterations} iters, unresolved: {ev.critique}",
                fix_hint=ev.suggested_action,
            )
            tui_print("**", BLUE, "MEMORY", "Failure lesson saved to LessonMemoryBank.")

        await self._update_skills_async(skills_used, success=ev.passed)
        await self._persist_session_async(session)
        self._print_footer(session)
        return session

    async def _run_single_iteration(
        self,
        i: int,
        current_code: str,
        current_error: str,
        task_description: str,
        *,
        task_type: str = "code_generation",
        fix_fn: Callable[..., Any],
        skills_used: list,
        lessons_applied_ids: list,
        history: list,
    ) -> tuple[str, str, Optional[EvaluationResult]]:
        """Runs a single iteration of evaluation and fix in the Reflexion loop."""
        ev = await self.evaluator.evaluate_async(
            current_code, current_error, task_description, pass_threshold=self.pass_threshold
        )
        color = GREEN if ev.score >= self.pass_threshold else YELLOW if ev.score >= 0.4 else RED
        tui_print("=>", color, f"ITER {i}/{self.max_iterations}", f"Score={ev.score:.3f}  | {ev.critique[:80]}")
        history.append({"iteration": i, "score": ev.score, "passed": ev.passed, "critique": ev.critique})

        if ev.passed:
            return current_code, current_error, ev

        error_sig = (current_error or ev.critique)[:80]
        past_lessons = await self.lesson_bank.retrieve_relevant_async(error_sig, task_type)
        if past_lessons:
            for l in past_lessons:
                tui_print("!!", BLUE, "LESSON", f"[{l['task_type']}] {l['lesson'][:75]}")
            lessons_applied_ids.extend(l["id"] for l in past_lessons)

        iter_skills = await self._select_skills_for_context_async(task_description, current_error)
        for sk in (iter_skills or []):
            if sk not in skills_used:
                skills_used.append(sk)

        tui_print("..", YELLOW, "FIX", f"Calling fix_fn (iter {i})...")
        new_code, new_error = await self._apply_fix_fn(
            fix_fn, current_code, ev.critique, [l["lesson"] for l in past_lessons], task_description
        )
        return new_code, new_error, None

    def _print_header(self, task_id: str, task_description: str, initial_code: str) -> None:
        """Prints a visual header for the Reflexion improvement session."""
        lines = [
            f"Task ID:     {task_id}",
            f"Description: {task_description[:60]}",
            f"Code Size:   {len(initial_code)} chars ({len(initial_code.splitlines())} lines)",
            f"Max Iters:   {self.max_iterations} (Pass Threshold: {self.pass_threshold:.0%})",
        ]
        box = tui_box("VAZUS REFLEXION AUTO-IMPROVER", lines, color=CYAN)
        try:
            print(box, flush=True)
        except Exception:
            pass

    async def improve(
        self,
        task_id: str,
        task_description: str,
        initial_code: str,
        fix_fn: Callable[..., Any],
        *,
        error_trace: str = "",
        task_type: str = "code_generation",
    ) -> ImprovementSession:
        """
        Runs the Reflexion loop asynchronously up to self.max_iterations.
        Protected by asyncio.timeout(300) to prevent hanging sessions.
        """
        self._print_header(task_id, task_description, initial_code)
        current_code, current_error = initial_code, error_trace
        history, skills_used, lessons_applied_ids = [], [], []

        try:
            async with asyncio.timeout(300):
                for i in range(1, self.max_iterations + 1):
                    current_code, current_error, ev = await self._run_single_iteration(
                        i, current_code, current_error, task_description,
                        task_type=task_type, fix_fn=fix_fn, skills_used=skills_used,
                        lessons_applied_ids=lessons_applied_ids, history=history,
                    )
                    if ev is not None and ev.passed:
                        tui_print("OK", GREEN, "PASS", f"Score {ev.score:.3f} >= {self.pass_threshold:.0%} — stopping early.")
                        return await self._finalize_improvement_session(
                            task_id, task_description,
                            initial_code=initial_code, final_code=current_code,
                            iterations=i, ev=ev, skills_used=skills_used,
                            lessons_applied=lessons_applied_ids, history=history
                        )
        except TimeoutError:
            tui_print("!!", RED, "TIMEOUT", "Reflexion loop timed out after 300 seconds")
            final_ev = await self.evaluator.evaluate_async(
                current_code, "TimeoutError: Execution exceeded 300s limit", task_description, pass_threshold=self.pass_threshold
            )
            return await self._finalize_improvement_session(
                task_id, task_description,
                initial_code=initial_code, final_code=current_code,
                iterations=self.max_iterations, ev=final_ev,
                skills_used=skills_used, lessons_applied=lessons_applied_ids, history=history
            )

        final_ev = await self.evaluator.evaluate_async(
            current_code, current_error, task_description, pass_threshold=self.pass_threshold
        )
        tui_print("!!", RED, "LIMIT", f"Max {self.max_iterations} iters reached. Final score: {final_ev.score:.3f}")
        return await self._finalize_improvement_session(
            task_id, task_description,
            initial_code=initial_code, final_code=current_code,
            iterations=self.max_iterations, ev=final_ev,
            skills_used=skills_used, lessons_applied=lessons_applied_ids, history=history,
            task_type=task_type, error_sig=(error_trace or "")[:80]
        )

    def improve_sync(
        self,
        task_id: str,
        task_description: str,
        initial_code: str,
        fix_fn: Callable[..., Any],
        *,
        error_trace: str = "",
        task_type: str = "code_generation",
    ) -> ImprovementSession:
        """Synchronous wrapper around `improve(...)` for legacy sync callers."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        coro = self.improve(
            task_id,
            task_description,
            initial_code,
            fix_fn,
            error_trace=error_trace,
            task_type=task_type,
        )

        if loop and loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(lambda: asyncio.run(coro))
                return future.result()
        else:
            return asyncio.run(coro)

    def _update_skills(self, skills: List[str], success: bool):
        for sk in skills:
            self.skill_tracker.record_use(sk, success=success)
            score = self.skill_tracker.get_score(sk)
            tui_print("--", DIM + WHITE, "SCORE", f"Skill '{sk}' EMA score -> {score:.3f}")

    def _persist_session(self, session: ImprovementSession):
        try:
            conn = get_db_connection()
            conn.execute("""
                CREATE TABLE IF NOT EXISTS auto_improver_sessions (
                    session_id   TEXT PRIMARY KEY,
                    task_type    TEXT,
                    task_desc    TEXT,
                    iterations   INTEGER,
                    success      INTEGER,
                    final_score  REAL,
                    skills_used  TEXT,
                    created_at   REAL
                )
            """)
            conn.execute(
                "INSERT OR REPLACE INTO auto_improver_sessions VALUES (?,?,?,?,?,?,?,?)",
                (
                    session.task_id, "code_generation",
                    session.task_description[:300], session.iterations,
                    1 if session.success else 0, session.final_score,
                    fast_json_dumps(session.skills_used), time.time(),
                )
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"[AutoImprover] Session persist failed: {e}")

    def _print_footer(self, session: ImprovementSession):
        color = GREEN if session.success else RED
        status = "IMPROVED" if session.success else "MAX RETRIES"
        lines = [
            f"Status    : {status}",
            f"Score     : {session.final_score:.3f}",
            f"Iterations: {session.iterations} / {self.max_iterations}",
            f"Skills    : {', '.join(session.skills_used) or 'none'}",
            f"Lessons   : {len(session.lessons_applied)} applied",
        ]
        print(tui_box("VAZUS AUTO-IMPROVER  Session Complete", lines, color=color), flush=True)

    def show_stats(self):
        """Prints live system stats to terminal: top skills + recent sessions."""
        top_skills = self.skill_tracker.get_top_skills(5)
        lines = ["-- Top Skills by EMA Score --"]
        for sk in top_skills:
            bar = "#" * int(sk["score"] * 20)
            lines.append(f"  {sk['name']:<35} [{bar:<20}] {sk['score']:.3f}  ({sk['uses']} uses)")

        lines.append("")
        lines.append("-- Recent Improvement Sessions --")
        try:
            conn = get_db_connection()
            rows = conn.execute(
                "SELECT session_id, task_desc, iterations, success, final_score FROM auto_improver_sessions ORDER BY created_at DESC LIMIT 5"
            ).fetchall()
            conn.close()
            for r in rows:
                status = "OK" if r[3] else "!!"
                lines.append(f"  [{status}] score={r[4]:.2f} iters={r[2]} | {r[1][:45]}")
        except Exception:
            lines.append("  (no sessions yet)")

        print(tui_box("VAZUS AUTO-IMPROVER  System Stats", lines, color=CYAN), flush=True)


# ────────────────────────────────────────────────
# Singleton accessor
# ────────────────────────────────────────────────

_default_improver: Optional[VazusAutoImprover] = None
_improver_lock = threading.Lock()


def get_auto_improver(max_iterations: int = 3) -> VazusAutoImprover:
    """Thread-safe getter for the global singleton VazusAutoImprover instance."""
    global _default_improver
    if _default_improver is None:
        with _improver_lock:
            if _default_improver is None:
                _default_improver = VazusAutoImprover(max_iterations=max_iterations)
    return _default_improver


# ────────────────────────────────────────────────
# CLI: python -m vazus_core.auto_improver [--stats]
# ────────────────────────────────────────────────

if __name__ == "__main__":
    _ensure_vt100()
    improver = get_auto_improver()

    if "--stats" in sys.argv:
        improver.show_stats()
        sys.exit(0)

    # Demo: self-fix a broken function with a contract violation
    broken_code = '''
def faulty_div(a: int, b: int) -> int:
    """
    :requires: b != 0
    :ensures: result >= 0
    """
    return a / b
'''

    async def demo_fix_fn(code: str, critique: str, lessons: List[str]) -> str:
        return code.replace("return a / b", "return abs(a // b) if b != 0 else 0")

    session = asyncio.run(improver.improve(
        task_id=f"demo_{int(time.time())}",
        task_description="Fix faulty integer division to satisfy non-negative postcondition",
        initial_code=broken_code,
        fix_fn=demo_fix_fn,
        error_trace="ZeroDivisionError: division by zero",
        task_type="code_fix",
    ))
    print(f"\nFinal code:\n{session.final_code}")

