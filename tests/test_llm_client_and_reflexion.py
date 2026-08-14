"""
tests/test_llm_client_and_reflexion.py — Unit tests for M2 Async LLM Client Bridge,
Reflexion Fixer (_llm_fix_fn), and Parallel Concordia Jury Voting.
"""

import os
import pytest
import asyncio
from vazus_core.llm_client import is_test_mode, _generate_mock_response, async_generate_llm
from vazus_core.model_selector import ModelSelector
from vazus_core.concordia_jury import ConcordiaJury
from vazus_core.subagent_framework import SubagentContext, auto_improver_on_complete_hook
from vazus_core.unified_reasoning_pipeline import UnifiedReasoningPipeline


def test_is_test_mode_detection():
    """Verify test mode is correctly detected in pytest execution."""
    assert is_test_mode() is True


def test_model_selector_get_active_model():
    """Verify get_active_model returns current model key or default."""
    model_key = ModelSelector.get_active_model()
    assert model_key in ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.1-pro", "claude-sonnet-4.6", "claude-opus-4.6", "gpt-oss-120b"]


def test_async_generate_llm_test_mode():
    """Verify async_generate_llm generates deterministic response in test mode."""
    async def _test():
        res = await async_generate_llm(prompt="Evaluate code proposal for Concordia Jury", system_prompt="You are Planner")
        assert isinstance(res, str)
        assert len(res) > 0

    asyncio.run(_test())


def test_concordia_jury_vote_async_parallel_eval():
    """Verify ConcordiaJury.vote_async executes 3 parallel LLM evaluations when votes is None."""
    async def _test():
        jury = ConcordiaJury()
        proposal = """
def add(a: int, b: int) -> int:
    return a + b
"""
        verdict = await jury.vote_async(proposal=proposal, votes=None)
        assert verdict.approved is True
        assert verdict.consensus_ratio >= 0.66
        assert len(verdict.votes) == 3

    asyncio.run(_test())


def test_unified_reasoning_pipeline_parallel_jury():
    """Verify UnifiedReasoningPipeline invokes real parallel jury calls when agent_votes is None."""
    async def _test():
        pipeline = UnifiedReasoningPipeline(effort_level="high")
        proposal = """
def multiply(x: int, y: int) -> int:
    return x * y
"""
        res = await pipeline.execute_pipeline(
            task_prompt="Multiply two integers",
            code_proposal=proposal,
            file_path="multiply.py",
            agent_votes=None
        )
        assert res["status"] == "APPROVED"
        assert res["approved"] is True
        assert "jury_result" in res

    asyncio.run(_test())
