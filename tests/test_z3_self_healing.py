"""
tests.test_z3_self_healing — Tests for SMT Z3 Counterexample-Guided Self-Healing Loop.
Verifies contract solving, counterexample extraction, and automated pytest fixture synthesis.
"""

import pytest
from vazus_core.verification.smt_z3_verifier import (
    verify_with_healing_feedback,
    SMTZ3SelfHealingLoop,
)


def test_smt_z3_valid_contract_proof():
    """Verify that a formally valid mathematical contract returns verified=True (UNSAT)."""
    code = """
def absolute_value(x: int) -> int:
    \"\"\"
    :requires: True
    :ensures: result >= 0
    \"\"\"
    if x < 0:
        return -x
    return x
"""
    feedback = verify_with_healing_feedback(code)
    assert feedback["verified"] is True
    assert feedback["contract_satisfied"] is True
    assert feedback["solver_status"] == "UNSAT"
    assert len(feedback["actionable_healing_steps"]) > 0


def test_smt_z3_counterexample_and_fixture_generation():
    """Verify that a contract violation triggers counterexample extraction and pytest fixture synthesis."""
    code = """
def faulty_increment(x: int) -> int:
    \"\"\"
    :requires: x > 0
    :ensures: result > x + 5
    \"\"\"
    return x + 1
"""
    feedback = verify_with_healing_feedback(code)
    assert feedback["verified"] is False
    assert feedback["contract_satisfied"] is False
    assert feedback["counterexample"] is not None
    assert len(feedback["failing_pytest_fixtures"]) > 0
    
    fixture_code = feedback["failing_pytest_fixtures"][0]
    assert "def test_z3_counterexample_" in fixture_code
    assert "faulty_increment(" in fixture_code
    # Fixture must carry the formal postcondition (result -> res) as a real assertion
    assert "res > x + 5" in fixture_code

    import re
    fixture_fn = re.search(r"def (test_z3_counterexample_\w+)\(\)", fixture_code).group(1)

    # Honest RED: executing the fixture against the faulty implementation must fail
    faulty_ns = {"faulty_increment": lambda x: x + 1}
    exec(fixture_code, faulty_ns)
    with pytest.raises(AssertionError):
        faulty_ns[fixture_fn]()

    # Honest GREEN: a healed implementation must satisfy the same fixture
    healed_ns = {"faulty_increment": lambda x: x + 100}
    exec(fixture_code, healed_ns)
    healed_ns[fixture_fn]()


def test_smt_z3_self_healing_loop_instance():
    """Verify that SMTZ3SelfHealingLoop inspect_and_heal method executes properly."""
    loop = SMTZ3SelfHealingLoop()
    res = loop.inspect_and_heal("def simple(a: int) -> int:\n    return a\n")
    assert "verified" in res
    assert "actionable_healing_steps" in res
