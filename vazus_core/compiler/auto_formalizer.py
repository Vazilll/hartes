import logging
import re
import time
from dataclasses import dataclass
from typing import List

logger = logging.getLogger(__name__)

try:
    import z3
except ImportError:
    z3 = None


@dataclass
class Constraint:
    name: str
    constraint_type: str
    lhs: str
    rhs: str
    operator: str


@dataclass
class FormalizedSpec:
    original_req: str
    constraints: List[Constraint]
    z3_assertions_str: List[str]
    cel_predicates: List[str]
    verified: bool = False


@dataclass
class VerificationResult:
    sat: bool
    unsat_core: List[str]
    duration_ms: float


class AutoFormalizer:
    def _extract_constraints(self, req: str) -> List[Constraint]:
        constraints = []

        # 1. Implications
        impl_pattern = re.compile(
            r"if\s+([a-zA-Z_]\w*)\s*(<=|>=|==|<|>)\s*(\d+)\s+then\s+([a-zA-Z_]\w*)\s*(<=|>=|==|<|>)\s*(\d+)",
            re.IGNORECASE,
        )
        for match in impl_pattern.finditer(req):
            lhs1, op1, rhs1, lhs2, op2, rhs2 = match.groups()
            constraints.append(
                Constraint(
                    name=f"impl_{lhs1}_{lhs2}",
                    constraint_type="implication",
                    lhs=f"{lhs1} {op1} {rhs1}",
                    rhs=f"{lhs2} {op2} {rhs2}",
                    operator="implies",
                )
            )
        req = impl_pattern.sub("", req)

        # 2. within
        within_pattern = re.compile(r"([a-zA-Z_]\w*)\s*within\s*(\d+)\s*ms", re.IGNORECASE)
        for match in within_pattern.finditer(req):
            lhs, rhs = match.groups()
            constraints.append(
                Constraint(name=f"{lhs}_within", constraint_type="numerical", lhs=lhs, rhs=rhs, operator="<=")
            )
        req = within_pattern.sub("", req)

        # 3. normal numerical
        num_pattern = re.compile(r"([a-zA-Z_]\w*)\s*(<=|>=|==|<|>)\s*(\d+)")
        for match in num_pattern.finditer(req):
            lhs, op, rhs = match.groups()
            constraints.append(
                Constraint(name=f"{lhs}_constraint", constraint_type="numerical", lhs=lhs, rhs=rhs, operator=op)
            )

        return constraints

    def _create_expr(self, var, operator, val):
        if operator == "<=":
            return var <= val
        elif operator == ">=":
            return var >= val
        elif operator == "==":
            return var == val
        elif operator == "<":
            return var < val
        elif operator == ">":
            return var > val
        else:
            raise ValueError(f"Unknown operator: {operator}")

    def _to_z3_assertion(self, c: Constraint, ctx: "z3.Context"):
        if c.constraint_type == "implication":
            lhs_match = re.match(r"([a-zA-Z_]\w*)\s*(<=|>=|==|<|>)\s*(\d+)", c.lhs)
            l_var_name, l_op, l_val = lhs_match.groups()
            l_var = z3.Real(l_var_name, ctx=ctx)
            l_expr = self._create_expr(l_var, l_op, float(l_val))

            rhs_match = re.match(r"([a-zA-Z_]\w*)\s*(<=|>=|==|<|>)\s*(\d+)", c.rhs)
            r_var_name, r_op, r_val = rhs_match.groups()
            r_var = z3.Real(r_var_name, ctx=ctx)
            r_expr = self._create_expr(r_var, r_op, float(r_val))

            return z3.Implies(l_expr, r_expr)
        else:
            var = z3.Real(c.lhs, ctx=ctx)
            rhs_val = float(c.rhs)
            return self._create_expr(var, c.operator, rhs_val)

    def _to_cel_predicate(self, c: Constraint) -> str:
        if c.constraint_type == "implication":
            return f"({c.lhs}) ? ({c.rhs}) : true"
        return f"{c.lhs} {c.operator} {c.rhs}"

    def formalize_requirement(self, req: str) -> FormalizedSpec:
        constraints = self._extract_constraints(req)
        z3_assertions_str = []
        cel_predicates = []

        ctx = z3.Context() if z3 else None
        for c in constraints:
            cel_predicates.append(self._to_cel_predicate(c))
            try:
                if ctx:
                    assertion = self._to_z3_assertion(c, ctx)
                    z3_assertions_str.append(str(assertion))
            except Exception as e:
                logger.error(f"Failed to create z3 assertion: {e}")

        return FormalizedSpec(
            original_req=req,
            constraints=constraints,
            z3_assertions_str=z3_assertions_str,
            cel_predicates=cel_predicates,
        )

    def verify_spec(self, spec: FormalizedSpec) -> VerificationResult:
        start = time.time()
        if not z3:
            raise ImportError("z3 is not available")

        ctx = z3.Context()
        solver = z3.Solver(ctx=ctx)
        solver.set(unsat_core=True)

        for c in spec.constraints:
            try:
                assertion = self._to_z3_assertion(c, ctx)
                solver.assert_and_track(assertion, c.name)
            except Exception as e:
                logger.error(f"Error adding assertion to solver: {e}")

        res = solver.check()
        sat = res == z3.sat
        unsat_core = []
        if res == z3.unsat:
            unsat_core = [str(core) for core in solver.unsat_core()]

        duration_ms = (time.time() - start) * 1000
        spec.verified = sat

        return VerificationResult(sat=sat, unsat_core=unsat_core, duration_ms=duration_ms)
