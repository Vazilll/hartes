"""
vazus_autonomous_harness.verification.smt_prover — SMT Z3 Formal Equivalence & Contract Prover.

Milestone 1 (F2):
- Microsoft Z3 5.0.0 symbolic theorem proving engine.
- Extracts and parses docstring contracts (:requires:, :ensures:, @requires, @ensures).
- Proves UNSAT (precondition ∧ ¬postcondition is unsatisfiable).
- Extracts concrete counterexample models when SAT.
- Verifies AST function and expression functional equivalence (∀ x: f1(x) == f2(x)).
- Anti-vacuous proof filter (rejects trivial tautologies).
- Memory safety and buffer bounds formal verification.
"""

import ast
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import z3

logger = logging.getLogger("vazus.harness.verification.smt")


@dataclass
class SMTProofResult:
    """Structured verdict from formal SMT Z3 verification."""
    verified: bool
    status: str  # "UNSAT", "SAT", "UNKNOWN", "NO_CONTRACTS", "VACUOUS_CONTRACT", "SYNTAX_ERROR", "ERROR"
    counterexample: Optional[Dict[str, Any]] = None
    details: str = ""
    structured_details: Optional[List[Dict[str, Any]]] = None

    @property
    def is_valid(self) -> bool:
        return self.verified

    def __getitem__(self, key: str) -> Any:
        if key in ("status", "solver_status", "smt_solver_status"):
            return self.status
        if key in ("equivalent", "is_valid", "valid"):
            return self.verified
        if key == "counterexample":
            return self.counterexample
        if key == "details":
            return self.details
        if hasattr(self, key):
            return getattr(self, key)
        raise KeyError(key)

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key) or key in ("status", "equivalent", "counterexample", "details")


def _coerce_sorts(left: Any, right: Any) -> tuple[Any, Any]:
    """Coerces mixed Int and Real sorts in Z3 expressions to Real."""
    if hasattr(left, "is_real") and hasattr(right, "is_real"):
        if left.is_real() and not right.is_real():
            right = z3.ToReal(right)
        elif right.is_real() and not left.is_real():
            left = z3.ToReal(left)
    return left, right


