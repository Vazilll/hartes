"""
Adversarial Forensic Audit Script for M4 Remediation SMT Z3 Verifier
"""

import sys
import json
from pathlib import Path

ROOT_DIR = Path("C:/vazus")
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# 1. Verify z3 package import
try:
    import z3
    print(f"[CHECK 1 PASS] Genuine z3 package imported from: {z3.__file__}")
    print(f"               Z3 version: {z3.get_version()}")
except Exception as e:
    print(f"[CHECK 1 FAIL] z3 import failed: {e}")
    sys.exit(1)

from vazus_core.smt_z3_verifier import smt_verifier, Z3_AVAILABLE, SMTZ3Verifier

print(f"[CHECK 2 PASS] Z3_AVAILABLE flag in module: {Z3_AVAILABLE}")

# Test suite of adversarial, valid, invalid, and non-trivial contracts
test_cases = [
    {
        "name": "Valid simple contract (n >= 0 => result >= 0)",
        "code": """
def f1(n: int) -> int:
    '''
    :requires: n >= 0
    :ensures: result >= 0
    '''
    return n + 5
""",
        "expected_status": "UNSAT",
        "expected_satisfied": True
    },
    {
        "name": "Invalid simple contract (n >= 0 => result == 999)",
        "code": """
def f2(n: int) -> int:
    '''
    :requires: n >= 0
    :ensures: result == 999
    '''
    return n + 1
""",
        "expected_status": "SAT",
        "expected_satisfied": False,
        "expect_counterexample": True
    },
    {
        "name": "Adversarial invalid contract that bypassed old facade (n >= 0 => result < 0)",
        "code": """
def f3(n: int) -> int:
    '''
    :requires: n >= 0
    :ensures: result < 0
    '''
    return n + 1
""",
        "expected_status": "SAT",
        "expected_satisfied": False,
        "expect_counterexample": True
    },
    {
        "name": "Non-trivial math contract (x > 10 => result > 20)",
        "code": """
def f4(x: int) -> int:
    '''
    :requires: x > 10
    :ensures: result > 20
    '''
    return x * 2
""",
        "expected_status": "UNSAT",
        "expected_satisfied": True
    },
    {
        "name": "Flawed math contract (x > 10 => result > 25 for return x * 2)",
        "code": """
def f5(x: int) -> int:
    '''
    :requires: x > 10
    :ensures: result > 25
    '''
    return x * 2
""",
        "expected_status": "SAT",
        "expected_satisfied": False,
        "expect_counterexample": True
    },
    {
        "name": "Multi-variable linear contract (a > 5 and b > 5 => result > 10)",
        "code": """
def f6(a: int, b: int) -> int:
    '''
    :requires: a > 5 and b > 5
    :ensures: result > 10
    '''
    return a + b
""",
        "expected_status": "UNSAT",
        "expected_satisfied": True
    },
    {
        "name": "Multi-variable flawed contract (a > 5 and b > 5 => result > 15)",
        "code": """
def f7(a: int, b: int) -> int:
    '''
    :requires: a > 5 and b > 5
    :ensures: result > 15
    '''
    return a + b
""",
        "expected_status": "SAT",
        "expected_satisfied": False,
        "expect_counterexample": True
    },
    {
        "name": "Conditional if-else function return path",
        "code": """
def f8(val: int) -> int:
    '''
    :requires: val >= 0
    :ensures: result >= 0
    '''
    if val == 0:
        return 10
    else:
        return val + 10
""",
        "expected_status": "UNSAT",
        "expected_satisfied": True
    }
]

all_passed = True
for idx, tc in enumerate(test_cases, 1):
    res = smt_verifier.verify_code_contracts(tc["code"], depth=10)
    status = res.get("status")
    satisfied = res.get("contract_satisfied")
    solver = res.get("model_checking", {}).get("solver")
    
    passed = (status == tc["expected_status"]) and (satisfied == tc["expected_satisfied"])
    if tc.get("expect_counterexample"):
        # Check counterexample in details
        ce = res.get("details", [{}])[0].get("smt_result", {}).get("counterexample")
        if not ce:
            passed = False
            print(f"[TEST {idx} FAIL] Expected counterexample model for '{tc['name']}', got None")

    if passed:
        print(f"[TEST {idx} PASS] {tc['name']}: status={status}, satisfied={satisfied}, solver={solver}")
        if tc.get("expect_counterexample"):
            ce = res.get("details", [{}])[0].get("smt_result", {}).get("counterexample")
            print(f"               Counterexample model: {ce}")
    else:
        all_passed = False
        print(f"[TEST {idx} FAIL] {tc['name']}: got status={status}, satisfied={satisfied}, expected status={tc['expected_status']}, satisfied={tc['expected_satisfied']}")
        print(f"               Full result: {json.dumps(res, indent=2)}")

if all_passed:
    print("\n[SUMMARY] ALL ADVERSARIAL SMT Z3 TEST CASES PASSED SUCCESSFULLY.")
else:
    print("\n[SUMMARY] SOME ADVERSARIAL TEST CASES FAILED.")
