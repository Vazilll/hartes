"""
Unit tests for Epistemic Meta-Search Engine & Search Bandit.
"""

from vazus_autonomous_harness.meta_search.epistemic_engine import EpistemicSearchEngine
from vazus_autonomous_harness.meta_search.search_bandit import SearchBandit


def test_expected_information_gain():
    engine = EpistemicSearchEngine()
    prior = 2.5
    posteriors = [0.5, 0.4, 0.6]  # Significant entropy collapse
    eig = engine.compute_expected_information_gain(prior, posteriors)
    assert eig > 1.5


def test_orthogonal_triangulation():
    engine = EpistemicSearchEngine()

    # Case 1: 3-vector complete convergence
    t_full = engine.evaluate_orthogonal_triangulation(
        empirical_verified=True,
        formal_z3_verified=True,
        literature_grounded=True,
    )
    assert t_full["classification"] == "FORMALLY_VERIFIED_TRUTH"
    assert t_full["epistemic_confidence"] > 0.999

    # Case 2: Only empirical test (missing formal & literature)
    t_partial = engine.evaluate_orthogonal_triangulation(
        empirical_verified=True,
        formal_z3_verified=False,
        literature_grounded=False,
    )
    assert t_partial["classification"] == "PROVISIONAL_UNVERIFIED"


def test_search_bandit_learning():
    bandit = SearchBandit(["strategy_a", "strategy_b"])
    # Give strategy_a 10 continuous successes
    for _ in range(10):
        bandit.update_outcome("strategy_a", success=True)

    # Give strategy_b 5 continuous failures
    for _ in range(5):
        bandit.update_outcome("strategy_b", success=False)

    rankings = bandit.get_rankings()
    assert rankings[0]["modality"] == "strategy_a"
    assert rankings[0]["expected_value"] > rankings[1]["expected_value"]
