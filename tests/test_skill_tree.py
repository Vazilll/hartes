"""
Unit tests for 5-tier Skill Tree.
"""

from vazus_autonomous_harness.skills.skill_tree import SkillTree, SkillNode


def test_skill_tree_levels():
    tree = SkillTree()
    # Ensure all levels 1..5 have initial definitions
    for lvl in range(1, 6):
        skills = tree.list_by_level(lvl)
        assert len(skills) >= 1


def test_skill_outcome_reinforcement():
    tree = SkillTree()
    node = SkillNode(id="test_skill", name="Test Skill", level=2, description="Test")
    tree.register_skill(node)

    initial_weight = node.reward_weight
    tree.record_outcome("test_skill", success=True)
    assert node.reward_weight > initial_weight
    assert node.success_count == 1

    tree.record_outcome("test_skill", success=False)
    assert node.failure_count == 1
    assert round(node.reliability, 2) == 0.5
