"""
Unit tests for SkillDistiller and Gödel RSI Auto-Distillation Compiler.
"""

import shutil
from pathlib import Path
import pytest
from vazus_autonomous_harness.skills.skill_tree import SkillTree
from vazus_autonomous_harness.skills.skill_distiller import SkillDistiller


@pytest.fixture
def tmp_skill_dir(tmp_path):
    output_dir = tmp_path / "skills_test"
    output_dir.mkdir(parents=True, exist_ok=True)
    yield output_dir
    if output_dir.exists():
        shutil.rmtree(output_dir, ignore_errors=True)


def test_skill_distiller_l3_success(tmp_skill_dir):
    tree = SkillTree()
    distiller = SkillDistiller(skill_tree=tree, skills_output_dir=tmp_skill_dir)

    code = """
def transform_data(items: list) -> list:
    return [x * 2 for x in items]
"""

    res = distiller.distill_and_verify(
        skill_id="test_l3_transformer",
        name="L3 Data Transformer",
        level=3,
        description="Transforms lists safely",
        code_str=code,
        persist_disk=True,
    )

    assert res.is_verified is True
    assert res.status == "VERIFIED"
    assert res.skill_md_path is not None
    assert Path(res.skill_md_path).exists()

    # Verify skill registered in tree
    node = tree.get_skill("test_l3_transformer")
    assert node is not None
    assert node.level == 3

    # Check SKILL.md content
    md_content = Path(res.skill_md_path).read_text(encoding="utf-8")
    assert "name: test_l3_transformer" in md_content
    assert "level: 3" in md_content
    assert "Gödel RSI Consistency" in md_content


def test_skill_distiller_l4_smt_contract_proved(tmp_skill_dir):
    tree = SkillTree()
    distiller = SkillDistiller(skill_tree=tree, skills_output_dir=tmp_skill_dir)

    code = '''
def add_positive(x: int) -> int:
    """
    Adds positive delta.
    :requires: x >= 0
    :ensures: result >= 0
    """
    return x + 10
'''

    res = distiller.distill_and_verify(
        skill_id="test_l4_adder",
        name="L4 Formal Adder",
        level=4,
        description="Formal addition with SMT contract",
        code_str=code,
        dependencies=["l1_run_cli"],
        persist_disk=True,
    )

    assert res.is_verified is True
    assert res.contract_proved is True
    assert tree.get_skill("test_l4_adder") is not None


def test_skill_distiller_l4_smt_contract_rejected(tmp_skill_dir):
    tree = SkillTree()
    distiller = SkillDistiller(skill_tree=tree, skills_output_dir=tmp_skill_dir)

    # Bad contract where postcondition fails (result > 1000 is not guaranteed)
    bad_code = '''
def faulty_func(x: int) -> int:
    """
    Faulty contract.
    :requires: x >= 0
    :ensures: result > 1000
    """
    return x + 1
'''

    res = distiller.distill_and_verify(
        skill_id="test_l4_faulty",
        name="L4 Faulty Function",
        level=4,
        description="Broken formal contract",
        code_str=bad_code,
        dependencies=["l1_run_cli"],
        persist_disk=True,
    )

    assert res.is_verified is False
    assert res.status == "SMT_VETO"
    assert "Formal SMT contract verification failed" in res.reason
    assert tree.get_skill("test_l4_faulty") is None
