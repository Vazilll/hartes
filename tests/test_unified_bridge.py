"""
tests/test_unified_bridge.py — Integration test for Unified SuperGraph Bridge (Item 1 & Item 3).

Verifies:
1. Item 1: SMT Z3 contract verification and Concordia Multi-Agent Jury consensus execution.
2. Item 3: Skill Authoring validation and registration.
"""

import sys
from pathlib import Path

VAZUS_DIR = Path("C:/vazus")
if str(VAZUS_DIR) not in sys.path:
    sys.path.insert(0, str(VAZUS_DIR))

from scripts.unified_supergraph_bridge import UnifiedSuperGraphBridge


def test_unified_bridge_pipeline():
    bridge = UnifiedSuperGraphBridge(effort_level="high")

    # Item 1 Test
    code_snippet = """
def check_positive_square(x: int) -> int:
    \"\"\"
    Returns square of x.
    :requires: x >= 0
    :ensures: result >= 0
    \"\"\"
    return x * x
"""
    res_verif = bridge.verify_code_with_jury_and_smt(
        file_path="C:/vazus/vazus_core/smt_z3_verifier.py",
        code_content=code_snippet,
        expected_functions=["check_positive_square"],
        smt_depth=5,
    )

    assert res_verif["overall_passed"] is True, "Expected Item 1 SMT Z3 + Jury verification to pass"

    # Item 3 Test
    res_skill = bridge.validate_and_register_skill(
        skill_id="unified-verifier-skill",
        display_name="Unified Verifier & Skill Authoring",
        description="Automated Z3 SMT proof solver and skill registration",
        instructions="Execute proof solver before registering new skill",
    )

    assert res_skill["success"] is True, "Expected Item 3 Skill Authoring registration to pass"


if __name__ == "__main__":
    test_unified_bridge_pipeline()
    print("✅ test_unified_bridge.py PASSED!")
