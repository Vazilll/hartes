"""
Tests for Phase 1: Task abstraction, Registry, CodeOptimizerTask, and Runner.

All tests run without LLM API calls — GeminiPlanner is mocked at the boundary.
The core loop logic, scoring, and registry are tested with real code.
"""

from __future__ import annotations

import sys
import types
import hashlib
from pathlib import Path

import pytest

# Ensure hartes root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tasks.base import Candidate, Task, TaskResult, TaskStatus
from tasks.registry import TaskRegistry
from tasks.builtin.code_optimizer import CodeOptimizerTask, _extract_code_block, _extract_top_level_names


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

GOOD_CODE = """\
def add(a: int, b: int) -> int:
    return a + b

def multiply(x: int, y: int) -> int:
    return x * y
"""

BLOATED_CODE = GOOD_CODE + "\n" * 30 + "# lots of dead code\n" * 20

BAD_SYNTAX_CODE = "def foo(:\n    pass"

OPTIMIZED_CODE = """\
def add(a: int, b: int) -> int:
    \"\"\"Return sum.\"\"\"
    return a + b

def multiply(x: int, y: int) -> int:
    \"\"\"Return product.\"\"\"
    return x * y
"""


def _make_planner(response: str):
    """Return a mock planner_fn that always responds with the given string."""
    def planner_fn(prompt: str, history: list) -> dict:
        sig = hashlib.sha256(response.encode()).hexdigest()[:16]
        return {"response": response, "thought": "", "thought_signature": sig}
    return planner_fn


# ─────────────────────────────────────────────────────────────────────────────
# Candidate
# ─────────────────────────────────────────────────────────────────────────────

class TestCandidate:
    def test_content_hash_is_deterministic(self):
        c = Candidate(code="x = 1")
        assert c.content_hash == Candidate(code="x = 1").content_hash

    def test_different_code_different_hash(self):
        assert Candidate(code="a = 1").content_hash != Candidate(code="b = 2").content_hash

    def test_metadata_defaults_empty(self):
        c = Candidate(code="pass")
        assert c.metadata == {}


# ─────────────────────────────────────────────────────────────────────────────
# CodeOptimizerTask — construction
# ─────────────────────────────────────────────────────────────────────────────

class TestCodeOptimizerTaskConstruction:
    def test_inline_code_accepted(self):
        task = CodeOptimizerTask(inline_code=GOOD_CODE)
        assert task.seed == GOOD_CODE

    def test_missing_both_args_raises(self):
        with pytest.raises(ValueError):
            CodeOptimizerTask()

    def test_nonexistent_file_raises(self):
        with pytest.raises(FileNotFoundError):
            CodeOptimizerTask(input_file="/nonexistent/path/script.py")

    def test_task_id_auto_generated(self):
        task = CodeOptimizerTask(inline_code="pass")
        assert task.task_id.startswith("CodeOptimizerTask_")

    def test_custom_task_id(self):
        task = CodeOptimizerTask(inline_code="pass", task_id="my_task_001")
        assert task.task_id == "my_task_001"

    def test_problem_description_contains_code(self):
        task = CodeOptimizerTask(inline_code=GOOD_CODE)
        assert "def add" in task.problem_description


# ─────────────────────────────────────────────────────────────────────────────
# CodeOptimizerTask — evaluator
# ─────────────────────────────────────────────────────────────────────────────

