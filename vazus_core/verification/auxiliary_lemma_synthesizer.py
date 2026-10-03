"""
vazus_core.verification.auxiliary_lemma_synthesizer
===================================================
AlphaGeometry-inspired Neurosymbolic Auxiliary Lemma Synthesizer.
When SMT Z3 returns UNKNOWN (e.g. due to non-linear integer arithmetic or incomplete
axiomatization), generates candidate auxiliary lemmas and invariants, re-feeding them
into the solver until UNSAT (verified), SAT (counterexample found), or timeout.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import z3

logger = logging.getLogger("vazus_core.verification.auxiliary_lemma_synthesizer")


@dataclass
class LemmaSynthesisResult:
    """Outcome of SMT verification with auxiliary lemma synthesis."""
    status: str  # "UNSAT" (proven theorem), "SAT" (counterexample found), "UNKNOWN", "TIMEOUT"
    verified: bool
    iterations: int
    lemmas_added: List[str] = field(default_factory=list)
    counterexample: Optional[Dict[str, Any]] = None
    duration_ms: float = 0.0
    error_message: Optional[str] = None


class AuxiliaryLemmaSynthesizer:
    """
    Active Neurosymbolic Synthesizer for SMT Z3.
    Augments proof search with auxiliary bounds, monotonicity, and induction lemmas.
    """

    DEFAULT_HEURISTIC_LEMMAS = [
        "x >= 0",
        "y >= 0",
        "old_val <= new_val",
        "stride > 0",
        "len(items) >= 0",
    ]

    def __init__(
        self,
        llm_engine: Optional[Any] = None,
        timeout_ms: int = 2000,
    ):
        self.llm = llm_engine
        self.timeout_ms = timeout_ms

    def verify_with_lemmas(
        self,
        solver: z3.Solver,
        goal_assertions: List[z3.BoolRef],
        variables: Optional[Dict[str, z3.ExprRef]] = None,
        context_description: str = "",
        max_iterations: int = 4,
    ) -> LemmaSynthesisResult:
        """
        Attempts to prove theorem (by checking negation unsatisfiability).
        If solver returns unknown, synthesizes auxiliary lemmas and retries.
        """
        t0 = time.perf_counter()
        solver.set("timeout", self.timeout_ms)

        lemmas_used: List[str] = []
        vars_map = variables or {}

        for iteration in range(1, max_iterations + 1):
            check_res = solver.check()

            if check_res == z3.unsat:
                dt_ms = (time.perf_counter() - t0) * 1000.0
                return LemmaSynthesisResult(
                    status="UNSAT",
                    verified=True,
                    iterations=iteration,
                    lemmas_added=lemmas_used,
                    duration_ms=round(dt_ms, 2),
                )

            elif check_res == z3.sat:
                dt_ms = (time.perf_counter() - t0) * 1000.0
                model = solver.model()
                cex = {str(d): str(model[d]) for d in model.decls()}
                return LemmaSynthesisResult(
                    status="SAT",
                    verified=False,
                    iterations=iteration,
                    lemmas_added=lemmas_used,
                    counterexample=cex,
                    duration_ms=round(dt_ms, 2),
                )

            # Solver returned UNKNOWN or TIMEOUT -> synthesize auxiliary lemma
            lemma_text = self._synthesize_candidate_lemma(
                iteration=iteration,
                context=context_description,
                vars_map=vars_map,
            )

            if not lemma_text:
                break

            lemmas_used.append(lemma_text)
            self._apply_lemma_to_solver(solver, lemma_text, vars_map)

        dt_ms = (time.perf_counter() - t0) * 1000.0
        return LemmaSynthesisResult(
            status="UNKNOWN",
            verified=False,
            iterations=max_iterations,
            lemmas_added=lemmas_used,
            duration_ms=round(dt_ms, 2),
            error_message=f"Z3 returned UNKNOWN after {max_iterations} lemma synthesis iterations",
        )

    def _synthesize_candidate_lemma(
        self,
        iteration: int,
        context: str,
        vars_map: Dict[str, z3.ExprRef],
    ) -> Optional[str]:
        """Synthesizes candidate lemma from LLM or structured domain heuristics."""
        # 1. Check if LLM engine is available
        if self.llm is not None and hasattr(self.llm, "generate"):
            try:
                var_names = list(vars_map.keys())
                prompt = (
                    f"Given verification context: {context}\n"
                    f"Variables: {var_names}\n"
                    f"Suggest ONE Z3 auxiliary invariant or boundary lemma (e.g., 'x >= 0', 'a + b >= c'):"
                )
                res = self.llm.generate(prompt)
                if res and isinstance(res, str):
                    return res.strip().splitlines()[0]
            except Exception as e:
                logger.debug("LLM lemma generation error: %s", e)

        # 2. Domain heuristics based on active variable names
        if iteration == 1 and vars_map:
            # Non-negativity on integer/real vars
            var_name = list(vars_map.keys())[0]
            return f"{var_name} >= 0"
        elif iteration == 2 and len(vars_map) >= 2:
            k1, k2 = list(vars_map.keys())[:2]
            return f"{k1} <= {k2}"
        elif iteration < len(self.DEFAULT_HEURISTIC_LEMMAS):
            return self.DEFAULT_HEURISTIC_LEMMAS[iteration]

        return None

    def _apply_lemma_to_solver(
        self,
        solver: z3.Solver,
        lemma_str: str,
        vars_map: Dict[str, z3.ExprRef],
    ) -> bool:
        """
        Parses relational lemmas and adds them as Z3 constraints only after
        verifying mathematical consistency with existing solver assertions.
        Guarantees Mathematical Soundness Gate: prevents false UNSAT from contradictory premises.
        """
        clean_lemma = lemma_str.strip()
        lemma_expr: Optional[z3.BoolRef] = None

        # 1. Try direct evaluation with vars_map as Z3 expression context
        try:
            res = eval(clean_lemma, {"__builtins__": {}}, vars_map)
            if isinstance(res, z3.BoolRef):
                lemma_expr = res
        except Exception:
            pass

        # 2. Heuristic regex parser for relational inequalities
        if lemma_expr is None:
            try:
                import re
                m = re.match(r"^(\w+)\s*(<=|>=|<|>|==|!=)\s*(\w+)$", clean_lemma)
                if m:
                    left, op, right = m.groups()
                    left_ref = vars_map.get(left)
                    right_ref = vars_map.get(right)
                    # Check if right is an integer constant
                    if right_ref is None and right.isdigit():
                        right_val = int(right)
                        if left_ref is not None:
                            if op == "<=": lemma_expr = (left_ref <= right_val)
                            elif op == ">=": lemma_expr = (left_ref >= right_val)
                            elif op == "<": lemma_expr = (left_ref < right_val)
                            elif op == ">": lemma_expr = (left_ref > right_val)
                            elif op == "==": lemma_expr = (left_ref == right_val)
                            elif op == "!=": lemma_expr = (left_ref != right_val)
                    elif left_ref is not None and right_ref is not None:
                        if op == "<=": lemma_expr = (left_ref <= right_ref)
                        elif op == ">=": lemma_expr = (left_ref >= right_ref)
                        elif op == "<": lemma_expr = (left_ref < right_ref)
                        elif op == ">": lemma_expr = (left_ref > right_ref)
                        elif op == "==": lemma_expr = (left_ref == right_ref)
                        elif op == "!=": lemma_expr = (left_ref != right_ref)
            except Exception as e:
                logger.debug("Failed parsing lemma '%s': %s", lemma_str, e)

        if lemma_expr is None:
            return False

        # Mathematical Soundness Gate: verify lemma is satisfiable and consistent with current assertions
        lemma_alone_solver = z3.Solver()
        lemma_alone_solver.set("timeout", 500)
        lemma_alone_solver.add(lemma_expr)
        if lemma_alone_solver.check() == z3.unsat:
            logger.warning("Rejected unsound lemma '%s': inherently unsatisfiable", lemma_str)
            return False

        if solver.assertions():
            test_solver = z3.Solver()
            test_solver.set("timeout", 500)
            for a in solver.assertions():
                test_solver.add(a)
            test_solver.add(lemma_expr)
            res_status = test_solver.check()
            if res_status != z3.sat:
                logger.warning("Rejected unsound lemma '%s': solver returned %s with existing assertions", lemma_str, res_status)
                return False

        solver.add(lemma_expr)
        return True

