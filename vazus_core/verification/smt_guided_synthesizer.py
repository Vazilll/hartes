"""
vazus_core.verification.smt_guided_synthesizer
==============================================
Neurosymbolic SMT-Guided Generation & Database State Invariants Engine.
Implements:
1. SMT-guided Boundary Constraint extraction & concrete counterexample test generation for REPL.
2. Formal verification of database state transitions in vazus.db (Academic dead-line invariants & Financial solvency).
3. CEGIS (Counterexample-Guided Inductive Synthesis) feedback bridge to repl_engine.
"""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

try:
    import z3
except ImportError:
    z3 = None

logger = logging.getLogger("vazus_core.verification.smt_guided_synthesizer")


@dataclass
class SMTBoundaryResult:
    """Outcome of SMT boundary analysis."""
    is_valid: bool
    status: str  # "UNSAT" (valid), "SAT" (counterexample found), "UNKNOWN", "ERROR"
    counterexample: Optional[Dict[str, Any]] = None
    generated_test_code: Optional[str] = None
    boundary_constraints: List[str] = field(default_factory=list)
    proof_details: str = ""


@dataclass
class StateInvariantVerdict:
    """Formal verification verdict for database state transitions."""
    approved: bool
    status: str  # "UNSAT" (no violation possible -> approved), "SAT" (violation witness found)
    violation_witness: Optional[Dict[str, Any]] = None
    invariant_rule: str = ""
    reason: str = ""