class TestCodeOptimizerEvaluator:
    def test_perfect_candidate_scores_high(self):
        task = CodeOptimizerTask(inline_code=GOOD_CODE)
        candidate = Candidate(code=OPTIMIZED_CODE)
        score = task.evaluator(candidate)
        assert score >= 75.0, f"Expected >= 75.0 but got {score}"

    def test_syntax_error_scores_zero(self):
        task = CodeOptimizerTask(inline_code=GOOD_CODE)
        candidate = Candidate(code=BAD_SYNTAX_CODE)
        assert task.evaluator(candidate) == 0.0

    def test_bloated_code_scores_lower_than_compact(self):
        task = CodeOptimizerTask(inline_code=GOOD_CODE)
        compact_score = task.evaluator(Candidate(code=OPTIMIZED_CODE))
        bloated_score = task.evaluator(Candidate(code=BLOATED_CODE))
        assert compact_score >= bloated_score

    def test_admissibility_threshold_at_75(self):
        task = CodeOptimizerTask(inline_code=GOOD_CODE)
        assert task.is_admissible(75.0) is True
        assert task.is_admissible(74.9) is False

    def test_no_test_command_awards_full_test_marks(self):
        # Without a test_command, 30 pts should be awarded by default
        task = CodeOptimizerTask(inline_code=GOOD_CODE)
        # Syntax OK (40) + tests waived (30) + compact (15) + names preserved (15) = 100
        score = task.evaluator(Candidate(code=GOOD_CODE))
        assert score == 100.0

    def test_missing_function_name_loses_points(self):
        task = CodeOptimizerTask(inline_code=GOOD_CODE)
        # Remove 'multiply' from candidate
        stripped = "def add(a, b):\n    return a + b\n"
        score = task.evaluator(Candidate(code=stripped))
        # Should be < 100 (loses 15 pts for missing name)
        assert score < 100.0


# ─────────────────────────────────────────────────────────────────────────────
# CodeOptimizerTask — generate_candidate
# ─────────────────────────────────────────────────────────────────────────────

class TestCodeOptimizerGenerate:
    def test_extracts_code_block_from_response(self):
        response = "Here is the code:\n```python\ndef foo(): return 42\n```"
        planner = _make_planner(response)
        task = CodeOptimizerTask(inline_code=GOOD_CODE)
        candidate = task.generate_candidate(planner, dead_ends=[], round_n=1)
        assert "def foo" in candidate.code

    def test_fallback_to_raw_response_when_no_block(self):
        response = "def bar(): return 1"
        planner = _make_planner(response)
        task = CodeOptimizerTask(inline_code=GOOD_CODE)
        candidate = task.generate_candidate(planner, dead_ends=[], round_n=1)
        assert "def bar" in candidate.code

    def test_dead_ends_injected_into_prompt(self, monkeypatch):
        captured_prompts = []

        def capturing_planner(prompt: str, history: list) -> dict:
            captured_prompts.append(prompt)
            return {"response": "def foo(): pass", "thought": "", "thought_signature": "x"}

        task = CodeOptimizerTask(inline_code=GOOD_CODE)
        task.generate_candidate(
            capturing_planner,
            dead_ends=["approach A failed", "approach B failed"],
            round_n=2,
        )
        assert "approach A failed" in captured_prompts[0]

    def test_round_number_in_prompt(self, monkeypatch):
        captured = []

        def planner(prompt, history):
            captured.append(prompt)
            return {"response": "pass", "thought": "", "thought_signature": "y"}

        task = CodeOptimizerTask(inline_code=GOOD_CODE)
        task.generate_candidate(planner, dead_ends=[], round_n=3)
        assert "round 3" in captured[0]


# ─────────────────────────────────────────────────────────────────────────────
# Helper functions
# ─────────────────────────────────────────────────────────────────────────────

class TestHelpers:
    def test_extract_code_block_python(self):
        text = "Some text\n```python\nresult = 42\n```\nmore text"
        assert _extract_code_block(text) == "result = 42"

    def test_extract_code_block_generic(self):
        text = "```\nx = 1\n```"
        assert _extract_code_block(text) == "x = 1"

    def test_extract_code_block_returns_none_when_absent(self):
        assert _extract_code_block("no code here") is None

    def test_extract_top_level_names_functions(self):
        names = _extract_top_level_names(GOOD_CODE)
        assert "add" in names
        assert "multiply" in names

    def test_extract_top_level_names_empty_on_syntax_error(self):
        assert _extract_top_level_names(BAD_SYNTAX_CODE) == set()

    def test_extract_top_level_names_excludes_nested(self):
        code = "def outer():\n    def inner(): pass\n"
        names = _extract_top_level_names(code)
        assert "outer" in names
        assert "inner" not in names


# ─────────────────────────────────────────────────────────────────────────────
# TaskRegistry
# ─────────────────────────────────────────────────────────────────────────────

