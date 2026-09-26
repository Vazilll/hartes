"""
vazus_autonomous_harness.verification.smt_equivalence_prover

Formal SMT Z3 Semantic Equivalence & Invariant Prover.
Mathematically proves functional equivalence between original and refactored/mutated expressions:
∀ inputs x ∈ Domain: f_original(x) == f_refactored(x)
Extracts concrete counterexamples upon discrepancy.
"""

import ast
import logging
from typing import Dict, List, Any
import z3

logger = logging.getLogger("vazus.harness.verification.smt")


class SMTEquivalenceProver:
    """
    Formally verifies functional equivalence of arithmetic and logical expressions
    using the Microsoft Z3 SMT Solver.
    """

    def __init__(self, timeout_ms: int = 5000):
        self.timeout_ms = timeout_ms

    def verify_expression_equivalence(
        self,
        expr1: str,
        expr2: str,
        variable_names: List[str]
    ) -> Dict[str, Any]:
        """
        Proves whether expr1 == expr2 for all continuous/discrete domain inputs.
        Returns:
            {"equivalent": True, "status": "PROVEN_EQUIVALENT"} if UNSAT (no counterexample)
            {"equivalent": False, "status": "DISPROVEN", "counterexample": {...}} if SAT
        """
        solver = z3.Solver()
        solver.set("timeout", self.timeout_ms)

        # Create Z3 symbolic variables
        z3_vars = {name: z3.Real(name) for name in variable_names}

        try:
            # Parse and translate AST expressions to Z3 symbolic AST
            z3_expr1 = self._ast_to_z3(ast.parse(expr1, mode="eval").body, z3_vars)
            z3_expr2 = self._ast_to_z3(ast.parse(expr2, mode="eval").body, z3_vars)

            # Invariant: prove that NOT (expr1 == expr2) is UNSATISFIABLE
            solver.add(z3_expr1 != z3_expr2)

            check_result = solver.check()
            if check_result == z3.unsat:
                return {
                    "equivalent": True,
                    "status": "PROVEN_EQUIVALENT",
                    "proof": "UNSAT — No inputs exist where expressions differ."
                }
            elif check_result == z3.sat:
                model = solver.model()
                counterexample = {d.name(): str(model[d]) for d in model.decls()}
                return {
                    "equivalent": False,
                    "status": "DISPROVEN",
                    "counterexample": counterexample
                }
            else:
                return {
                    "equivalent": False,
                    "status": "UNKNOWN_TIMEOUT",
                    "reason": "Solver returned unknown or timed out."
                }
        except Exception as e:
            logger.warning(f"SMT translation error for '{expr1}' vs '{expr2}': {e}")
            return {
                "equivalent": False,
                "status": "TRANSLATION_ERROR",
                "error": str(e)
            }

    def _ast_to_z3(self, node: ast.AST, z3_vars: Dict[str, z3.ExprRef]) -> z3.ExprRef:
        """Recursively translates an AST expression into a Z3 symbolic expression."""
        if isinstance(node, ast.Constant):
            return z3.RealVal(node.value)
        elif isinstance(node, ast.Name):
            if node.id in z3_vars:
                return z3_vars[node.id]
            else:
                z3_vars[node.id] = z3.Real(node.id)
                return z3_vars[node.id]
        elif isinstance(node, ast.BinOp):
            left = self._ast_to_z3(node.left, z3_vars)
            right = self._ast_to_z3(node.right, z3_vars)
            if isinstance(node.op, ast.Add):
                return left + right
            elif isinstance(node.op, ast.Sub):
                return left - right
            elif isinstance(node.op, ast.Mult):
                return left * right
            elif isinstance(node.op, ast.Div):
                return left / right
            elif isinstance(node.op, ast.Mod):
                return left % right
            elif isinstance(node.op, ast.Pow):
                return left ** right
        elif isinstance(node, ast.UnaryOp):
            operand = self._ast_to_z3(node.operand, z3_vars)
            if isinstance(node.op, ast.USub):
                return -operand
            elif isinstance(node.op, ast.UAdd):
                return operand
        raise NotImplementedError(f"Unsupported AST node in SMT translation: {type(node).__name__}")