def _ast_to_z3(
    node: ast.AST,
    z3_vars: Dict[str, Any],
    type_hints: Optional[Dict[str, str]] = None
) -> Any:
    """Recursively translates an AST arithmetic/value node into a Z3 symbolic expression."""
    type_hints = type_hints or {}

    if isinstance(node, ast.Name):
        if node.id not in z3_vars:
            hint = type_hints.get(node.id, "int")
            if hint == "float":
                z3_vars[node.id] = z3.Real(node.id)
            elif hint == "bool":
                z3_vars[node.id] = z3.Bool(node.id)
            else:
                z3_vars[node.id] = z3.Int(node.id)
        return z3_vars[node.id]

    elif isinstance(node, ast.Constant):
        if isinstance(node.value, bool):
            return z3.BoolVal(node.value)
        elif isinstance(node.value, float):
            return z3.RealVal(node.value)
        elif isinstance(node.value, int):
            return z3.IntVal(node.value)
        elif node.value is None:
            return z3.IntVal(0)

    elif isinstance(node, ast.BinOp):
        left = _ast_to_z3(node.left, z3_vars, type_hints)
        right = _ast_to_z3(node.right, z3_vars, type_hints)
        left, right = _coerce_sorts(left, right)

        if isinstance(node.op, ast.Add):
            return left + right
        elif isinstance(node.op, ast.Sub):
            return left - right
        elif isinstance(node.op, ast.Mult):
            return left * right
        elif isinstance(node.op, ast.Div):
            left_r = z3.ToReal(left) if hasattr(left, "is_real") and not left.is_real() else left
            right_r = z3.ToReal(right) if hasattr(right, "is_real") and not right.is_real() else right
            return left_r / right_r
        elif isinstance(node.op, ast.FloorDiv):
            return left / right
        elif isinstance(node.op, ast.Mod):
            return left % right
        elif isinstance(node.op, ast.Pow):
            return left ** right
        elif isinstance(node.op, ast.BitAnd):
            return left & right if hasattr(left, "__and__") else left
        elif isinstance(node.op, ast.BitOr):
            return left | right if hasattr(left, "__or__") else left
        elif isinstance(node.op, ast.BitXor):
            return left ^ right if hasattr(left, "__xor__") else left

    elif isinstance(node, ast.UnaryOp):
        operand = _ast_to_z3(node.operand, z3_vars, type_hints)
        if isinstance(node.op, ast.USub):
            return -operand
        elif isinstance(node.op, ast.UAdd):
            return operand
        elif isinstance(node.op, ast.Not):
            return z3.Not(_parse_expr_to_z3(node.operand, z3_vars, type_hints))

    elif isinstance(node, ast.IfExp):
        cond = _parse_expr_to_z3(node.test, z3_vars, type_hints)
        body = _ast_to_z3(node.body, z3_vars, type_hints)
        orelse = _ast_to_z3(node.orelse, z3_vars, type_hints)
        body, orelse = _coerce_sorts(body, orelse)
        return z3.If(cond, body, orelse)

    elif isinstance(node, ast.Call):
        func_name = getattr(node.func, "id", None)
        if func_name == "abs" and len(node.args) == 1:
            arg = _ast_to_z3(node.args[0], z3_vars, type_hints)
            zero = z3.RealVal(0.0) if hasattr(arg, "is_real") and arg.is_real() else z3.IntVal(0)
            return z3.If(arg >= zero, arg, -arg)
        elif func_name == "min" and len(node.args) == 2:
            a = _ast_to_z3(node.args[0], z3_vars, type_hints)
            b = _ast_to_z3(node.args[1], z3_vars, type_hints)
            a, b = _coerce_sorts(a, b)
            return z3.If(a <= b, a, b)
        elif func_name == "max" and len(node.args) == 2:
            a = _ast_to_z3(node.args[0], z3_vars, type_hints)
            b = _ast_to_z3(node.args[1], z3_vars, type_hints)
            a, b = _coerce_sorts(a, b)
            return z3.If(a >= b, a, b)

    raise ValueError(f"Unsupported AST node for Z3 conversion: {type(node).__name__}")


def _parse_expr_to_z3(
    node: ast.AST,
    z3_vars: Dict[str, Any],
    type_hints: Optional[Dict[str, str]] = None
) -> Any:
    """Translates an AST comparison/boolean expression into a Z3 boolean formula."""
    type_hints = type_hints or {}

    if isinstance(node, ast.Compare):
        left = _ast_to_z3(node.left, z3_vars, type_hints)
        z3_ops = []
        curr_left = left

        for op, comp in zip(node.ops, node.comparators):
            right = _ast_to_z3(comp, z3_vars, type_hints)
            curr_left, right = _coerce_sorts(curr_left, right)

            if isinstance(op, ast.GtE):
                sub_expr = (curr_left >= right)
            elif isinstance(op, ast.Gt):
                sub_expr = (curr_left > right)
            elif isinstance(op, ast.LtE):
                sub_expr = (curr_left <= right)
            elif isinstance(op, ast.Lt):
                sub_expr = (curr_left < right)
            elif isinstance(op, ast.Eq):
                sub_expr = (curr_left == right)
            elif isinstance(op, ast.NotEq):
                sub_expr = (curr_left != right)
            else:
                raise ValueError(f"Unsupported comparison operator: {type(op).__name__}")

            z3_ops.append(sub_expr)
            curr_left = right

        return z3.And(*z3_ops) if len(z3_ops) > 1 else z3_ops[0]

    elif isinstance(node, ast.BoolOp):
        vals = [_parse_expr_to_z3(v, z3_vars, type_hints) for v in node.values]
        if isinstance(node.op, ast.And):
            return z3.And(*vals)
        elif isinstance(node.op, ast.Or):
            return z3.Or(*vals)

    elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return z3.Not(_parse_expr_to_z3(node.operand, z3_vars, type_hints))

    elif isinstance(node, ast.Constant) and isinstance(node.value, bool):
        return z3.BoolVal(node.value)

    return _ast_to_z3(node, z3_vars, type_hints)


