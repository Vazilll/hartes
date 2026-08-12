import sys
from pathlib import Path
sys.path.insert(0, "C:/vazus")

import vazus_core.smt_z3_verifier as smt_mod
from vazus_core.smt_z3_verifier import smt_verifier

# Case 3: Invalid contract with different condition (n >= 0 ==> result == 999)
invalid_code_3 = '''
def check_invalid_3(n: int) -> int:
    """
    :requires: n >= 0
    :ensures: result == 999
    """
    return n + 1
'''
res3 = smt_verifier.verify_code_contracts(invalid_code_3)
print(f"Case 3 (Invalid result == 999): status={res3['status']}, satisfied={res3['contract_satisfied']}, solver={res3['model_checking']['solver']}")
print(f"Details 3: {res3['details']}")
