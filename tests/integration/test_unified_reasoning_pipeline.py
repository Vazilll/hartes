"""
Unit tests for vazus_core.unified_reasoning_pipeline and vazus_core.model_selector.
Verifies asyncio-native execution, timeout handling (asyncio.timeout), Z3 thread offloading,
synchronous backward compatibility wrappers, and async model configuration.
"""

import asyncio
import time
import pytest
import os
from unittest.mock import patch, MagicMock

from vazus_core.unified_reasoning_pipeline import UnifiedReasoningPipeline
from vazus_core.model_selector import ModelSelector


VALID_CODE_PROPOSAL = """
def safe_add(a: int, b: int) -> int:
    \"\"\"
    Add two non-negative integers.
    :requires: a >= 0
    :requires: b >= 0
    :ensures: result >= 0
    \"\"\"
    return a + b
"""

INVALID_CODE_PROPOSAL = """
def faulty_sub(a: int, b: int) -> int:
    \"\"\"
    Faulty subtraction claiming result >= 0 for non-negative inputs.
    :requires: a >= 0
    :requires: b >= 0
    :ensures: result >= 0
    \"\"\"
    return a - b
"""


def test_async_execute_pipeline_success():
    """Verify async execute_pipeline returns correct structure and approves valid code."""
    async def _test():
        pipeline = UnifiedReasoningPipeline(effort_level="high")
        res = await pipeline.execute_pipeline(
            task_prompt="Optimize safe_add function",
            code_proposal=VALID_CODE_PROPOSAL,
            file_path="safe_add.py",
            agent_votes=[
                {"agent": "Planner", "approved": True, "verdict": "PASS", "reason": "OK"},
                {"agent": "RLM_Coder", "approved": True, "verdict": "PASS", "reason": "OK"},
                {"agent": "Verifier_Worker", "approved": False, "verdict": "FAIL", "reason": "Nitpick"},
            ],
        )

        assert isinstance(res, dict)
        assert res["status"] == "APPROVED"
        assert res["approved"] is True
        assert res["effort_level"] == "high"
        assert "ast_stats" in res
        assert "smt_verification" in res
        assert "jury_result" in res
        assert "pipeline_log" in res
        assert "laconic_summary" in res
        assert "APPROVED" in res["laconic_summary"]

    asyncio.run(_test())


def test_async_execute_pipeline_rejected_by_smt():
    """Verify async execute_pipeline rejects code violating SMT Z3 contract."""
    async def _test():
        pipeline = UnifiedReasoningPipeline(effort_level="high")
        res = await pipeline.execute_pipeline(
            task_prompt="Verify faulty_sub function",
            code_proposal=INVALID_CODE_PROPOSAL,
            file_path="faulty_sub.py"
        )

        assert isinstance(res, dict)
        assert res["status"] == "REJECTED"
        assert res["approved"] is False

    asyncio.run(_test())


def test_async_execute_pipeline_timeout_handling():
    """Verify execute_pipeline handles timeout via asyncio.timeout(timeout)."""
    async def _test():
        pipeline = UnifiedReasoningPipeline(effort_level="high")

        def slow_verify(*args, **kwargs):
            time.sleep(0.3)
            return {"contract_satisfied": True}

        with patch.object(pipeline.smt_verifier, "verify_code_contracts", side_effect=slow_verify):
            res = await pipeline.execute_pipeline(
                task_prompt="Slow verification task",
                code_proposal=VALID_CODE_PROPOSAL,
                file_path="slow.py",
                timeout=0.05
            )

            assert isinstance(res, dict)
            assert res["status"] == "TIMED_OUT"
            assert res["approved"] is False
            assert "timed out" in res.get("error", "").lower() or "timed_out" in res.get("laconic_summary", "").lower()

    asyncio.run(_test())


def test_z3_thread_offloading_responsiveness():
    """Verify SMT Z3 theorem prover calls run via asyncio.to_thread without blocking event loop tasks."""
    async def _test():
        pipeline = UnifiedReasoningPipeline(effort_level="high")
        counter = 0

        async def heart_beat():
            nonlocal counter
            for _ in range(5):
                await asyncio.sleep(0.01)
                counter += 1

        pipeline_task = asyncio.create_task(
            pipeline.execute_pipeline(
                task_prompt="Concurrency test",
                code_proposal=VALID_CODE_PROPOSAL,
                file_path="concurrent.py",
                agent_votes=[
                    {"agent": "Planner", "approved": True, "verdict": "PASS", "reason": "OK"},
                    {"agent": "RLM_Coder", "approved": True, "verdict": "PASS", "reason": "OK"},
                    {"agent": "Verifier_Worker", "approved": False, "verdict": "FAIL", "reason": "Nitpick"},
                ],
            )
        )
        heartbeat_task = asyncio.create_task(heart_beat())

        res, _ = await asyncio.gather(pipeline_task, heartbeat_task)
        assert res["status"] == "APPROVED"
        assert counter == 5  # Event loop remained active!

    asyncio.run(_test())


def test_sync_execute_pipeline_wrapper():
    """Verify backward-compatible sync wrapper execute_pipeline_sync operates correctly."""
    pipeline = UnifiedReasoningPipeline(effort_level="high")
    res = pipeline.execute_pipeline_sync(
        task_prompt="Sync wrapper test",
        code_proposal=VALID_CODE_PROPOSAL,
        file_path="sync_test.py",
        agent_votes=[
            {"agent": "Planner", "approved": True, "verdict": "PASS", "reason": "OK"},
            {"agent": "RLM_Coder", "approved": True, "verdict": "PASS", "reason": "OK"},
            {"agent": "Verifier_Worker", "approved": False, "verdict": "FAIL", "reason": "Nitpick"},
        ],
    )

    assert isinstance(res, dict)
    assert res["status"] == "APPROVED"
    assert res["approved"] is True


def test_model_selector_async():
    """Verify ModelSelector.set_agent_configuration_async sets environment variables asynchronously."""
    async def _test():
        res = await ModelSelector.set_agent_configuration_async("gemini-3.6-flash", "high")
        assert isinstance(res, dict)
        assert res["model"] == "Gemini 3.6 Flash (High)"
        assert os.environ.get("VAZUS_MODEL") == "Gemini 3.6 Flash (High)"
        assert os.environ.get("VAZUS_REASONING_EFFORT") == "high"

    asyncio.run(_test())


def test_model_selector_sync_compatibility():
    """Verify ModelSelector.set_agent_configuration sync compatibility."""
    res = ModelSelector.set_agent_configuration("gpt-oss-120b", "medium")
    assert isinstance(res, dict)
    assert res["model"] == "GPT-OSS 120B (Medium)"
    assert os.environ.get("VAZUS_MODEL") == "GPT-OSS 120B (Medium)"
    assert os.environ.get("VAZUS_REASONING_EFFORT") == "medium"