def _extract_return_from_body(
    body_stmts: List[ast.stmt],
    z3_vars: Dict[str, Any],
    type_hints: Optional[Dict[str, str]] = None
) -> Any:
    """Extracts the symbolic return expression from a sequence of AST statements."""
    for idx, stmt in enumerate(body_stmts):
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name):
                    try:
                        val_z3 = _ast_to_z3(stmt.value, z3_vars, type_hints)
                        z3_vars[target.id] = val_z3
                    except Exception as exc:
                        logger.debug("AST assignment to Z3 value conversion skipped for %s: %s", target.id, exc)
        elif isinstance(stmt, ast.Return) and stmt.value:
            try:
                return _parse_expr_to_z3(stmt.value, z3_vars, type_hints)
            except Exception:
                return _ast_to_z3(stmt.value, z3_vars, type_hints)
        elif isinstance(stmt, ast.If):
            test_z3 = _parse_expr_to_z3(stmt.test, z3_vars, type_hints)
            then_ret = _extract_return_from_body(stmt.body, z3_vars, type_hints)
            else_ret = _extract_return_from_body(stmt.orelse, z3_vars, type_hints)
            if then_ret is not None and else_ret is not None:
                then_ret, else_ret = _coerce_sorts(then_ret, else_ret)
                return z3.If(test_z3, then_ret, else_ret)
            elif then_ret is not None:
                remaining_ret = _extract_return_from_body(body_stmts[idx + 1:], z3_vars, type_hints)
                if remaining_ret is not None:
                    then_ret, remaining_ret = _coerce_sorts(then_ret, remaining_ret)
                    return z3.If(test_z3, then_ret, remaining_ret)
                return then_ret
    return None


def _format_model_val(val: Any) -> Any:
    """Converts a Z3 model evaluation into a native Python scalar."""
    if hasattr(val, "as_long"):
        return val.as_long()
    elif hasattr(val, "as_decimal"):
        return float(val.as_decimal(5))
    elif hasattr(val, "as_fraction"):
        return float(val.as_fraction())
    elif hasattr(val, "is_true"):
        return True if val.is_true() else False
    return str(val)


