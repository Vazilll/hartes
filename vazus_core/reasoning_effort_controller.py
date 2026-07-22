"""
dnts_core.reasoning_effort_controller — Dynamic Test-Time Compute Scaling & Effort Slider Engine.
Maps Effort score [0.0, 1.0] or level ('low', 'medium', 'high', 'xhigh', 'ultra') to 5 concrete execution budgets:
- thinking_budget (tokens)
- mcts_simulations
- repl_steps
- subagent_depth
- smt_z3_depth
"""

import math
from typing import Dict, Any, Union

LEVEL_PRESETS = {
    "low": 0.1,
    "medium": 0.35,
    "high": 0.65,
    "xhigh": 0.85,
    "ultra": 1.0
}

class ReasoningEffortController:
    """Controller for dynamic Test-Time Compute (TTC) scaling."""

    @staticmethod
    def get_config(effort: Union[str, float]) -> Dict[str, Any]:
        if isinstance(effort, str):
            score = LEVEL_PRESETS.get(effort.lower(), 0.65)
            level_name = effort.lower()
        else:
            score = max(0.0, min(1.0, float(effort)))
            if score <= 0.2:
                level_name = "low"
            elif score <= 0.5:
                level_name = "medium"
            elif score <= 0.75:
                level_name = "high"
            elif score <= 0.9:
                level_name = "xhigh"
            else:
                level_name = "ultra"

        # Logarithmic scaling laws formula
        tokens = int(1024 * ((65536 / 1024) ** (score ** 1.2)))
        mcts_sims = int(10 * ((2000 / 10) ** score))
        repl_steps = int(5 * (2 ** (4 * score)))
        subagent_depth = int(1 + 5 * score)
        smt_z3_depth = int(score * 20)

        return {
            "level": level_name,
            "effort_score": round(score, 3),
            "thinking_budget": tokens,
            "mcts_simulations": mcts_sims,
            "repl_steps": repl_steps,
            "subagent_depth": subagent_depth,
            "smt_z3_depth": smt_z3_depth
        }

if __name__ == "__main__":
    for lvl in ["low", "medium", "high", "xhigh", "ultra"]:
        cfg = ReasoningEffortController.get_config(lvl)
        print(f"Level: {lvl.upper():<7} -> Tokens: {cfg['thinking_budget']:<6} | MCTS: {cfg['mcts_simulations']:<4} | REPL: {cfg['repl_steps']:<3} | SubDepth: {cfg['subagent_depth']}")
