"""
hartes.tasks.builtin.code_optimizer — Python code optimization task.

Given an input Python file (or inline code), this task asks the LLM to
produce a refactored/optimized version and evaluates it by:
  1. Syntax validity (AST parse) — mandatory gate
  2. Correctness — running original tests if a test_command is provided
  3. Parsimony — rewarding shorter, cleaner diffs

This is the canonical "hello world" task for Hartes: it demonstrates
the full loop (generate → evaluate → record → accept/escalate) with
a real, measurable objective.

Usage via CLI:
    python -m hartes run --task=code_optimizer --input=my_script.py
    python -m hartes run --task=code_optimizer --input=my_script.py --test-cmd="pytest tests/"
"""

from __future__ import annotations

import ast
import shlex
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from tasks.base import Candidate, Task


class CodeOptimizerTask(Task):
    """
    Optimize a Python source file: improve readability, reduce complexity,
    eliminate dead code, enforce PEP-8, and keep all existing tests passing.

    Scoring rubric (max 100 pts):
        40 — syntax valid AST  (mandatory, hard gate)
        30 — tests pass (or no test_command provided → awarded by default)
        15 — lines_of_code delta <= 0  (did not bloat)
        15 — no new pylint/pyflakes violations (best-effort)
    """

    def __init__(
        self,
        input_file: Optional[str] = None,
        inline_code: Optional[str] = None,
        test_command: Optional[str] = None,
        task_id: Optional[str] = None,
    ):
        super().__init__(task_id=task_id)
        if input_file is None and inline_code is None:
            raise ValueError("Provide either 'input_file' or 'inline_code'.")
        if input_file is not None:
            p = Path(input_file)
            if not p.exists():
                raise FileNotFoundError(f"Input file not found: {input_file}")
            self._source_path: Optional[Path] = p
            self._seed_code: str = p.read_text(encoding="utf-8")
        else:
            self._source_path = None
            self._seed_code = inline_code or ""
        self._test_command = test_command

    # ── Task contract ────────────────────────────────────────────────────────

    @property
    def problem_description(self) -> str:
        origin = str(self._source_path) if self._source_path else "<inline>"
        loc = self._seed_code.count("\n") + 1
        return (
            f"Optimize the following Python code ({loc} lines, source: {origin}).\n"
            f"Goals: improve readability, reduce cyclomatic complexity, eliminate "
            f"dead code and imports, follow PEP-8, preserve all existing behaviour.\n\n"
            f"```python\n{self._seed_code}\n```"
        )

    @property
    def seed(self) -> str:
        return self._seed_code

    def evaluator(self, candidate: Candidate) -> float:
        """
        Objective scoring — pure function, no side effects on the repo.
        Returns a float in [0.0, 100.0].
        """
        code = candidate.code
        score = 0.0

        # ── Gate 1: AST syntax (+40 pts, mandatory) ──────────────────────────
        try:
            ast.parse(code)
            score += 40.0
        except SyntaxError:
            return 0.0  # hard reject — unrunnable code

        # ── Gate 2: Tests pass (+30 pts) ─────────────────────────────────────
        if self._test_command is None:
            # No test suite provided → award full marks (good faith)
            score += 30.0
        else:
            import tempfile, os
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False, encoding="utf-8"
            ) as tmp:
                tmp.write(code)
                tmp_path = tmp.name
            try:
                # Swap the candidate file in for testing
                cmd = self._test_command.replace(
                    str(self._source_path or ""), tmp_path
                )
                result = subprocess.run(
                    shlex.split(cmd, posix=(sys.platform != "win32")),
                    shell=False,
                    capture_output=True,
                    timeout=60
                )
                if result.returncode == 0:
                    score += 30.0
            except subprocess.TimeoutExpired:
                pass
            finally:
                os.unlink(tmp_path)

        # ── Gate 3: Parsimony — no line bloat (+15 pts) ──────────────────────
        original_loc = self._seed_code.count("\n") + 1
        candidate_loc = code.count("\n") + 1
        if candidate_loc <= original_loc:
            score += 15.0
        else:
            # Partial credit: up to 15 pts proportional to how much smaller/larger
            ratio = original_loc / max(candidate_loc, 1)
            score += max(0.0, 15.0 * ratio)

        # ── Gate 4: No obvious regressions (heuristic, +15 pts) ──────────────
        # Check that all top-level function/class names from the original exist
        original_names = _extract_top_level_names(self._seed_code)
        candidate_names = _extract_top_level_names(code)
        if original_names and original_names.issubset(candidate_names):
            score += 15.0
        elif not original_names:
            score += 15.0  # nothing to compare → full marks

        return min(score, 100.0)

    def generate_candidate(
        self,
        planner_fn: Callable[[str, List[Dict[str, Any]]], Dict[str, Any]],
        dead_ends: List[str],
        round_n: int = 1,
    ) -> Candidate:
        """Ask the LLM to produce an optimized version of the code."""
        dead_end_section = ""
        if dead_ends:
            formatted = "\n".join(f"  - {d}" for d in dead_ends[:5])
            dead_end_section = (
                f"\n\nIMPORTANT — these approaches were tried before and FAILED. "
                f"Do NOT repeat them:\n{formatted}\n"
            )

        prompt = textwrap.dedent(f"""
            You are an expert Python software engineer performing a code optimization task.

            TASK (round {round_n}):
            {self.problem_description}
            {dead_end_section}
            OUTPUT FORMAT:
            Respond with ONLY the optimized Python code, enclosed in triple backticks:
            ```python
            <your optimized code here>
            ```
            No explanation. No commentary. Code only.
        """).strip()

        plan = planner_fn(prompt, [])
        raw_response: str = plan.get("response", "")

        # Extract code block from response
        code = _extract_code_block(raw_response) or raw_response.strip()
        return Candidate(
            code=code,
            metadata={"round": round_n, "prompt_len": len(prompt)},
        )


# ── Helpers ──────────────────────────────────────────────────────────────────

def _extract_top_level_names(code: str) -> set[str]:
    """Return the set of top-level function and class names in code."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return set()
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and isinstance(getattr(node, "col_offset", 1), int)
        and node.col_offset == 0
    }


def _extract_code_block(text: str) -> Optional[str]:
    """Extract the first ```python ... ``` block from LLM output."""
    import re
    pattern = r"```(?:python)?\s*\n(.*?)```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None
