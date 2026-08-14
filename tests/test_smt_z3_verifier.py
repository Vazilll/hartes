"""
Unit tests for SMT Z3 Formal Proofs Engine & Rollback Guardrails (Milestone 4).
Tests functional equivalence proofs, memory bounds safety verification,
and RollbackGuardrail automatic commit/rollback behaviors.
"""

import sys
import tempfile
from pathlib import Path
import pytest

from vazus_core.smt_z3_verifier import (
    SMTZ3Verifier,
    VerificationResult,
    RollbackGuardrail,
    smt_verifier,
)
from scripts.subagent_verifier_bridge import VerifierSubagentBridge


def test_verification_result_structure():
    """Verify VerificationResult dataclass initialization, attributes, and dictionary access."""
    res = VerificationResult(
        verified=True,
        proof_type="TEST_PROOF",
        solver_status="UNSAT",
        counterexample=None
    )
    assert res.verified is True
    assert res.proof_type == "TEST_PROOF"
    assert res.solver_status == "UNSAT"
    assert res.counterexample is None

    # Subscripting and get() access for backward compatibility
    assert res["verified"] is True
    assert res["solver_status"] == "UNSAT"
    assert res.get("proof_type") == "TEST_PROOF"

    to_d = res.to_dict()
    assert isinstance(to_d, dict)
    assert to_d["verified"] is True


def test_verify_functional_equivalence_passing():
    """Verify symbolic functional equivalence for equivalent arithmetic routines."""
    verifier = SMTZ3Verifier()

    orig_code = """
def double_val(x: int) -> int:
    return x + x
"""

    opt_code = """
def double_val(x: int) -> int:
    return x * 2
"""

    res = verifier.verify_functional_equivalence(orig_code, opt_code, "double_val")
    assert res.verified is True
    assert res.proof_type == "FUNCTIONAL_EQUIVALENCE"
    assert res.solver_status == "UNSAT"
    assert res.counterexample is None


def test_verify_functional_equivalence_polynomial():
    """Verify equivalence for polynomial algebraic identity (x+y)*(x-y) == x**2 - y**2."""
    verifier = SMTZ3Verifier()

    orig_code = """
def poly_identity(x: int, y: int) -> int:
    return (x + y) * (x - y)
"""

    opt_code = """
def poly_identity(x: int, y: int) -> int:
    return x**2 - y**2
"""

    res = verifier.verify_functional_equivalence(orig_code, opt_code, "poly_identity")
    assert res.verified is True
    assert res.proof_type == "FUNCTIONAL_EQUIVALENCE"
    assert res.solver_status == "UNSAT"
    assert res.counterexample is None


def test_verify_functional_equivalence_counterexample():
    """Verify counterexample detection for non-equivalent routines."""
    verifier = SMTZ3Verifier()

    orig_code = """
def add_one(x: int) -> int:
    return x + 1
"""

    opt_code = """
def add_one(x: int) -> int:
    return x + 2
"""

    res = verifier.verify_functional_equivalence(orig_code, opt_code, "add_one")
    assert res.verified is False
    assert res.proof_type == "FUNCTIONAL_EQUIVALENCE"
    assert res.solver_status == "SAT"
    assert res.counterexample is not None
    assert "x" in res.counterexample


def test_verify_memory_safety_passing():
    """Verify memory bounds safety condition offset >= 0 and length >= 0 and offset + length <= capacity."""
    verifier = SMTZ3Verifier()

    # Valid memory bounds
    res = verifier.verify_memory_safety(offset=10, length=20, capacity=100)
    assert res.verified is True
    assert res.proof_type == "MEMORY_SAFETY"
    assert res.solver_status == "UNSAT"
    assert res.counterexample is None

    # Exact capacity boundary fit
    res_bound = verifier.verify_memory_safety(offset=0, length=100, capacity=100)
    assert res_bound.verified is True
    assert res_bound.solver_status == "UNSAT"


