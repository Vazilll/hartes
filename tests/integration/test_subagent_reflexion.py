"""
tests/test_subagent_reflexion.py — Unit tests for vazus_core.subagent_reflexion module.
"""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest
from vazus_core.subagent_framework import SubagentContext
from vazus_core.subagent_reflexion import MultiAgentJuryReflexionEngine, ReflexionResult
from vazus_core.auto_improver import VazusAutoImprover


_APPROVED_JURY_RESULT = {
    "approved": True,
    "consensus_ratio": 1.0,
    "votes": [
        {"agent": "Planner", "approved": True, "verdict": "PASS", "reason": "OK"},
        {"agent": "RLM_Coder", "approved": True, "verdict": "PASS", "reason": "OK"},
        {"agent": "Verifier_Worker", "approved": True, "verdict": "PASS", "reason": "OK"},
    ],
    "fixation_ready": True,
    "smt_verification": {"contract_satisfied": True, "status": "UNSAT"},
    "ast_error": None,
    "effort_level": "high",
}


def test_multi_agent_jury_reflexion_success():
    engine = MultiAgentJuryReflexionEngine(max_retries=2)
    ctx = SubagentContext(
        subagent_name="test_worker",
        task_id="task_reflexion_test",
        prompt="Fix division by zero bug"
    )

    def mock_fix_generator(code: str, error: str) -> str:
        return code.replace("return a / b", "return a / b if b != 0 else 0.0")

    initial_code = "def divide(a, b): return a / b"
    error_trace = "ZeroDivisionError: division by zero"

    engine = MultiAgentJuryReflexionEngine(max_retries=2)
    # Fail-closed jury contract: real LLM votes would abstain in test mode,
    # so stub the jury engine directly — this test verifies the REFLEXION
    # loop logic, not the jury itself (see test_concordia_jury_fail_closed_*).
    engine.jury_engine.evaluate_code_proposal = lambda *a, **k: _APPROVED_JURY_RESULT
    res = engine.run_reflexion_loop(
            ctx=ctx,
            target_file="math_utils.py",
            initial_code=initial_code,
            error_trace=error_trace,
            fix_generator_fn=mock_fix_generator
        )

    assert isinstance(res, ReflexionResult)
    assert res.success is True
    assert res.iterations_used == 1
    assert "if b != 0" in res.corrected_code
    assert "Lesson Learned" in res.lesson_learned or "Successfully resolved" in res.lesson_learned


def test_vazus_auto_improver_async_and_sync_fix_fn():
    """Verify VazusAutoImprover accepts both coroutine and sync fix_fn callbacks."""
    async def _test():
        improver = VazusAutoImprover(max_iterations=2, pass_threshold=0.8)

        # 1. Test with async def fix_fn
        async def async_fix(code, critique, lessons):
            return code.replace("return a / b", "return a / b if b != 0 else 0.0")

        sess_async = await improver.improve(
            task_id="test_async_fix",
            task_description="Fix division by zero with async fix_fn",
            initial_code="def divide(a, b): return a / b",
            fix_fn=async_fix,
            error_trace="ZeroDivisionError"
        )
        assert sess_async.success is True
        assert "if b != 0" in sess_async.final_code

        # 2. Test with standard def fix_fn
        def sync_fix(code, critique, lessons):
            return code.replace("return a / b", "return a / b if b != 0 else 0.0")

        sess_sync = await improver.improve(
            task_id="test_sync_fix",
            task_description="Fix division by zero with sync fix_fn",
            initial_code="def divide(a, b): return a / b",
            fix_fn=sync_fix,
            error_trace="ZeroDivisionError"
        )
        assert sess_sync.success is True
        assert "if b != 0" in sess_sync.final_code

    asyncio.run(_test())

