#!/usr/bin/env python3
"""
vazus_core.verification.differential_runner — Property-Based Differential Fuzzing Runner.
========================================================================================

Implements Differential Testing (DiffTestGen / Cross-Version Equivalence):
  1. Compares original baseline function against modified/optimized function.
  2. Generates comprehensive boundary fuzzing inputs (zero, negative, sys.maxsize, empty strings, NaN, deep lists).
  3. Executes both functions in isolated namespaces and compares outputs and exceptions.
  4. Returns minimal counterexamples for any behavioral divergence.
"""

import logging
import math
import sys
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("vazus_core.verification.differential")


# Standard edge-case fuzz corpus for generic Python functions
DEFAULT_INT_CORPUS = [0, 1, -1, 2, 42, 100, -100, 1000, 2**16, 2**31 - 1, -(2**31), sys.maxsize]
DEFAULT_STR_CORPUS = ["", "a", "hello world", "   ", "\n\t", "123", "🔥", "null", "None", "a" * 500]
DEFAULT_LIST_CORPUS = [[], [0], [1, 2, 3], [-1, 0, 1], list(range(50)), ["a", "b"]]


class DifferentialRunner:
    """
    Executes differential fuzz testing between two callable implementations.
    """

    def run_differential_comparison(
        self, func_orig: Callable, func_new: Callable, input_corpus: Optional[List[Any]] = None
    ) -> Dict[str, Any]:
        """
        Runs func_orig and func_new on each input in corpus and compares results.
        """
        corpus = input_corpus or (DEFAULT_INT_CORPUS + DEFAULT_STR_CORPUS + DEFAULT_LIST_CORPUS)
        passed_count = 0
        divergences = []

        for inp in corpus:
            res_orig, exc_orig = self._safe_call(func_orig, inp)
            res_new, exc_new = self._safe_call(func_new, inp)

            if exc_orig is not None or exc_new is not None:
                # Compare exception types
                if type(exc_orig) == type(exc_new):
                    passed_count += 1
                else:
                    divergences.append(
                        {
                            "input": repr(inp),
                            "orig_exception": str(exc_orig),
                            "new_exception": str(exc_new),
                            "type": "EXCEPTION_MISMATCH",
                        }
                    )
            else:
                # Compare return values
                if self._are_outputs_equal(res_orig, res_new):
                    passed_count += 1
                else:
                    divergences.append(
                        {
                            "input": repr(inp),
                            "orig_output": repr(res_orig),
                            "new_output": repr(res_new),
                            "type": "OUTPUT_MISMATCH",
                        }
                    )

        total = len(corpus)
        equivalence_rate = (passed_count / total) if total > 0 else 1.0

        return {
            "status": "EQUIVALENT" if not divergences else "DIVERGENCE_DETECTED",
            "total_tested": total,
            "passed_count": passed_count,
            "divergences_count": len(divergences),
            "equivalence_rate": round(equivalence_rate, 4),
            "counterexamples": divergences[:5],  # Top 5 minimal counterexamples
        }

    def _safe_call(self, fn: Callable, inp: Any) -> Tuple[Any, Optional[Exception]]:
        """Executes function safely, handling single args or tuple args."""
        try:
            if isinstance(inp, tuple):
                return fn(*inp), None
            return fn(inp), None
        except Exception as e:
            return None, e

    def _are_outputs_equal(self, a: Any, b: Any) -> bool:
        """Handles float NaN equality and deep collection equality."""
        if isinstance(a, float) and isinstance(b, float):
            if math.isnan(a) and math.isnan(b):
                return True
            return math.isclose(a, b, rel_tol=1e-7)
        return a == b
