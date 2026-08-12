import sys
from pathlib import Path

ROOT_DIR = Path("C:/vazus")
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from vazus_core.smt_z3_verifier import smt_verifier

def run_stress_tests():
    print("--- RUNNING ADVERSARIAL STRESS TESTS FOR SMT Z3 VERIFIER ---")

    # Test 1: Nonlinear math & quadratic constraints
    code1 = '''
def pythagoras(a: int, b: int) -> int:
    """
    :requires: a > 0 and b > 0
    :ensures: result > 0
    """
    return a * a + b * b
'''
    res1 = smt_verifier.verify_code_contracts(code1)
    print("Test 1 (a > 0, b > 0 => a^2 + b^2 > 0):", res1["status"], "Satisfied:", res1["contract_satisfied"])
    assert res1["status"] == "UNSAT" and res1["contract_satisfied"] is True

    # Test 2: Counterexample for flawed condition
    code2 = '''
def sum_threshold(a: int, b: int) -> int:
    """
    :requires: a > 0 and b > 0
    :ensures: result > 100
    """
    return a + b
'''
    res2 = smt_verifier.verify_code_contracts(code2)
    print("Test 2 (a > 0, b > 0 => a + b > 100 [Flawed]):", res2["status"], "Counterexample:", res2["details"][0]["smt_result"]["counterexample"])
    assert res2["status"] == "SAT" and res2["contract_satisfied"] is False
    assert res2["details"][0]["smt_result"]["counterexample"] is not None

    # Test 3: If-Else expression return (Conditional AST parsing)
    code3 = '''
def abs_val(x: int) -> int:
    """
    :requires: x != 0
    :ensures: result > 0
    """
    return x if x > 0 else -x
'''
    res3 = smt_verifier.verify_code_contracts(code3)
    print("Test 3 (x != 0 => abs(x) > 0 [IfExp return]):", res3["status"], "Satisfied:", res3["contract_satisfied"])
    assert res3["status"] == "UNSAT" and res3["contract_satisfied"] is True

    # Test 4: Multiple function contracts in single module
    code4 = '''
def func_one(n: int) -> int:
    """
    :requires: n >= 10
    :ensures: result >= 20
    """
    return n * 2

def func_two(m: int) -> int:
    """
    :requires: m < 0
    :ensures: result < 0
    """
    return m - 5
'''
    res4 = smt_verifier.verify_code_contracts(code4)
    print("Test 4 (Multi-function verification):", res4["status"], "Verified functions:", res4["functions_verified"])
    assert res4["status"] == "UNSAT" and len(res4["functions_verified"]) == 2

    print("ALL STRESS TESTS COMPLETED SUCCESSFULLY WITH ZERO FAILS!")

if __name__ == "__main__":
    run_stress_tests()
