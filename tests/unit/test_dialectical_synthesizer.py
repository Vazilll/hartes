"""
Tests for vazus_core.engine.dialectical_synthesizer — DialecticalSynthesizer.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from vazus_core.engine.dialectical_synthesizer import DialecticalSynthesizer


SAMPLE_CODE = "def add(a: int, b: int) -> int:\n    return a + b"
SAMPLE_FENCE = f"```python\n{SAMPLE_CODE}\n```"
SAMPLE_CRITIQUE = "1. No overflow guard. 2. No type check."


class TestExtractCode:
    def setup_method(self):
        self.ds = DialecticalSynthesizer(depth=2)

    def test_extracts_from_python_fence(self):
        code = self.ds._extract_code(SAMPLE_FENCE)
        assert "def add" in code
        assert "```" not in code

    def test_extracts_from_bare_fence(self):
        text = "```\nprint('hello')\n```"
        code = self.ds._extract_code(text)
        assert "print" in code
        assert "```" not in code

    def test_returns_raw_text_when_no_fence(self):
        raw = "def foo(): pass"
        assert self.ds._extract_code(raw) == raw

    def test_strips_whitespace(self):
        padded = "```python\n\n  x = 1  \n\n```"
        code = self.ds._extract_code(padded)
        assert code == "x = 1"


class TestSynthesizeContract:
    """Validates synthesize() returns a dict with required keys (mocked LLM)."""

    def test_synthesize_keys_present(self):
        ds = DialecticalSynthesizer(depth=2)

        with patch(
            "vazus_core.engine.dialectical_synthesizer.async_generate_llm",
            new=AsyncMock(side_effect=[SAMPLE_FENCE, SAMPLE_CRITIQUE, SAMPLE_FENCE]),
        ):
            result = asyncio.run(ds.synthesize(
                task_description="Write an add function",
                context="simple arithmetic"
            ))

        assert result["status"] == "SUCCESS"
        assert "thesis_code" in result
        assert "antithesis_critique" in result
        assert "final_synthesized_code" in result
        assert "smt_initial_status" in result

    def test_synthesize_three_llm_calls(self):
        """Exactly 3 LLM calls: Thesis, Antithesis, Synthesis."""
        ds = DialecticalSynthesizer(depth=2)
        mock_llm = AsyncMock(side_effect=[SAMPLE_FENCE, SAMPLE_CRITIQUE, SAMPLE_FENCE])

        with patch("vazus_core.engine.dialectical_synthesizer.async_generate_llm", new=mock_llm):
            asyncio.run(ds.synthesize("Write a multiply function"))

        assert mock_llm.call_count == 3

    def test_smt_status_is_string_or_none(self):
        """SMT verifier runs on thesis code and status is propagated."""
        ds = DialecticalSynthesizer(depth=2)

        with patch(
            "vazus_core.engine.dialectical_synthesizer.async_generate_llm",
            new=AsyncMock(side_effect=[SAMPLE_FENCE, SAMPLE_CRITIQUE, SAMPLE_FENCE]),
        ):
            result = asyncio.run(ds.synthesize("Write a safe divide function"))

        assert isinstance(result["smt_initial_status"], (str, type(None)))
        assert "smt_final_status" in result
        assert "smt_final_verified" in result
        assert "cegis_refined" in result

    def test_cegis_refinement_trigger_on_smt_sat(self):
        """When synthesis output triggers SMT SAT violation, CEGIS stage 3b is executed."""
        ds = DialecticalSynthesizer(depth=2)

        # Mock initial synthesis code with failing contract
        failing_code = """
def abs_val(x: int) -> int:
    \"\"\"
    :requires: True
    :ensures: result > 0
    \"\"\"
    return x
"""
        failing_fence = f"```python\n{failing_code}\n```"

        repaired_code = """
def abs_val(x: int) -> int:
    \"\"\"
    :requires: True
    :ensures: result >= 0
    \"\"\"
    return -x if x < 0 else x
"""
        repaired_fence = f"```python\n{repaired_code}\n```"

        # Thesis, Antithesis, Synthesis (failing), CEGIS Refinement (repaired)
        mock_llm = AsyncMock(side_effect=[SAMPLE_FENCE, SAMPLE_CRITIQUE, failing_fence, repaired_fence])

        with patch("vazus_core.engine.dialectical_synthesizer.async_generate_llm", new=mock_llm):
            result = asyncio.run(ds.synthesize("Write an abs function"))

        assert result["status"] == "SUCCESS"
        assert result["cegis_refined"] is True
        assert mock_llm.call_count == 4
