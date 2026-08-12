"""
test_smt_stress.py — Stress test harness for SMT Z3 Verifier and Bridge components.
"""

import sys
from pathlib import Path

ROOT_DIR = Path("C:/vazus")
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from vazus_core.smt_z3_verifier import smt_verifier, Z3_AVAILABLE, SMTZ3Verifier
import z3

def test_z3_direct():
    print(f"Z3_AVAILABLE: {Z3_AVAILABLE}")
    print(f"z3 module: {z3.__file__}")

    # Test 1: Simple function with return statement
    code_1 = """
def add_five(x: int) -> int:
    \"\"\"
    :requires: x > 0
    :ensures: result > 5
    \"\"\"
    return x + 5
"""
    res1 = smt_verifier.verify_code_contracts(code_1)
    print("Test 1 (add_five, x > 0 => result > 5):", res1)

    # Test 2: Function body returns wrong value for contract
    code_2 = """
def add_five_buggy(x: int) -> int:
    \"\"\"
    :requires: x > 0
    :ensures: result > 5
    \"\"\"
    return x - 10
"""
    res2 = smt_verifier.verify_code_contracts(code_2)
    print("Test 2 (add_five_buggy, x > 0 => result > 5, body returns x - 10):", res2)

    # Test 3: Postcondition with expression on right side e.g. result >= x
    code_3 = """
def identity_plus(x: int) -> int:
    \"\"\"
    :requires: x >= 0
    :ensures: result >= x
    \"\"\"
    return x
"""
    res3 = smt_verifier.verify_code_contracts(code_3)
    print("Test 3 (identity_plus, x >= 0 => result >= x):", res3)

    # Test 4: Syntax error in python code
    code_4 = "def bad_syntax(x: int -> int return x +++"
    res4 = smt_verifier.verify_code_contracts(code_4)
    print("Test 4 (bad syntax):", res4)

    # Test 5: Malformed contract syntax in docstring
    code_5 = """
def malformed_contract(x: int) -> int:
    \"\"\"
    :requires: x is non-negative and valid integer
    :ensures: result is strictly positive
    \"\"\"
    return x + 1
"""
    res5 = smt_verifier.verify_code_contracts(code_5)
    print("Test 5 (malformed/textual contract):", res5)

if __name__ == "__main__":
    test_z3_direct()
