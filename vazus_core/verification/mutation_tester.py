#!/usr/bin/env python3
"""vazus_core.verification.mutation_tester — Windows-Native AST Mutation Testing Engine."""

import ast
import copy
import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("vazus_core.verification.mutation")


def _exec_mutant_pytest(*pytest_args: str, timeout: int = 15) -> int:
    """Executes pytest for a mutant in workspace sandbox."""
    proc = subprocess.run(
        list(pytest_args),
        capture_output=True,
        text=True,
        cwd="C:/vazus",
        timeout=timeout,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode


class ASTMutator(ast.NodeTransformer):
    """AST Transformer that generates single-point mutations."""

    OP_SWAPS = {
        ast.Add: ast.Sub,
        ast.Sub: ast.Add,
        ast.Mult: ast.FloorDiv,
        ast.FloorDiv: ast.Mult,
        ast.Eq: ast.NotEq,
        ast.NotEq: ast.Eq,
        ast.Lt: ast.GtE,
        ast.LtE: ast.Gt,
        ast.Gt: ast.LtE,
        ast.GtE: ast.Lt,
        ast.And: ast.Or,
        ast.Or: ast.And,
    }

    def __init__(self, target_mutation_index: int):
        self.target_index = target_mutation_index
        self.current_index = 0
        self.mutation_applied = False
        self.mutation_desc = ""

    def visit_BoolOp(self, node: ast.BoolOp) -> ast.AST:
        self.generic_visit(node)
        op_type = type(node.op)
        if op_type in self.OP_SWAPS:
            if self.current_index == self.target_index:
                new_op_type = self.OP_SWAPS[op_type]
                node.op = new_op_type()
                self.mutation_applied = True
                self.mutation_desc = f"BoolOp swap {op_type.__name__} -> {new_op_type.__name__} at L{node.lineno}"
            self.current_index += 1
        return node

    def visit_BinOp(self, node: ast.BinOp) -> ast.AST:
        self.generic_visit(node)
        op_type = type(node.op)
        if op_type in self.OP_SWAPS:
            if self.current_index == self.target_index:
                new_op_type = self.OP_SWAPS[op_type]
                node.op = new_op_type()
                self.mutation_applied = True
                self.mutation_desc = f"BinOp swap {op_type.__name__} -> {new_op_type.__name__} at L{node.lineno}"
            self.current_index += 1
        return node

    def visit_Compare(self, node: ast.Compare) -> ast.AST:
        self.generic_visit(node)
        new_ops = []
        for op in node.ops:
            op_type = type(op)
            if op_type in self.OP_SWAPS:
                if self.current_index == self.target_index:
                    new_op_type = self.OP_SWAPS[op_type]
                    new_ops.append(new_op_type())
                    self.mutation_applied = True
                    self.mutation_desc = f"Compare swap {op_type.__name__} -> {new_op_type.__name__} at L{node.lineno}"
                else:
                    new_ops.append(op)
                self.current_index += 1
            else:
                new_ops.append(op)
        node.ops = new_ops
        return node

    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        if isinstance(node.value, bool):
            if self.current_index == self.target_index:
                node.value = not node.value
                self.mutation_applied = True
                self.mutation_desc = f"Bool invert -> {node.value} at L{node.lineno}"
            self.current_index += 1
        return node


class MutationTester:
    """Evaluates test suite robustness by calculating AST Mutation Score."""

    def __init__(self, workspace_root: str = r"C:\vazus"):
        self.workspace_root = Path(workspace_root).resolve()

    def count_possible_mutations(self, src_code: str) -> int:
        """Counts how many potential mutation sites exist in the AST."""
        try:
            tree = ast.parse(src_code)
            mutator = ASTMutator(target_mutation_index=-1)
            mutator.visit(tree)
            return mutator.current_index
        except Exception:
            return 0

    def generate_mutant_code(self, src_code: str, mutation_index: int) -> Tuple[Optional[str], str]:
        """Generates a mutated version of the source code by index."""
        try:
            tree = ast.parse(src_code)
            mutator = ASTMutator(target_mutation_index=mutation_index)
            mutated_tree = mutator.visit(copy.deepcopy(tree))
            ast.fix_missing_locations(mutated_tree)
            if mutator.mutation_applied:
                return ast.unparse(mutated_tree), mutator.mutation_desc
            return None, ""
        except Exception as e:
            logger.warning("Failed to generate mutant %d: %s", mutation_index, e)
            return None, ""

    def _test_single_mutant(
        self, target_path: Path, test_path: Path, orig_code: str, idx: int, *, pytest_exe: str, timeout: int = 15
    ) -> Optional[Tuple[str, str]]:
        """Applies a single mutation, runs pytest, and restores original code."""
        mutated_code, desc = self.generate_mutant_code(orig_code, idx)
        if not mutated_code:
            return None
        try:
            target_path.write_text(mutated_code, encoding="utf-8")
            rc = _exec_mutant_pytest(pytest_exe, str(test_path), "-q", "--tb=no", timeout=timeout)
            status = "KILLED" if rc != 0 else "SURVIVED"
            return status, desc
        finally:
            target_path.write_text(orig_code, encoding="utf-8")

    def evaluate_mutation_score(
        self, target_file_rel: str, test_file_rel: str, max_mutants: int = 20, timeout_s: int = 15
    ) -> Dict[str, Any]:
        """Runs mutation testing against target file using specified test file."""
        target_path = self.workspace_root / target_file_rel
        test_path = self.workspace_root / test_file_rel
        if not target_path.exists() or not test_path.exists():
            return {"status": "ERROR", "reason": "Target or test file not found"}
        orig_code = target_path.read_text(encoding="utf-8", errors="replace")
        total_possible = self.count_possible_mutations(orig_code)
        if total_possible == 0:
            return {
                "status": "PASS",
                "mutation_score": 1.0,
                "total_mutants": 0,
                "killed_mutants": 0,
                "survived_mutants": 0,
                "details": [],
            }
        num_to_test = min(max_mutants, total_possible)
        killed, survived = 0, 0
        details = []
        pytest_exe = str(self.workspace_root / ".venv" / "Scripts" / "pytest.exe")
        if not os.path.exists(pytest_exe):
            pytest_exe = "pytest"
        for idx in range(num_to_test):
            res = self._test_single_mutant(
                target_path, test_path, orig_code, idx, pytest_exe=pytest_exe, timeout=timeout_s
            )
            if res is None:
                continue
            status, desc = res
            if status == "KILLED":
                killed += 1
            else:
                survived += 1
            details.append({"index": idx, "description": desc, "status": status})
        total_tested = killed + survived
        score = (killed / total_tested) if total_tested > 0 else 1.0
        return {
            "status": "SUCCESS",
            "target_file": target_file_rel,
            "test_file": test_file_rel,
            "mutation_score": round(score, 3),
            "mutation_score_pct": f"{round(score * 100, 1)}%",
            "total_tested": total_tested,
            "killed_mutants": killed,
            "survived_mutants": survived,
            "details": details,
        }
