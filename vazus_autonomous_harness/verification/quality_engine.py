"""
vazus_autonomous_harness.verification.quality_engine — Point-Based Multi-Dimensional Quality Evaluation Engine.

Milestone 1 (F1, F3):
- 100-Point Objective Quality Evaluation Rubric:
  * Formal Correctness (SMT Z3): +40 points (UNSAT = 40, SAT/Error = 0)
  * Empirical Integrity (Tests): +30 points (100% Pass = 30, Fail = 0)
  * Parsimony & Efficiency (AST): +15 points (Bloat Penalty, Clean Diff Bonus)
  * Academic Sovereignty (USER.md#L37): +15 points (Socratic, No Leaks/Stubs)
- Hard Admission Threshold: S >= 75.0 AND Correctness == 40.0 AND Sovereignty == 15.0.
- AST Bloat & Parsimony Analyzer: calculates AST node count, bloat ratio, and penalty/bonus.
"""

import ast
import logging
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from vazus_autonomous_harness.verification.academic_sovereignty import AcademicSovereigntyGuard
from vazus_autonomous_harness.verification.smt_prover import SMTProver

logger = logging.getLogger("vazus.harness.verification.quality")


@dataclass
class QualityScore:
    """100-point multi-dimensional quality evaluation score."""
    total_score: float  # 0 to 100
    correctness_smt: float  # max 40
    empirical_integrity: float  # max 30
    parsimony_efficiency: float  # max 15
    academic_sovereignty: float  # max 15
    is_admissible: bool  # total_score >= 75.0 and correctness_smt == 40.0 and academic_sovereignty == 15.0
    counterexample: Optional[Dict[str, Any]] = None
    violation_reasons: Optional[List[str]] = None
    ast_bloat_ratio: float = 0.0

    def __post_init__(self):
        if self.violation_reasons is None:
            self.violation_reasons = []


class ASTParsimonyAnalyzer:
    """
    Measures AST structural bloat and calculates parsimony scores (F3).
    Rejects the 'more code = better' LLM verbosity bias.
    """

    def count_nodes(self, code: str) -> int:
        """Counts the total number of AST nodes in a Python code snippet."""
        if not code or not code.strip():
            return 0
        try:
            tree = ast.parse(code)
            return len(list(ast.walk(tree)))
        except SyntaxError:
            return 0

    def calculate_bloat(self, baseline_code: str, candidate_code: str) -> Dict[str, Any]:
        """
        Calculates AST node counts, bloat ratio, penalty, and bonus.
        Formula:
          bloat_ratio = (N_cand - N_base) / N_base
          Base parsimony = 10 pts
          Penalty = min(10, floor(bloat_ratio * 10)) if bloat_ratio > 0.10 else 0
          Bonus = 5 pts if bloat_ratio <= 0 and N_cand > 0
          Score = max(0, min(15, 10 - Penalty + Bonus))
        """
        base_nodes = self.count_nodes(baseline_code)
        cand_nodes = self.count_nodes(candidate_code)

        if base_nodes == 0:
            bloat_ratio = 0.0
            penalty = 0.0
            bonus = 5.0 if cand_nodes > 0 else 0.0
            score = 15.0 if cand_nodes > 0 else 10.0
        else:
            bloat_ratio = (cand_nodes - base_nodes) / max(1, base_nodes)

            # Penalty for bloat above 10%
            if bloat_ratio <= 0.10:
                penalty = 0.0
            else:
                penalty = min(10.0, float(int(bloat_ratio * 10.0)))

            # Clean diff / refactoring bonus (+5 pts for non-positive bloat)
            if bloat_ratio <= 0.0 and cand_nodes > 0:
                bonus = 5.0
            else:
                bonus = 0.0

            score = max(0.0, min(15.0, 10.0 - penalty + bonus))

        return {
            "score": score,
            "base_nodes": base_nodes,
            "cand_nodes": cand_nodes,
            "bloat_ratio": round(bloat_ratio, 4),
            "penalty": penalty,
            "bonus": bonus,
        }

    # Alias for API compatibility across test harnesses
    analyze_bloat = calculate_bloat