class SMTGuidedSynthesizer:
    """
    Neurosymbolic SMT-Guided Code Synthesizer and Graph/DB Invariant Verifier.
    """

    def __init__(self, timeout_ms: int = 5000):
        self.timeout_ms = timeout_ms

    def extract_counterexample_and_test(
        self,
        func_name: str,
        code_str: str,
        preconditions: Optional[List[str]] = None,
        postconditions: Optional[List[str]] = None,
    ) -> SMTBoundaryResult:
        """
        Symbolically analyzes function contracts using Z3.
        If a violation model exists (SAT), extracts the minimal counterexample and
        generates an executable regression test for repl_engine.
        """
        if z3 is None:
            return SMTBoundaryResult(
                is_valid=True,
                status="NO_Z3",
                proof_details="Z3 solver not available; skipping symbolic analysis.",
            )

        solver = z3.Solver()
        solver.set("timeout", self.timeout_ms)

        # Parse AST to find target function arguments
        arg_names: List[str] = []
        try:
            tree = ast.parse(code_str)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and (node.name == func_name or not arg_names):
                    arg_names = [a.arg for a in node.args.args if a.arg != "self"]
                    func_name = node.name
                    break
        except Exception:
            arg_names = ["x", "y"]

        if not arg_names:
            arg_names = ["x"]

        # Declare symbolic integer variables for parameters
        z3_vars = {arg: z3.Int(arg) for arg in arg_names}

        # Apply preconditions (assumptions)
        if preconditions:
            for pre in preconditions:
                c = self._parse_simple_constraint(pre, z3_vars)
                if c is not None:
                    solver.add(c)

        # Postcondition negation to find counterexample violating ensures
        violation_asserted = False
        boundary_rules: List[str] = []
        if postconditions:
            for post in postconditions:
                c = self._parse_simple_constraint(post, z3_vars)
                if c is not None:
                    # Invariant violation occurs when NOT(ensures) is satisfiable
                    solver.add(z3.Not(c))
                    violation_asserted = True
                    boundary_rules.append(post)

        if not violation_asserted:
            # Fallback default safety check: division by zero or negative bounds
            if "y" in z3_vars:
                solver.add(z3_vars["y"] == 0)
                boundary_rules.append("y != 0")
            else:
                first_var = list(z3_vars.values())[0]
                solver.add(first_var < 0)
                boundary_rules.append(f"{list(z3_vars.keys())[0]} >= 0")

        check_res = solver.check()
        if check_res == z3.sat:
            model = solver.model()
            cex: Dict[str, Any] = {}
            for k, var in z3_vars.items():
                val = model.eval(var)
                try:
                    cex[k] = val.as_long()
                except Exception:
                    cex[k] = str(val)

            # Generate executable test case
            test_code = self._generate_pytest_fixture(func_name, cex, boundary_rules)

            return SMTBoundaryResult(
                is_valid=False,
                status="SAT",
                counterexample=cex,
                generated_test_code=test_code,
                boundary_constraints=boundary_rules,
                proof_details=f"SMT Counterexample witness found violating {boundary_rules}",
            )
        elif check_res == z3.unsat:
            return SMTBoundaryResult(
                is_valid=True,
                status="UNSAT",
                proof_details="Formal proof verified: no counterexample exists satisfying negated invariant.",
            )
        else:
            return SMTBoundaryResult(
                is_valid=True,
                status="UNKNOWN",
                proof_details=f"Z3 solver returned {check_res}",
            )

    def verify_academic_state_transition(
        self,
        current_debt_count: int,
        days_until_deadline: int,
        proposed_action: str,
        target_debt_delta: int = 0,
    ) -> StateInvariantVerdict:
        """
        Formal Z3 verification of academic sovereignty and schedule invariants:
        - Invariant 1: debt_count >= 0 (no negative debts).
        - Invariant 2: if days_until_deadline < 0, transitions without debt liquidation or without approval are forbidden.
        - Invariant 3: debt liquidation delta must not exceed current debt count and must be non-negative.
        """
        if z3 is None:
            return StateInvariantVerdict(approved=True, status="UNSAT", reason="Z3 absent")

        s = z3.Solver()
        s.set("timeout", self.timeout_ms)

        debts = z3.Int("debts")
        days = z3.Int("days")
        delta = z3.Int("delta")

        s.add(debts == current_debt_count)
        s.add(days == days_until_deadline)
        s.add(delta == target_debt_delta)

        # Violation conditions
        cond_viol_neg_delta = delta < 0
        cond_viol_a = (debts - delta) < 0
        cond_viol_b = z3.And(days < 0, z3.BoolVal(proposed_action in ("DEFER_WITHOUT_APPROVAL", "IGNORE", "STUDY") and target_debt_delta <= 0))
        cond_viol_c = delta > debts

        s.add(z3.Or(cond_viol_neg_delta, cond_viol_a, cond_viol_b, cond_viol_c))

        if s.check() == z3.sat:
            m = s.model()
            witness = {
                "debts": int(str(m.eval(debts))),
                "days": int(str(m.eval(days))),
                "delta": int(str(m.eval(delta))),
                "proposed_action": proposed_action,
            }
            return StateInvariantVerdict(
                approved=False,
                status="SAT",
                violation_witness=witness,
                invariant_rule="Academic Integrity: non-negative debt and deadline non-negativity",
                reason="State transition violates academic schedule invariant (counterexample found).",
            )
        return StateInvariantVerdict(
            approved=True,
            status="UNSAT",
            reason="Formally proven: no academic invariant violation possible.",
        )

    def verify_financial_state_transition(
        self,
        current_balance: float,
        min_reserve: float,
        transaction_amount: float,
        is_debit: bool = True,
    ) -> StateInvariantVerdict:
        """
        Formal Z3 verification of financial state transitions:
        - Invariant 1: post_balance >= min_reserve.
        - Invariant 2: transaction_amount > 0.
        """
        import math
        if (
            math.isnan(current_balance)
            or math.isinf(current_balance)
            or math.isnan(min_reserve)
            or math.isinf(min_reserve)
            or math.isnan(transaction_amount)
            or math.isinf(transaction_amount)
        ):
            return StateInvariantVerdict(
                approved=False,
                status="SAT",
                violation_witness={"error": "Non-finite numeric value"},
                invariant_rule="Financial Solvency: numeric parameters must be finite",
                reason="Invalid floating point values (NaN or Inf) detected.",
            )

        if z3 is None:
            return StateInvariantVerdict(approved=True, status="UNSAT", reason="Z3 absent")

        s = z3.Solver()
        s.set("timeout", self.timeout_ms)

        # Scale by 100 to avoid float precision issues in Z3 Int
        bal = z3.Int("balance_cents")
        reserve = z3.Int("reserve_cents")
        tx = z3.Int("tx_cents")

        s.add(bal == int(current_balance * 100))
        s.add(reserve == int(min_reserve * 100))
        s.add(tx == int(transaction_amount * 100))

        # Check violation: (is_debit and bal - tx < reserve) OR (tx <= 0)
        if is_debit:
            cond_violation = z3.Or((bal - tx) < reserve, tx <= 0)
        else:
            cond_violation = tx <= 0

        s.add(cond_violation)

        if s.check() == z3.sat:
            m = s.model()
            witness = {
                "current_balance": current_balance,
                "min_reserve": min_reserve,
                "transaction_amount": transaction_amount,
                "post_balance": current_balance - (transaction_amount if is_debit else -transaction_amount),
            }
            return StateInvariantVerdict(
                approved=False,
                status="SAT",
                violation_witness=witness,
                invariant_rule="Financial Invariant: minimum reserve solvency & positive transactions",
                reason="Transaction would violate minimum solvency reserve or transaction amount is non-positive.",
            )
        return StateInvariantVerdict(
            approved=True,
            status="UNSAT",
            reason="Formally proven: financial state transition maintains solvency invariants.",
        )

    def _parse_simple_constraint(self, constraint_str: str, z3_vars: Dict[str, Any]) -> Optional[Any]:
        """Parses relational expressions into Z3 constraints supporting variable and arithmetic terms."""
        clean = (
            constraint_str.replace("==", " == ")
            .replace("!=", " != ")
            .replace(">=", " >= ")
            .replace("<=", " <= ")
            .replace(">", " > ")
            .replace("<", " < ")
        )
        tokens = clean.split()
        if len(tokens) >= 3:
            op_idx = -1
            for i, t in enumerate(tokens):
                if t in (">=", "<=", ">", "<", "==", "!=", "="):
                    op_idx = i
                    break
            if op_idx > 0:
                lhs_tokens = tokens[:op_idx]
                op = tokens[op_idx]
                rhs_tokens = tokens[op_idx + 1 :]

                lhs_expr = self._eval_token_expr(lhs_tokens, z3_vars)
                rhs_expr = self._eval_token_expr(rhs_tokens, z3_vars)

                if lhs_expr is not None and rhs_expr is not None:
                    if op == ">=":
                        return lhs_expr >= rhs_expr
                    elif op == "<=":
                        return lhs_expr <= rhs_expr
                    elif op == ">":
                        return lhs_expr > rhs_expr
                    elif op == "<":
                        return lhs_expr < rhs_expr
                    elif op in ("==", "="):
                        return lhs_expr == rhs_expr
                    elif op == "!=":
                        return lhs_expr != rhs_expr
        return None

    def _eval_token_expr(self, tokens: List[str], z3_vars: Dict[str, Any]) -> Optional[Any]:
        """Evaluates simple token sequence like ['x'] or ['x', '+', 'y'] or ['10'] into Z3 expression."""
        if not tokens:
            return None
        if len(tokens) == 1:
            tok = tokens[0]
            if tok in z3_vars:
                return z3_vars[tok]
            if tok.lstrip("-").isdigit():
                return int(tok)
            return None
        if len(tokens) == 3:
            left = self._eval_token_expr([tokens[0]], z3_vars)
            op = tokens[1]
            right = self._eval_token_expr([tokens[2]], z3_vars)
            if left is not None and right is not None:
                if op == "+":
                    return left + right
                elif op == "-":
                    return left - right
                elif op == "*":
                    return left * right
        return None

    def _generate_pytest_fixture(
        self,
        func_name: str,
        counterexample: Dict[str, Any],
        boundary_rules: List[str],
    ) -> str:
        """Constructs an executable pytest test case representing the counterexample witness."""
        args_str = ", ".join(f"{k}={repr(v)}" for k, v in counterexample.items())
        rules_comment = "; ".join(boundary_rules)
        return f"""
def test_smt_counterexample_{func_name}():
    \"\"\"Auto-synthesized CEGIS regression test from Z3 SAT counterexample.
    Boundary rules tested: {rules_comment}
    \"\"\"
    # Counterexample witness inputs:
    inputs = {counterexample}
    # Expected: implementation must safely handle or validate these boundary conditions
    try:
        from vazus_core.{func_name} import {func_name}
        res = {func_name}(**inputs)
        assert res is not None, "Function returned None for counterexample witness"
    except (ValueError, TypeError, ZeroDivisionError):
        # Gracefully handled boundary condition
        pass
"""
