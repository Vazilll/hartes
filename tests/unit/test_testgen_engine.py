"""
Tests for vazus_core.verification.testgen_engine — AssuredTestGenEngine.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

from vazus_core.verification.testgen_engine import AssuredTestGenEngine


CLEAN_TEST = "import pytest\n\ndef test_add():\n    assert 1 + 1 == 2\n"
REWARD_HACK_TEST = "def test_nothing():\n    pass\n"
ASSERT_TRUE_TEST = "def test_trivial():\n    assert True\n"
SAMPLE_TARGET_SRC = 'def greet(name: str) -> str:\n    """Returns a greeting."""\n    return f"Hello, {name}"\n'

CLEAN_FENCE = f"```python\n{CLEAN_TEST}\n```"
HACK_FENCE = f"```python\n{REWARD_HACK_TEST}\n```"


class TestExtractCodeBlock:
    def setup_method(self):
        self.engine = AssuredTestGenEngine(workspace_root=r"C:\vazus")

    def test_extracts_python_fence(self):
        code = self.engine._extract_code_block(CLEAN_FENCE)
        assert "def test_add" in code
        assert "```" not in code

    def test_returns_raw_if_def_test_present(self):
        raw = "def test_foo():\n    assert 2 == 2"
        code = self.engine._extract_code_block(raw)
        assert "def test_foo" in code

    def test_returns_empty_for_non_test_text(self):
        code = self.engine._extract_code_block("Just some prose, no test here.")
        assert code == ""


class TestIsRewardHacking:
    def setup_method(self):
        self.engine = AssuredTestGenEngine(workspace_root=r"C:\vazus")

    def test_pass_detected(self):
        assert self.engine._is_reward_hacking(REWARD_HACK_TEST) is True

    def test_assert_true_detected(self):
        assert self.engine._is_reward_hacking(ASSERT_TRUE_TEST) is True

    def test_assert_one_equals_one_detected(self):
        assert self.engine._is_reward_hacking("def test_x():\n    assert 1 == 1") is True

    def test_clean_test_not_flagged(self):
        assert self.engine._is_reward_hacking(CLEAN_TEST) is False


class TestGenerateAssuredTest:
    def _make_engine_with_target(self, tmp_path: Path) -> tuple:
        src_file = tmp_path / "greet.py"
        src_file.write_text(SAMPLE_TARGET_SRC, encoding="utf-8")
        (tmp_path / "tests").mkdir()
        engine = AssuredTestGenEngine(workspace_root=str(tmp_path))
        return engine, "greet.py"

    def test_missing_file_returns_error(self, tmp_path):
        engine = AssuredTestGenEngine(workspace_root=str(tmp_path))
        result = asyncio.run(engine.generate_assured_test("nonexistent_module.py"))
        assert result["status"] == "ERROR"
        assert "not found" in result["reason"]

    def test_success_path(self, tmp_path):
        engine, rel = self._make_engine_with_target(tmp_path)

        with (
            patch(
                "vazus_core.verification.testgen_engine.async_generate_llm",
                new=AsyncMock(return_value=CLEAN_FENCE),
            ),
            patch.object(
                engine, "_execute_test_sandbox",
                return_value={"passed": True, "error": "", "duration_s": 0.1},
            ),
        ):
            result = asyncio.run(engine.generate_assured_test(rel, max_attempts=1))

        assert result["status"] == "SUCCESS"
        assert "test_code" in result
        assert result["attempt"] == 1

    def test_reward_hacking_skipped_exhausts_retries(self, tmp_path):
        engine, rel = self._make_engine_with_target(tmp_path)

        with patch(
            "vazus_core.verification.testgen_engine.async_generate_llm",
            new=AsyncMock(return_value=HACK_FENCE),
        ):
            result = asyncio.run(engine.generate_assured_test(rel, max_attempts=2))

        assert result["status"] == "FAIL"

    def test_syntax_error_gate_exhausts_retries(self, tmp_path):
        engine, rel = self._make_engine_with_target(tmp_path)
        bad_code = "```python\ndef test_broken(\n```"

        with patch(
            "vazus_core.verification.testgen_engine.async_generate_llm",
            new=AsyncMock(return_value=bad_code),
        ):
            result = asyncio.run(engine.generate_assured_test(rel, max_attempts=2))

        assert result["status"] == "FAIL"


class TestGate8Integration:
    """Tests Gate 8 (testgen coverage advisory) in precommit_gate."""

    def test_gate8_advisory_passes_by_default(self, tmp_path):
        from vazus_core.verification.precommit_gate import run_gate_8_testgen_coverage

        dummy = tmp_path / "orphan_module.py"
        dummy.write_text("def foo(): pass")

        passed, msgs = run_gate_8_testgen_coverage([dummy])
        assert passed is True
        assert isinstance(msgs, list)

    def test_gate8_strict_mode_blocks_on_missing_tests(self, tmp_path, monkeypatch):
        from vazus_core.verification.precommit_gate import run_gate_8_testgen_coverage

        monkeypatch.setenv("VAZUS_GATE_STRICT_TESTGEN", "1")

        dummy = tmp_path / "totally_new_untracked_module_xyz123.py"
        dummy.write_text("def bar(): pass")

        passed, msgs = run_gate_8_testgen_coverage([dummy])
        assert passed is False
        assert any("totally_new_untracked_module_xyz123" in m for m in msgs)