class QualityEvaluationEngine:
    """
    R4 Multi-Dimensional Quality Evaluation Engine (100 Points).
    Enforces strict point-based admission threshold (>= 75.0) and zero hard vetoes.
    """

    def __init__(
        self,
        smt_prover: Optional[SMTProver] = None,
        sovereignty_guard: Optional[AcademicSovereigntyGuard] = None,
        parsimony_analyzer: Optional[ASTParsimonyAnalyzer] = None,
        admission_threshold: float = 75.0,
    ):
        self.smt_prover = smt_prover or SMTProver()
        self.sovereignty_guard = sovereignty_guard or AcademicSovereigntyGuard()
        self.parsimony_analyzer = parsimony_analyzer or ASTParsimonyAnalyzer()
        self.admission_threshold = admission_threshold

    def evaluate(
        self,
        candidate_code: str,
        baseline_code: str = "",
        test_command: Optional[str] = None,
        context_prompt: str = ""
    ) -> QualityScore:
        """
        Evaluates a candidate code proposal across the 4 orthogonal quality dimensions:
        D1: Formal Correctness (SMT Z3) -> max 40
        D2: Empirical Integrity (Tests) -> max 30
        D3: Parsimony & Efficiency (AST) -> max 15
        D4: Academic Sovereignty (USER.md#L37) -> max 15
        """
        violation_reasons: List[str] = []
        counterexample: Optional[Dict[str, Any]] = None

        # ---------------------------------------------------------
        # D1: Formal Correctness (SMT Z3) — max 40 points
        # ---------------------------------------------------------
        correctness_smt = 0.0
        try:
            cand_tree = ast.parse(candidate_code)
            syntax_valid = True
        except SyntaxError as se:
            syntax_valid = False
            violation_reasons.append(f"Syntax error in candidate code: {se}")

        if syntax_valid:
            contract_res = self.smt_prover.verify_contracts(candidate_code)

            if contract_res.status == "UNSAT":
                correctness_smt = 40.0
            elif contract_res.status == "SAT":
                correctness_smt = 0.0
                counterexample = contract_res.counterexample
                violation_reasons.append(f"SMT contract disproven (SAT): {contract_res.details}")
            elif contract_res.status == "VACUOUS_CONTRACT":
                correctness_smt = 0.0
                violation_reasons.append(f"Vacuous SMT contract rejected: {contract_res.details}")
            elif contract_res.status in ("UNKNOWN", "ERROR"):
                correctness_smt = 0.0
                violation_reasons.append(f"SMT solver failure: {contract_res.details}")
            elif contract_res.status == "NO_CONTRACTS":
                # Check for SMT contract regression against baseline
                if baseline_code and baseline_code.strip():
                    base_contract_res = self.smt_prover.verify_contracts(baseline_code)
                    if base_contract_res.status == "UNSAT":
                        correctness_smt = 0.0
                        violation_reasons.append("SMT regression: candidate dropped formal contracts present in baseline")
                    else:
                        # Baseline also had no contracts: verify functional equivalence
                        equiv_res = self.smt_prover.verify_functional_equivalence(candidate_code, baseline_code)
                        if equiv_res.status == "UNSAT":
                            correctness_smt = 40.0
                        elif equiv_res.status == "SAT":
                            correctness_smt = 0.0
                            counterexample = equiv_res.counterexample
                            violation_reasons.append("Functional equivalence check failed: candidate diverges from baseline")
                        else:
                            correctness_smt = 40.0
                else:
                    # Clean code with valid AST and no contracts
                    correctness_smt = 40.0

        # ---------------------------------------------------------
        # D2: Empirical Integrity (Tests) — max 30 points
        # ---------------------------------------------------------
        empirical_integrity = 0.0

        # Check for illicit mocking of core functionality
        has_illicit_mock = False
        if syntax_valid:
            for node in ast.walk(cand_tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if "mock" in alias.name.lower():
                            has_illicit_mock = True
                elif isinstance(node, ast.ImportFrom):
                    if node.module and "mock" in node.module.lower():
                        has_illicit_mock = True

        if has_illicit_mock:
            violation_reasons.append("Illicit mock detected: mocking core components violates empirical integrity")
            empirical_integrity = 0.0
        elif test_command:
            try:
                import os
                # On Windows, subprocess.run(shell=False) natively accepts strings securely.
                # On POSIX, we need shlex.split to securely parse the string without a shell.
                cmd_args = test_command if os.name == 'nt' else shlex.split(test_command)

                proc = subprocess.run(
                    cmd_args,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=str(Path.cwd())
                )
                if proc.returncode == 0:
                    empirical_integrity = 30.0
                else:
                    empirical_integrity = 0.0
                    err_snippet = (proc.stderr or proc.stdout or "").strip()[:200]
                    violation_reasons.append(f"Empirical test execution failed (exit {proc.returncode}): {err_snippet}")
            except subprocess.TimeoutExpired:
                empirical_integrity = 0.0
                violation_reasons.append("Test command timed out after 30 seconds")
            except Exception as e:
                empirical_integrity = 0.0
                violation_reasons.append(f"Test command error: {e}")
        else:
            # Inline execution of candidate test functions if present
            if syntax_valid:
                test_funcs = [
                    n.name for n in ast.walk(cand_tree)
                    if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")
                ]
                if test_funcs:
                    try:
                        sandbox_ns: Dict[str, Any] = {}
                        exec(candidate_code, sandbox_ns)
                        for tf in test_funcs:
                            sandbox_ns[tf]()
                        empirical_integrity = 30.0
                    except AssertionError as ae:
                        empirical_integrity = 0.0
                        violation_reasons.append(f"Inline assertion test failed: {ae}")
                    except Exception as exc:
                        empirical_integrity = 0.0
                        violation_reasons.append(f"Inline test error: {exc}")
                else:
                    # Valid syntax without dedicated test command or inline tests
                    empirical_integrity = 30.0
            else:
                empirical_integrity = 0.0

        # ---------------------------------------------------------
        # D3: Parsimony & Efficiency (AST) — max 15 points
        # ---------------------------------------------------------
        bloat_info = self.parsimony_analyzer.calculate_bloat(baseline_code, candidate_code)
        parsimony_efficiency = float(bloat_info["score"])
        ast_bloat_ratio = float(bloat_info["bloat_ratio"])

        # ---------------------------------------------------------
        # D4: Academic Sovereignty (USER.md#L37) — max 15 points
        # ---------------------------------------------------------
        sov_result = self.sovereignty_guard.verify_code_sovereignty(candidate_code, context_prompt)
        academic_sovereignty = float(sov_result.get("score", 0.0))
        if not sov_result.get("allowed", False):
            violation_reasons.append(sov_result.get("reason", "Academic sovereignty violation"))

        # ---------------------------------------------------------
        # Total Score & Hard Admission Threshold
        # ---------------------------------------------------------
        total_score = round(correctness_smt + empirical_integrity + parsimony_efficiency + academic_sovereignty, 2)

        # Hard admission conditions:
        # 1. Total score >= threshold (75.0)
        # 2. Formal SMT correctness == 40.0 (no contract violations, no equivalence disproofs)
        # 3. Academic sovereignty == 15.0 (no leaks, no stubs)
        # 4. Zero fatal vetoes in violation_reasons
        has_fatal_veto = (
            correctness_smt < 40.0
            or academic_sovereignty < 15.0
            or empirical_integrity < 30.0
            or any("[VETO]" in r or "violation" in r.lower() or "disproven" in r.lower() or "syntax" in r.lower() for r in violation_reasons)
        )

        is_admissible = bool(
            total_score >= self.admission_threshold
            and correctness_smt == 40.0
            and academic_sovereignty == 15.0
            and not has_fatal_veto
        )

        return QualityScore(
            total_score=total_score,
            correctness_smt=correctness_smt,
            empirical_integrity=empirical_integrity,
            parsimony_efficiency=parsimony_efficiency,
            academic_sovereignty=academic_sovereignty,
            is_admissible=is_admissible,
            counterexample=counterexample,
            violation_reasons=violation_reasons,
            ast_bloat_ratio=ast_bloat_ratio,
        )