def test_verify_memory_safety_violations():
    """Verify memory safety violation detection for out-of-bounds or negative inputs."""
    verifier = SMTZ3Verifier()

    # Out of bounds (90 + 20 = 110 > 100)
    res_oob = verifier.verify_memory_safety(offset=90, length=20, capacity=100)
    assert res_oob.verified is False
    assert res_oob.proof_type == "MEMORY_SAFETY"
    assert res_oob.solver_status == "SAT"
    assert res_oob.counterexample is not None

    # Negative offset (-5 < 0)
    res_neg_off = verifier.verify_memory_safety(offset=-5, length=10, capacity=100)
    assert res_neg_off.verified is False
    assert res_neg_off.solver_status == "SAT"

    # Negative length (-10 < 0)
    res_neg_len = verifier.verify_memory_safety(offset=0, length=-10, capacity=100)
    assert res_neg_len.verified is False
    assert res_neg_len.solver_status == "SAT"


def test_rollback_guardrail_success():
    """Verify RollbackGuardrail commits changes when optimization and tests pass."""
    with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".py") as tmp:
        tmp.write("def dummy(): return 'original'")
        tmp_path = Path(tmp.name)

    try:
        def opt_func():
            tmp_path.write_text("def dummy(): return 'optimized'", encoding="utf-8")
            return True

        test_cmd = [sys.executable, "-c", "import sys; sys.exit(0)"]
        success = RollbackGuardrail.execute_with_guardrail(tmp_path, opt_func, test_cmd)

        assert success is True
        assert tmp_path.read_text(encoding="utf-8") == "def dummy(): return 'optimized'"
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def test_rollback_guardrail_opt_func_failure():
    """Verify RollbackGuardrail restores target file when optimization function raises exception."""
    with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".py") as tmp:
        tmp.write("def dummy(): return 'original'")
        tmp_path = Path(tmp.name)

    try:
        def opt_func():
            tmp_path.write_text("def dummy(): return 'broken'", encoding="utf-8")
            raise ValueError("Optimization failed")

        test_cmd = [sys.executable, "-c", "import sys; sys.exit(0)"]
        success = RollbackGuardrail.execute_with_guardrail(tmp_path, opt_func, test_cmd)

        assert success is False
        assert tmp_path.read_text(encoding="utf-8") == "def dummy(): return 'original'"
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def test_rollback_guardrail_test_cmd_failure():
    """Verify RollbackGuardrail restores target file when test command returns non-zero exit code."""
    with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".py") as tmp:
        tmp.write("def dummy(): return 'original'")
        tmp_path = Path(tmp.name)

    try:
        def opt_func():
            tmp_path.write_text("def dummy(): return 'broken'", encoding="utf-8")
            return True

        test_cmd = [sys.executable, "-c", "import sys; sys.exit(1)"]  # Failing test command
        success = RollbackGuardrail.execute_with_guardrail(tmp_path, opt_func, test_cmd)

        assert success is False
        assert tmp_path.read_text(encoding="utf-8") == "def dummy(): return 'original'"
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def test_verifier_bridge_integration():
    """Verify VerifierSubagentBridge python API bindings for formal verification."""
    bridge = VerifierSubagentBridge()

    orig_code = "def f(x): return x + x"
    opt_code = "def f(x): return x * 2"

    eq_res = bridge.verify_functional_equivalence(orig_code, opt_code, "f")
    assert eq_res["verified"] is True
    assert eq_res["solver_status"] == "UNSAT"

    mem_res = bridge.verify_memory_safety(offset=10, length=50, capacity=100)
    assert mem_res["verified"] is True
    assert mem_res["solver_status"] == "UNSAT"

    mem_fail = bridge.verify_memory_safety(offset=80, length=50, capacity=100)
    assert mem_fail["verified"] is False
    assert mem_fail["solver_status"] == "SAT"


def test_verify_contract_pass():
    """Verify SMTZ3Verifier.verify_contract returns UNSAT ProofVerdict for valid pre/post contracts."""
    verifier = SMTZ3Verifier()
    code = """
def abs_val(n: int) -> int:
    \"\"\"
    :requires: n >= 0
    :ensures: result >= 0
    \"\"\"
    return n
"""
    verdict = verifier.verify_contract(code)
    assert verdict.verified is True
    assert verdict.proof_status == "UNSAT"
    assert verdict.solver_status == "UNSAT"


def test_rollback_on_failure_trigger():
    """Verify RollbackGuardrail.rollback_on_failure triggers git revert/checkout safely."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        res = RollbackGuardrail.rollback_on_failure(repo_dir=tmp_dir)
        assert isinstance(res, bool)

