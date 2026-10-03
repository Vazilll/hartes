"""
labs.deepmind.funsearch_evolver.evaluator
=========================================
FunSearch code evaluation engine utilizing AntigravityWorktreeSandbox.
Executes candidate functions against verification suites and assigns multi-dimensional fitness.
"""

from __future__ import annotations

import ast
import logging
import time
from typing import Any, Callable, Dict, Optional, Tuple

logger = logging.getLogger("labs.deepmind.funsearch_evolver.evaluator")


class FunSearchEvaluator:
    """Evaluates code candidates in an isolated execution sandbox."""

    def __init__(self, sandbox: Optional[Any] = None):
        self.sandbox = sandbox

    def evaluate(self, candidate_code: str, test_suite_fn: Optional[Callable[[str], float]] = None) -> Tuple[float, int, int]:
        """
        Evaluates candidate code.
        Returns: (fitness_score, complexity_dim, performance_dim)
        """
        # 1. AST syntax & complexity analysis
        try:
            tree = ast.parse(candidate_code)
            nodes_count = len(list(ast.walk(tree)))
            # Complexity niche 0..4
            complexity_dim = min(4, max(0, nodes_count // 10))
        except SyntaxError:
            return 0.0, 0, 0

        # 2. Execution evaluation
        t0 = time.perf_counter()
        fitness = 0.0

        if test_suite_fn is not None:
            try:
                fitness = float(test_suite_fn(candidate_code))
            except Exception as e:
                logger.debug("Evaluation error: %s", e)
                fitness = 0.0
        elif self.sandbox is not None and hasattr(self.sandbox, "execute_task"):
            try:
                import sys
                res = self.sandbox.execute_task(command=[sys.executable, "-c", candidate_code], timeout=5)
                fitness = 1.0 if getattr(res, "success", False) and getattr(res, "returncode", -1) == 0 else 0.0
            except Exception as e:
                logger.debug("Sandbox evaluation error: %s", e)
                fitness = 0.0
        else:
            # Baseline AST heuristics if no test harness provided
            defs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
            fitness = min(1.0, 0.5 + (0.1 * len(defs)))

        dt_ms = (time.perf_counter() - t0) * 1000.0
        # Performance niche 0..4 (fastest is niche 4)
        perf_dim = 4 if dt_ms < 10 else (3 if dt_ms < 50 else (2 if dt_ms < 200 else 1))

        return round(fitness, 4), complexity_dim, perf_dim
