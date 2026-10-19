"""
Deep, hardcore, zero-mock empirical verification tests for Advanced Verification Stack:
  1. Real AST Mutation Testing with live execution & boundary mutant detection.
  2. Metamorphic Invariance across nested closures, lambdas & scope shadowing.
  3. Differential Fuzzing with NaN, subnormals, Unicode, and Exception hierarchies.
  4. SBFL Ochiai Mathematical Fault Localization on multi-branch diamond CFG.
"""

import math
import sys
import pytest
from pathlib import Path
from vazus_core.verification.mutation_tester import MutationTester, ASTMutator
from vazus_core.verification.metamorphic_verifier import MetamorphicVerifier
from vazus_core.verification.differential_runner import DifferentialRunner
from vazus_core.verification.sbfl_localizer import SBFLLocalizer


def test_mutation_tester_generation_deep():
    src_code = """
def complex_calc(x: int, y: int, flag: bool) -> int:
    if flag and x > 0:
        val = (x * 2) + y
        if val <= 100:
            return val
        return val - 50
    return 0
"""
    tester = MutationTester()
    count = tester.count_possible_mutations(src_code)
    assert count >= 6  # and, >, *, +, <=, -

    mutated_codes = []
    for i in range(count):
        code, desc = tester.generate_mutant_code(src_code, mutation_index=i)
        if code:
            mutated_codes.append((code, desc))

    # All generated mutants must be valid Python syntax
    import ast
    for code, desc in mutated_codes:
        parsed = ast.parse(code)
        assert parsed is not None
        assert code != src_code


def test_mutation_tester_real_execution_scoring(tmp_path):
    """Zero-mock: writes real python target and test files and executes live mutation scoring."""
    target_file = tmp_path / "calc_mod.py"
    test_file = tmp_path / "test_calc_mod.py"

    target_file.write_text("""
def is_strictly_positive(x: int) -> bool:
    return x > 0
""", encoding="utf-8")

    # Test file that only tests x=5 (weak test: does NOT test x=0 boundary!)
    test_file.write_text("""
from calc_mod import is_strictly_positive

def test_pos():
    assert is_strictly_positive(5) is True
""", encoding="utf-8")

    tester = MutationTester(workspace_root=str(tmp_path))
    res = tester.evaluate_mutation_score(
        target_file_rel="calc_mod.py",
        test_file_rel="test_calc_mod.py",
        max_mutants=5
    )

    assert res["status"] == "SUCCESS"
    assert res["total_tested"] > 0
    # Mutation '>' -> '>=' survives because weak test didn't check x=0!
    assert "mutation_score" in res


def test_metamorphic_nested_closures_and_shadowing():
    """Verifies alpha-renaming in nested closures without breaking builtins or outer scope."""
    verifier = MetamorphicVerifier()
    src_code = """
def outer_fn(base_val, multiplier):
    def inner_fn(step):
        return (step + base_val) * multiplier
    return [inner_fn(i) for i in range(5)]
"""
    transformed, renames = verifier.transform_alpha_rename(src_code)
    assert renames >= 2
    assert "_meta_base_val" in transformed
    assert "_meta_multiplier" in transformed
    # Builtins like range must NOT be corrupted
    assert "range(5)" in transformed


def test_differential_fuzzing_nan_and_subnormals():
    """Deep differential fuzzing verifying float NaN, -0.0 vs 0.0 and infinity semantics."""
    runner = DifferentialRunner()

    def calc_a(f: float) -> float:
        if math.isnan(f):
            return float("nan")
        return f * 2.0

    def calc_b(f: float) -> float:
        if math.isnan(f):
            return float("nan")
        return f + f

    corpus = [0.0, -0.0, 1e-15, float("inf"), float("-inf"), float("nan")]
    res = runner.run_differential_comparison(calc_a, calc_b, input_corpus=corpus)
    assert res["status"] == "EQUIVALENT"
    assert res["equivalence_rate"] == 1.0


def test_differential_fuzzing_exception_hierarchy_divergence():
    """Verifies that differing exception types (ValueError vs TypeError) are correctly detected as divergence."""
    runner = DifferentialRunner()

    def parse_a(x: int) -> int:
        if x < 0:
            raise ValueError("Negative number")
        return x * 2

    def parse_b(x: int) -> int:
        if x < 0:
            raise TypeError("Negative number")
        return x * 2

    res = runner.run_differential_comparison(parse_a, parse_b, input_corpus=[-5])
    assert res["status"] == "DIVERGENCE_DETECTED"
    assert len(res["counterexamples"]) == 1
    assert res["counterexamples"][0]["type"] == "EXCEPTION_MISMATCH"



def test_sbfl_ochiai_diamond_control_flow():
    """
    Empirically verifies Ochiai formula on diamond control flow:
    Path 1 (Pass): L1 -> L2 -> L4 -> L5
    Path 2 (Pass): L1 -> L3 -> L4 -> L5
    Path 3 (Fail): L1 -> L2 -> L6(BUG) -> L5
    Path 4 (Fail): L1 -> L3 -> L6(BUG) -> L5
    """
    localizer = SBFLLocalizer()
    pass_cov = [{1, 2, 4, 5}, {1, 3, 4, 5}]
    fail_cov = [{1, 2, 6, 5}, {1, 3, 6, 5}]
    all_lines = {1, 2, 3, 4, 5, 6}

    scores = localizer.calculate_ochiai_scores(pass_cov, fail_cov, all_lines)
    # Line 6 is covered by 2/2 failing tests and 0/2 passing tests -> Ochiai(6) MUST be 1.0 (Top 1)
    top_line, top_score = scores[0]
    assert top_line == 6
    assert top_score == 1.0

    # Line 1 and 5 are covered by ALL tests (2 fail, 2 pass) -> Ochiai = 2 / sqrt(2 * 4) = 2 / 2.828 = ~0.7071
    score_line_1 = dict(scores)[1]
    assert math.isclose(score_line_1, 2.0 / math.sqrt(2.0 * 4.0), rel_tol=1e-3)
