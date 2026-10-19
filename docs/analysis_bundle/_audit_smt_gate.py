"""Live probes: SMT SAT counterexample, gate timeout claim, targeted-test mapper."""
import sys
import time

sys.path.insert(0, "C:/vazus")

print("=== 1. SMT counterexample content (DISPROVEN case) ===")
from vazus_core.verification.smt_equivalence_prover import SMTEquivalenceProver  # noqa: E402
p = SMTEquivalenceProver()
b = p.verify_expression_equivalence("a * b + 1", "a * b", ["a", "b"])
print("keys:", sorted(b.keys()))
print("full result:", b)

print()
print("=== 2. smt_z3_verifier: does SAT fire on a violated contract? ===")
from vazus_core.verification.smt_z3_verifier import SMTZ3Verifier  # noqa: E402
v = SMTZ3Verifier(depth=10)
bad = '''
def f(x):
    """
    :requires: x > 0
    :ensures: result < 0
    """
    return x
'''
r = v.verify_code_contracts(bad, depth=10)
print("violated-contract status:", r.get("status"), "| satisfied:", r.get("contract_satisfied"))
print("details:", str(r.get("proof_details") or r.get("error_message"))[:200])

good = '''
def g(x):
    """
    :requires: x > 0
    :ensures: result > 0
    """
    return x
'''
r2 = v.verify_code_contracts(good, depth=10)
print("sound-contract  status:", r2.get("status"), "| satisfied:", r2.get("contract_satisfied"))

print()
print("=== 3. Gate targeted-test mapper (claim: 1 -> 7 tests via AST imports) ===")
from pathlib import Path  # noqa: E402
from vazus_core.verification.precommit_gate import find_targeted_tests, get_staged_python_files  # noqa: E402
staged = get_staged_python_files()
print(f"staged .py files: {len(staged)}")
t0 = time.time()
tests = find_targeted_tests(staged)
print(f"targeted tests found: {len(tests)} in {time.time()-t0:.2f}s")
for t in tests:
    print("   ", t)

print()
print("=== 4. Single-file mapper sanity (llm_client.py) ===")
one = [Path("C:/vazus/vazus_core/engine/llm_client.py")]
t = find_targeted_tests(one)
print(f"llm_client.py -> {len(t)} tests: {t}")