class SMTProver:
    """
    Microsoft Z3 SMT Formal Contract & Equivalence Prover.
    Implements formal verification (F2) for Autonomous Absolute AI Flywheel.
    """

    def __init__(self, timeout_ms: int = 5000):
        self.timeout_ms = timeout_ms

    def verify_contracts(self, code: str) -> SMTProofResult:
        """
        Parses Python code, extracts docstring contracts (:requires:, :ensures:),
        and mathematically proves satisfaction (UNSAT) or extracts counterexamples (SAT).
        """
        if not code or not code.strip():
            return SMTProofResult(
                verified=True,
                status="NO_CONTRACTS",
                details="Empty code snippet provided."
            )

        try:
            tree = ast.parse(code)
        except SyntaxError as se:
            return SMTProofResult(
                verified=False,
                status="SYNTAX_ERROR",
                details=f"Syntax Error: {se}"
            )

        functions_checked = 0
        all_structured = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                docstring = ast.get_docstring(node) or ""
                requires = re.findall(r"[@:]requires:?\s*(.+)", docstring)
                ensures = re.findall(r"[@:]ensures:?\s*(.+)", docstring)

                if not (requires or ensures):
                    continue

                functions_checked += 1
                result = self._verify_single_function_contract(node, requires, ensures)
                all_structured.append({
                    "function": node.name,
                    "result": result
                })

                if not result.verified:
                    return result

        if functions_checked > 0:
            return SMTProofResult(
                verified=True,
                status="UNSAT",
                details=f"All {functions_checked} formal function contract(s) proved mathematically sound (UNSAT).",
                structured_details=all_structured
            )

        return SMTProofResult(
            verified=True,
            status="NO_CONTRACTS",
            details="No formal :requires:/:ensures: docstring contracts found in AST."
        )

    def _verify_single_function_contract(
        self,
        node: ast.FunctionDef,
        requires: List[str],
        ensures: List[str]
    ) -> SMTProofResult:
        """Verifies formal contracts for a single AST FunctionDef node."""
        # Anti-vacuous contract checks
        for ens in ensures:
            cleaned = ens.strip().lower()
            if cleaned in ("true", "1 == 1", "0 == 0", "true == true"):
                return SMTProofResult(
                    verified=False,
                    status="VACUOUS_CONTRACT",
                    details=f"Tautological vacuous postcondition ':ensures: {ens}' rejected."
                )

        for req in requires:
            cleaned = req.strip().lower()
            if cleaned in ("false", "1 == 0", "0 == 1"):
                return SMTProofResult(
                    verified=False,
                    status="VACUOUS_CONTRACT",
                    details=f"Contradictory vacuous precondition ':requires: {req}' rejected."
                )

        try:
            z3_vars: Dict[str, Any] = {}
            for arg in node.args.args:
                # Infer type annotation if available
                ann = getattr(arg, "annotation", None)
                ann_id = getattr(ann, "id", "") if ann else ""
                if ann_id == "float":
                    z3_vars[arg.arg] = z3.Real(arg.arg)
                elif ann_id == "bool":
                    z3_vars[arg.arg] = z3.Bool(arg.arg)
                else:
                    z3_vars[arg.arg] = z3.Int(arg.arg)

            result_z3 = _extract_return_from_body(node.body, z3_vars)
            if result_z3 is None:
                ret_node = next((n for n in ast.walk(node) if isinstance(n, ast.Return) and n.value), None)
                if ret_node:
                    result_z3 = _ast_to_z3(ret_node.value, z3_vars)
            if result_z3 is None:
                result_z3 = z3.Int("result")

            z3_vars["result"] = result_z3

            # 1. Z3-based precondition satisfiability check (anti-vacuous contract check)
            if requires:
                pre_solver = z3.Solver()
                pre_solver.set("timeout", self.timeout_ms)
                for req in requires:
                    req_ast = ast.parse(req.strip(), mode="eval").body
                    pre_solver.add(_parse_expr_to_z3(req_ast, z3_vars))
                if pre_solver.check() == z3.unsat:
                    return SMTProofResult(
                        verified=False,
                        status="VACUOUS_CONTRACT",
                        details=f"Preconditions are unsatisfiable (contradictory) in Z3 for function '{node.name}'."
                    )

            # 2. Z3-based tautology check on postconditions (identity tautology rejection)
            if ensures:
                taut_vars: Dict[str, Any] = {}
                for arg in node.args.args:
                    ann = getattr(arg, "annotation", None)
                    ann_id = getattr(ann, "id", "") if ann else ""
                    if ann_id == "float":
                        taut_vars[arg.arg] = z3.Real(arg.arg)
                    elif ann_id == "bool":
                        taut_vars[arg.arg] = z3.Bool(arg.arg)
                    else:
                        taut_vars[arg.arg] = z3.Int(arg.arg)
                taut_vars["result"] = z3.Int("result")

                for ens in ensures:
                    ens_ast = ast.parse(ens.strip(), mode="eval").body
                    ens_taut_z3 = _parse_expr_to_z3(ens_ast, taut_vars)
                    taut_solver = z3.Solver()
                    taut_solver.set("timeout", self.timeout_ms)
                    taut_solver.add(z3.Not(ens_taut_z3))
                    if taut_solver.check() == z3.unsat:
                        return SMTProofResult(
                            verified=False,
                            status="VACUOUS_CONTRACT",
                            details=f"Tautological identity postcondition ':ensures: {ens}' is universally valid (identity tautology) in Z3."
                        )

                if len(ensures) > 1:
                    all_ens_z3 = []
                    for ens in ensures:
                        ens_ast = ast.parse(ens.strip(), mode="eval").body
                        all_ens_z3.append(_parse_expr_to_z3(ens_ast, taut_vars))
                    conj_taut = z3.And(*all_ens_z3)
                    taut_solver = z3.Solver()
                    taut_solver.set("timeout", self.timeout_ms)
                    taut_solver.add(z3.Not(conj_taut))
                    if taut_solver.check() == z3.unsat:
                        return SMTProofResult(
                            verified=False,
                            status="VACUOUS_CONTRACT",
                            details="Tautological identity postcondition conjunction is universally valid in Z3."
                        )

            solver = z3.Solver()
            solver.set("timeout", self.timeout_ms)

            # Add preconditions: P(x)
            for req in requires:
                req_ast = ast.parse(req.strip(), mode="eval").body
                solver.add(_parse_expr_to_z3(req_ast, z3_vars))

            # Add negation of postconditions: ¬Q(x, result)
            ensures_z3_list = []
            for ens in ensures:
                ens_ast = ast.parse(ens.strip(), mode="eval").body
                ensures_z3_list.append(_parse_expr_to_z3(ens_ast, z3_vars))

            if ensures_z3_list:
                postcondition = z3.And(*ensures_z3_list) if len(ensures_z3_list) > 1 else ensures_z3_list[0]
                solver.add(z3.Not(postcondition))

            check_res = solver.check()
            if check_res == z3.unsat:
                return SMTProofResult(
                    verified=True,
                    status="UNSAT",
                    details=f"Function '{node.name}' contract proved UNSAT (no counterexamples exist)."
                )
            elif check_res == z3.sat:
                model = solver.model()
                counterexample = {}
                for var_name, z3_var in z3_vars.items():
                    if var_name == "result":
                        continue
                    try:
                        m_val = model.eval(z3_var, model_completion=True)
                        counterexample[var_name] = _format_model_val(m_val)
                    except Exception as exc:
                        logger.debug("Failed to evaluate variable %s in model: %s", var_name, exc)
                return SMTProofResult(
                    verified=False,
                    status="SAT",
                    counterexample=counterexample,
                    details=f"Contract violation found for function '{node.name}'."
                )
            elif check_res == z3.unknown:
                return SMTProofResult(
                    verified=False,
                    status="UNKNOWN",
                    details=f"Solver returned UNKNOWN or timed out for function '{node.name}'."
                )
            return SMTProofResult(
                verified=False,
                status="ERROR",
                details=f"Unexpected solver result: {check_res}"
            )
        except Exception as e:
            logger.warning("SMT verification exception in '%s': %s", node.name, e)
            return SMTProofResult(
                verified=False,
                status="ERROR",
                details=f"SMT translation error in '{node.name}': {e}"
            )

    def verify_functional_equivalence(
        self,
        code1: str,
        code2: str,
        func_name: Optional[str] = None
    ) -> SMTProofResult:
        """
        Mathematically proves whether two functions are functionally equivalent:
        ∀ x: f1(x) == f2(x)
        Returns UNSAT when equivalent, SAT with counterexample when divergent.
        """
        if code1.strip() == code2.strip():
            return SMTProofResult(
                verified=True,
                status="UNSAT",
                details="Identical source code is trivially functionally equivalent (UNSAT)."
            )

        try:
            tree1 = ast.parse(code1)
            tree2 = ast.parse(code2)
        except SyntaxError as se:
            return SMTProofResult(
                verified=False,
                status="SYNTAX_ERROR",
                details=f"Syntax Error in equivalence input: {se}"
            )

        fn1 = next((n for n in ast.walk(tree1) if isinstance(n, ast.FunctionDef) and (not func_name or n.name == func_name)), None)
        fn2 = next((n for n in ast.walk(tree2) if isinstance(n, ast.FunctionDef) and (not func_name or n.name == func_name)), None)

        if not fn1 or not fn2:
            return SMTProofResult(
                verified=True,
                status="NO_FUNCTIONS",
                details="No matching function definitions found to compare equivalence."
            )

        try:
            args1 = [a.arg for a in fn1.args.args]
            args2 = [a.arg for a in fn2.args.args]
            if len(args1) != len(args2):
                return SMTProofResult(
                    verified=False,
                    status="SAT",
                    counterexample={"reason": "Argument count mismatch"},
                    details=f"Function argument counts differ ({len(args1)} vs {len(args2)})."
                )

            # Symbolic variables for arguments
            z3_vars1 = {arg: z3.Int(arg) for arg in args1}
            # Map args2 to the same symbolic variables as args1
            z3_vars2 = {arg2: z3_vars1[arg1] for arg1, arg2 in zip(args1, args2)}

            ret1 = _extract_return_from_body(fn1.body, z3_vars1)
            ret2 = _extract_return_from_body(fn2.body, z3_vars2)

            if ret1 is None or ret2 is None:
                return SMTProofResult(
                    verified=False,
                    status="ERROR",
                    details="Could not extract return expressions for both functions."
                )

            ret1, ret2 = _coerce_sorts(ret1, ret2)

            solver = z3.Solver()
            solver.set("timeout", self.timeout_ms)
            solver.add(ret1 != ret2)

            check_res = solver.check()
            if check_res == z3.unsat:
                return SMTProofResult(
                    verified=True,
                    status="UNSAT",
                    details=f"Functions '{fn1.name}' and '{fn2.name}' are functionally equivalent (UNSAT)."
                )
            elif check_res == z3.sat:
                model = solver.model()
                counterexample = {}
                for arg in args1:
                    try:
                        m_val = model.eval(z3_vars1[arg], model_completion=True)
                        counterexample[arg] = _format_model_val(m_val)
                    except Exception:
                        counterexample[arg] = str(model.eval(z3_vars1[arg]))
                return SMTProofResult(
                    verified=False,
                    status="SAT",
                    counterexample=counterexample,
                    details=f"Functions '{fn1.name}' and '{fn2.name}' diverge on inputs."
                )
            elif check_res == z3.unknown:
                return SMTProofResult(
                    verified=False,
                    status="UNKNOWN",
                    details="Solver returned UNKNOWN or timed out during equivalence check."
                )
            return SMTProofResult(
                verified=False,
                status="ERROR",
                details=f"Unexpected solver result: {check_res}"
            )
        except Exception as e:
            logger.warning("Equivalence proof error: %s", e)
            return SMTProofResult(
                verified=False,
                status="ERROR",
                details=f"Equivalence proof error: {e}"
            )

    def verify_expression_equivalence(
        self,
        expr1: str,
        expr2: str,
        variable_names: List[str]
    ) -> Dict[str, Any]:
        """
        Drop-in compatible method for SMTEquivalenceProver.
        Proves whether expr1 == expr2 for all continuous/discrete domain inputs.
        """
        solver = z3.Solver()
        solver.set("timeout", self.timeout_ms)

        z3_vars = {name: z3.Real(name) for name in variable_names}

        try:
            z3_expr1 = _ast_to_z3(ast.parse(expr1, mode="eval").body, z3_vars)
            z3_expr2 = _ast_to_z3(ast.parse(expr2, mode="eval").body, z3_vars)
            z3_expr1, z3_expr2 = _coerce_sorts(z3_expr1, z3_expr2)

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
            logger.warning("SMT translation error for '%s' vs '%s': %s", expr1, expr2, e)
            return {
                "equivalent": False,
                "status": "TRANSLATION_ERROR",
                "error": str(e)
            }

    def verify_memory_safety(self, offset: int, length: int, capacity: int) -> SMTProofResult:
        """
        Formally verifies buffer bounds safety:
        offset >= 0 and length >= 0 and offset + length <= capacity.
        """
        solver = z3.Solver()
        solver.set("timeout", self.timeout_ms)

        o = z3.IntVal(offset)
        l = z3.IntVal(length)
        c = z3.IntVal(capacity)

        # Invariant to prove: (o >= 0 ∧ l >= 0 ∧ o + l <= c)
        safe_condition = z3.And(o >= 0, l >= 0, (o + l) <= c)
        solver.add(z3.Not(safe_condition))

        check_res = solver.check()
        if check_res == z3.unsat:
            return SMTProofResult(
                verified=True,
                status="UNSAT",
                details="Memory bounds proven safe (UNSAT): 0 <= offset and 0 <= length and offset + length <= capacity."
            )
        else:
            return SMTProofResult(
                verified=False,
                status="SAT",
                counterexample={
                    "offset": offset,
                    "length": length,
                    "capacity": capacity,
                    "violation": "Buffer overflow" if (offset + length > capacity) else "Negative bounds violation"
                },
                details="Memory safety bounds violated."
            )


# Backward-compatible alias
class SMTEquivalenceProver(SMTProver):
    """Alias for SMTEquivalenceProver preserving legacy interface."""
    pass
