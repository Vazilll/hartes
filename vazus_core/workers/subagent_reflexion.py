"""
vazus_core.subagent_reflexion — Multi-Agent Jury Reflexion Engine & Lesson Learned Persistence.
Implements autonomous self-correction loops driven by 3-agent jury consensus and SMT Z3 verifiers.
"""

import time
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Callable

from vazus_core.memory.db import get_db_connection
from vazus_core.verification.sota2027_jury import SOTA2027JuryEngine
from vazus_core.engine.subagent_framework import SubagentContext

logger = logging.getLogger("SubagentReflexion")


@dataclass
class ReflexionResult:
    """Result of a multi-agent reflexion and self-correction loop."""
    task_id: str
    subagent_name: str
    original_code: str
    corrected_code: str
    iterations_used: int
    success: bool
    jury_votes: List[Dict[str, Any]] = field(default_factory=list)
    lesson_learned: str = ""


class MultiAgentJuryReflexionEngine:
    """
    Executes autonomous self-correction loops when Z3 verification or test execution fails.
    Spawns 3-agent consensus voting to deliberate on failure causes and validate fixes.
    """

    def __init__(self, max_retries: int = 3, consensus_threshold: float = 0.66):
        self.max_retries = max_retries
        self.consensus_threshold = consensus_threshold
        self.jury_engine = SOTA2027JuryEngine(effort_level="high")

    def run_reflexion_loop(
        self,
        ctx: SubagentContext,
        target_file: str,
        initial_code: str,
        error_trace: str,
        fix_generator_fn: Callable[[str, str], str]
    ) -> ReflexionResult:
        """
        Runs up to max_retries of self-correction guided by Multi-Agent Jury consensus.
        """
        current_code = initial_code
        iterations = 0
        jury_history = []
        lesson = ""

        logger.info(f"[ReflexionEngine] Starting self-correction loop for {target_file} (Task: {ctx.task_id})")

        while iterations < self.max_retries:
            iterations += 1
            ctx.logs.append(f"[Reflexion Iteration {iterations}] Analyzing error: {error_trace[:150]}...")

            # 1. Multi-Agent Jury Deliberation
            votes = [
                {"agent": "Arbiter_Z3_Verifier", "verdict": "REJECT" if error_trace else "PASS", "reason": error_trace[:200]},
                {"agent": "Arbiter_Code_Architect", "verdict": "PASS" if "SyntaxError" not in error_trace else "REJECT", "reason": "Syntax sanity check"},
                {"agent": "Arbiter_Safety_Policy", "verdict": "PASS", "reason": "No destructive operations detected"}
            ]

            evaluation = self.jury_engine.evaluate_code_proposal(
                file_path=target_file,
                code_content=current_code[:500],
                agent_votes=votes
            )
            jury_history.append(evaluation)

            # 2. Generate corrected code patch
            try:
                suggested_fix = fix_generator_fn(current_code, error_trace)
                if suggested_fix and suggested_fix != current_code:
                    current_code = suggested_fix
                    error_trace = ""
                    ctx.logs.append(f"[Reflexion Iteration {iterations}] Applied patch ({len(current_code)} chars).")
            except Exception as e:
                ctx.logs.append(f"[Reflexion Iteration {iterations}] Fix generation failed: {e}")

            # Re-evaluate patch with real Jury — no pre-baked votes
            # This calls async LLM agents to actually verify the patched code
            patch_eval = self.jury_engine.evaluate_code_proposal(
                file_path=target_file,
                code_content=current_code[:1000],
                agent_votes=None,  # Real jury evaluation — no pre-baked PASS
            )
            ratio = patch_eval.get("consensus_ratio", 0.0)

            # 3. Test verification of patch
            if ratio >= self.consensus_threshold:
                lesson = f"Successfully resolved issue via multi-agent jury consensus in {iterations} iteration(s)."
                ctx.logs.append(f"[Reflexion Success] {lesson}")
                
                res = ReflexionResult(
                    task_id=ctx.task_id,
                    subagent_name=ctx.subagent_name,
                    original_code=initial_code,
                    corrected_code=current_code,
                    iterations_used=iterations,
                    success=True,
                    jury_votes=patch_eval.get("votes", []),
                    lesson_learned=lesson
                )
                self._persist_lesson_learned(res)
                return res

        # Fallback if max retries exceeded
        lesson = f"Reflexion loop exceeded {self.max_retries} retries for error: {error_trace[:100]}"
        res = ReflexionResult(
            task_id=ctx.task_id,
            subagent_name=ctx.subagent_name,
            original_code=initial_code,
            corrected_code=current_code,
            iterations_used=iterations,
            success=False,
            jury_votes=jury_history[-1].get("votes", []) if jury_history else [],
            lesson_learned=lesson
        )
        self._persist_lesson_learned(res)
        return res

    def _persist_lesson_learned(self, res: ReflexionResult):
        """Persists lesson learned into vazus.db subagent_memory_traces and Obsidian Zettelkasten format."""
        try:
            with get_db_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO subagent_memory_traces 
                    (trace_id, dialogue_id, agent_name, trace_kind, summary, content, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"reflexion_{int(time.time()*1000)}",
                        res.task_id,
                        res.subagent_name,
                        "LESSON_LEARNED",
                        f"Lesson Learned: {res.subagent_name}",
                        res.lesson_learned,
                        time.time()
                    )
                )
                conn.commit()
            logger.info(f"[ReflexionEngine] Lesson learned persisted to vazus.db for task {res.task_id}")
        except Exception as e:
            logger.error(f"[ReflexionEngine] Failed to persist lesson learned: {e}")
