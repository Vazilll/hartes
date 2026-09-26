"""
Integration test for Multi-Round Recursive Self-Improvement Flywheel.
"""

from vazus_autonomous_harness.flywheel.recursive_runner import RecursiveSelfImprovementFlywheel


def test_multi_round_evolution():
    flywheel = RecursiveSelfImprovementFlywheel()
    results = flywheel.run_evolution_rounds(num_rounds=3)

    assert results["completed_rounds"] == 3
    assert len(results["rounds"]) == 3

    # Check that mutations were formally verified and skills promoted
    for r_data in results["rounds"]:
        assert r_data["mutations_verified"] >= 1
        assert r_data["skills_promoted"] >= 1
        assert r_data["round_latency_ms"] > 0

    # Ensure search bandit updated its rankings
    assert len(results["search_rankings"]) > 0

    # Verify skill tree gained evolved skills
    l3_skills = results["skill_tree_state"]["level_3"]
    assert len(l3_skills) >= 1
