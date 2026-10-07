"""
Unit tests for Layer 4 SMT Z3 Equivalence Prover.
"""

from vazus_core.verification.smt_equivalence_prover import SMTEquivalenceProver

def test_smt_prover_equivalent_expressions():
    prover = SMTEquivalenceProver()
    # (a + b) * 2 == 2 * a + 2 * b
    res = prover.verify_expression_equivalence(
        "(a + b) * 2",
        "2 * a + 2 * b",
        ["a", "b"]
    )
    assert res["equivalent"] is True
    assert res["status"] == "PROVEN_EQUIVALENT"

def test_smt_prover_disproven_counterexample():
    prover = SMTEquivalenceProver()
    # (a + b) * 2 != a * 2 + b (missing 2*b)
    res = prover.verify_expression_equivalence(
        "(a + b) * 2",
        "a * 2 + b",
        ["a", "b"]
    )
    assert res["equivalent"] is False
    assert res["status"] == "DISPROVEN"
    assert "counterexample" in res


def test_smt_prover_unary_and_power():
    prover = SMTEquivalenceProver()
    # +a == a
    res = prover.verify_expression_equivalence("+a", "a", ["a"])
    assert res["equivalent"] is True

    # a ** 2 == a * a
    res2 = prover.verify_expression_equivalence("a ** 2", "a * a", ["a"])
    assert res2["equivalent"] is True


def test_smt_prover_comparisons_and_conditionals():
    prover = SMTEquivalenceProver()
    # (x if a > 0 else y) == (y if not (a > 0) else x)
    res = prover.verify_expression_equivalence(
        "x if a > 0 else y",
        "y if not (a > 0) else x",
        ["a", "x", "y"]
    )
    assert res["equivalent"] is True

