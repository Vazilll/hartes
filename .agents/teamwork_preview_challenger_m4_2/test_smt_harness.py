"""
Empirical Stress-Test Harness for SMT Z3 Code Contract Verifier (Milestone 4 Remediation)
Working directory: C:\\vazus\\.agents\\teamwork_preview_challenger_m4_2
"""

import sys
import json
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, r"C:\vazus")

from vazus_core.smt_z3_verifier import SMTZ3Verifier, smt_verifier

def run_direct_verifier_tests():
    verifier = SMTZ3Verifier(depth=10)
    results = []

    # Test Case 1: Single-parameter valid contract
    code1 = """
def abs_val(x: int) -> int:
    \"\"\"
    Compute absolute value.
    :requires: x >= -100
    :ensures: result >= 0
    \"\"\"
    return x if x >= 0 else -x
"""
    res1 = verifier.verify_code_contracts(code1)
    results.append({
        "name": "TestCase 1: Single-param valid abs_val",
        "expected_status": "UNSAT",
        "expected_satisfied": True,
        "actual": res1
    })

    # Test Case 2: Multi-parameter arithmetic valid contract
    code2 = """
def add_positive(a: int, b: int) -> int:
    \"\"\"
    Add two positive integers.
    :requires: a > 0
    :requires: b > 0
    :ensures: result > 1
    \"\"\"
    return a + b
"""
    res2 = verifier.verify_code_contracts(code2)
    results.append({
        "name": "TestCase 2: Multi-param valid add_positive",
        "expected_status": "UNSAT",
        "expected_satisfied": True,
        "actual": res2
    })

    # Test Case 3: Invalid contract with counterexample x = 0
    code3 = """
def identity_positive(x: int) -> int:
    \"\"\"
    Return identity expecting strictly positive result.
    :requires: x >= 0
    :ensures: result > 0
    \"\"\"
    return x
"""
    res3 = verifier.verify_code_contracts(code3)
    results.append({
        "name": "TestCase 3: Invalid contract identity_positive (counterexample x=0)",
        "expected_status": "SAT",
        "expected_satisfied": False,
        "actual": res3
    })

    # Test Case 4: Complex arithmetic boundary condition (valid)
    code4 = """
def scale_offset(x: int, y: int) -> int:
    \"\"\"
    Scale and offset calculation.
    :requires: x >= 5
    :requires: y >= 10
    :ensures: result >= 20
    \"\"\"
    return 2 * x + y
"""
    res4 = verifier.verify_code_contracts(code4)
    results.append({
        "name": "TestCase 4: Multi-param boundary scale_offset (valid)",
        "expected_status": "UNSAT",
        "expected_satisfied": True,
        "actual": res4
    })

    # Test Case 5: Integer division flaw (counterexample x = 1)
    code5 = """
def half_exact(x: int) -> int:
    \"\"\"
    Exact half function contract.
    :requires: x >= 0
    :ensures: result * 2 == x
    \"\"\"
    return x // 2
"""
    res5 = verifier.verify_code_contracts(code5)
    results.append({
        "name": "TestCase 5: Integer division parity flaw (counterexample x=1)",
        "expected_status": "SAT",
        "expected_satisfied": False,
        "actual": res5
    })

    # Test Case 6: Docstring Requires/Ensures alternative syntax
    code6 = """
def clamp_upper(n: int) -> int:
    \"\"\"
    Clamp function.
    Requires: n <= 50
    Requires: n >= 0
    Ensures: result <= 50
    Ensures: result >= 0
    \"\"\"
    if n > 50:
        return 50
    if n < 0:
        return 0
    return n
"""
    res6 = verifier.verify_code_contracts(code6)
    results.append({
        "name": "TestCase 6: Requires/Ensures docstring formatting (valid)",
        "expected_status": "UNSAT",
        "expected_satisfied": True,
        "actual": res6
    })

    return results

if __name__ == "__main__":
    print("Running Direct SMT Z3 Verifier Tests...")
    test_results = run_direct_verifier_tests()
    passed = 0
    failed = 0
    for t in test_results:
        act_status = t["actual"].get("status")
        act_sat = t["actual"].get("contract_satisfied")
        match = (act_status == t["expected_status"]) and (act_sat == t["expected_satisfied"])
        if match:
            passed += 1
            print(f"[PASS] {t['name']}")
        else:
            failed += 1
            print(f"[FAIL] {t['name']} - Expected status={t['expected_status']}, satisfied={t['expected_satisfied']}; Got status={act_status}, satisfied={act_sat}")
        
        # Print details if SAT (counterexample found)
        details = t["actual"].get("details", [])
        for d in details:
            smt_res = d.get("smt_result", {})
            if smt_res.get("counterexample"):
                print(f"       -> Counterexample Model: {smt_res.get('counterexample')}")

    print(f"\nDirect Verifier Summary: {passed} PASSED, {failed} FAILED out of {len(test_results)} test cases.")
    with open(r"C:\vazus\.agents\teamwork_preview_challenger_m4_2\direct_test_results.json", "w", encoding="utf-8") as f:
        json.dump(test_results, f, indent=2)
