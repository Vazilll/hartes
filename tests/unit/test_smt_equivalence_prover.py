"""
Unit tests for Layer 4 SMT Z3 Equivalence Prover.
"""

import pytest
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