class TestTaskRegistry:
    def test_code_optimizer_is_discoverable(self):
        TaskRegistry._discovered = False
        TaskRegistry._registry = {}
        available = TaskRegistry.list_available()
        assert "code_optimizer" in available

    def test_load_code_optimizer(self):
        TaskRegistry._discovered = False
        TaskRegistry._registry = {}
        task = TaskRegistry.load("code_optimizer", inline_code="x = 1")
        assert isinstance(task, CodeOptimizerTask)

    def test_load_unknown_task_raises_key_error(self):
        TaskRegistry._discovered = False
        TaskRegistry._registry = {}
        with pytest.raises(KeyError, match="No task named"):
            TaskRegistry.load("nonexistent_task_xyz")


# ─────────────────────────────────────────────────────────────────────────────
# Runner integration (deterministic test mode)
# ─────────────────────────────────────────────────────────────────────────────

class TestRunnerIntegration:
    """
    Integration tests for runner.run() using AgyPlanner's internal deterministic test mode.
    Verifies that the full loop (Memory → Preflight → Generate → Evaluate →
    AntiThrashing) runs correctly without real API calls or mocks.
    """

    def test_success_on_first_round(self):
        import runner
        result = runner.run(
            task_name="code_optimizer",
            max_rounds=3,
            model="flash-lite",
            inline_code=GOOD_CODE,
        )
        assert result["status"] == "SUCCESS"
        assert result["score"] >= 75.0
        assert result["rounds_used"] == 1

    def test_timeout_when_always_bad(self, monkeypatch):
        class DeterministicBadPlanner:
            def __init__(self, *args, **kwargs):
                pass

            def plan(self, user_input, history):
                sig = hashlib.sha256(BAD_SYNTAX_CODE.encode()).hexdigest()[:16]
                return {
                    "response": f"```python\n{BAD_SYNTAX_CODE}\n```",
                    "thought": "Deterministic syntax failure",
                    "thought_signature": sig,
                    "model": "deterministic-bad",
                }

        monkeypatch.setattr("llm.agy_planner.AgyPlanner", DeterministicBadPlanner)
        import runner
        result = runner.run(
            task_name="code_optimizer",
            max_rounds=2,
            model="flash-lite",
            inline_code=GOOD_CODE,
        )
        assert result["status"] in ("TIMEOUT", "ESCALATED")

    def test_result_has_required_keys(self):
        import runner
        result = runner.run(
            task_name="code_optimizer",
            max_rounds=1,
            model="flash-lite",
            inline_code=GOOD_CODE,
        )
        for key in ("status", "task_id", "score", "rounds_used", "duration_s"):
            assert key in result, f"Missing key: {key}"


# ─────────────────────────────────────────────────────────────────────────────
# AgyPlanner Unit Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestAgyPlanner:
    def test_resolve_model_name_aliases(self):
        from llm.agy_planner import resolve_model_name
        assert resolve_model_name("flash") == "gemini-3.8-flash-high"
        assert resolve_model_name("flash-lite") == "gemini-3.7-flash-high"
        assert resolve_model_name("pro") == "gemini-3.1-pro-high"
        assert resolve_model_name("sonnet") == "claude-sonnet-4-6"
        assert resolve_model_name("opus") == "claude-opus-4-6-thinking"
        assert resolve_model_name("gpt") == "gpt-oss-120b-medium"

    def test_resolve_agy_binary_returns_valid_or_none(self):
        from llm.agy_planner import resolve_agy_binary
        bin_path = resolve_agy_binary()
        # On user machine agy.exe is installed, so bin_path is not None
        assert bin_path is not None
        assert bin_path.exists()

    def test_agy_planner_offline_mock(self):
        from llm.agy_planner import AgyPlanner
        planner = AgyPlanner(model="flash")
        # In pytest, is_test_mode() is True
        res = planner.plan("def foo(): return 1", history=[])
        assert "response" in res
        assert "thought_signature" in res
        assert res["model"] == "gemini-3.8-flash-high"
        assert "def foo" in res["response"]
