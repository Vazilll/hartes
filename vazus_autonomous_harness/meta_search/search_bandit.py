"""
vazus_autonomous_harness.meta_search.search_bandit — Thompson Sampling Bandit over Search Modalities.

Allows the AI to solve the exploration vs. exploitation dilemma across search strategies.
Each search modality maintains Beta(alpha, beta) parameters.
"""

from typing import Dict, Any, List
import random


class SearchBandit:
    """
    Multi-Armed Bandit maintaining Bayesian posterior distributions for search modalities.
    """

    def __init__(self, modalities: List[str]):
        # modality -> {"alpha": successes, "beta": failures}
        self.arms: Dict[str, Dict[str, float]] = {
            m: {"alpha": 1.0, "beta": 1.0} for m in modalities
        }

    def select_strategy(self) -> str:
        """
        Thompson Sampling: sample from Beta distribution for each arm,
        select the one with highest sample.
        """
        best_modality = None
        highest_sample = -1.0

        for modality, params in self.arms.items():
            sample = random.betavariate(params["alpha"], params["beta"])
            if sample > highest_sample:
                highest_sample = sample
                best_modality = modality

        return best_modality or list(self.arms.keys())[0]

    def update_outcome(self, modality: str, success: bool, reward_magnitude: float = 1.0):
        """
        Bayesian update:
        Success -> alpha += reward_magnitude
        Failure -> beta += reward_magnitude
        """
        if modality in self.arms:
            if success:
                self.arms[modality]["alpha"] += reward_magnitude
            else:
                self.arms[modality]["beta"] += reward_magnitude

    def get_rankings(self) -> List[Dict[str, Any]]:
        """
        Returns search modalities sorted by expected value E[Beta] = alpha / (alpha + beta).
        """
        rankings = []
        for modality, params in self.arms.items():
            ev = params["alpha"] / (params["alpha"] + params["beta"])
            rankings.append({
                "modality": modality,
                "expected_value": round(ev, 4),
                "trials": round(params["alpha"] + params["beta"] - 2.0, 1),
            })
        return sorted(rankings, key=lambda x: x["expected_value"], reverse=True)
