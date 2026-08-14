"""
vazus_core.reasoning_effort_controller — Dynamic Test-Time Compute Scaling & Effort Slider Engine.

Maps Effort score [0.0, 1.0] or level ('low', 'medium', 'high', 'xhigh', 'ultra') to concrete execution budgets:
- thinking_budget (tokens, dynamically clamped to model max_output_tokens envelope)
- mcts_simulations
- repl_steps
- subagent_depth
- smt_z3_depth
"""

import math
from typing import Dict, Any, Union, Optional

LEVEL_PRESETS = {
    "low": 0.1,
    "medium": 0.35,
    "high": 0.65,
    "xhigh": 0.85,
    "ultra": 1.0
}

# 2026 Model Context & Max Output Token Limits
MODEL_LIMITS = {
    "gemini-3.6-flash": {"max_output": 65536, "context_window": 1048576},
    "gemini-3.1-pro": {"max_output": 65536, "context_window": 2097152},
    "claude-sonnet-4.6": {"max_output": 128000, "context_window": 200000},
    "gpt-oss-120b": {"max_output": 16384, "context_window": 131072},
    "default": {"max_output": 32768, "context_window": 131072},
}


class ReasoningEffortController:
    """Controller for dynamic Test-Time Compute (TTC) scaling and provider budget clamping."""

    @staticmethod
    def get_config(
        effort: Union[str, float],
        model_key: str = "gemini-3.6-flash",
        prompt_tokens: int = 0,
        safety_headroom: int = 4096
    ) -> Dict[str, Any]:
        """
        Calculates execution parameters and dynamically clamps thinking_budget to prevent
        FINISH_REASON: MAX_TOKENS truncation or provider context limit overflow.
        """
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

        # Logarithmic scaling laws formula for base tokens
        raw_tokens = int(1024 * ((65536 / 1024) ** (score ** 1.2)))
        
        # Model-aware Context Clamping
        limits = MODEL_LIMITS.get(model_key.lower(), MODEL_LIMITS["default"])
        max_output = limits["max_output"]
        context_window = limits["context_window"]

        # Dynamic Safety Envelope: ensure prompt + thinking + headroom <= context_window
        available_headroom = max(1024, context_window - prompt_tokens - safety_headroom)
        clamped_thinking_budget = min(raw_tokens, max_output - safety_headroom, available_headroom)
        clamped_thinking_budget = max(0, clamped_thinking_budget)

        # Compute scaling parameters
        mcts_sims = int(10 * ((2000 / 10) ** score))
        repl_steps = int(5 * (2 ** (4 * score)))
        subagent_depth = int(1 + 5 * score)
        smt_z3_depth = int(score * 20)

        return {
            "level": level_name,
            "effort_score": round(score, 3),
            "thinking_budget": clamped_thinking_budget,
            "raw_thinking_budget": raw_tokens,
            "max_output_tokens": max_output,
            "prompt_tokens": prompt_tokens,
            "mcts_simulations": mcts_sims,
            "repl_steps": repl_steps,
            "subagent_depth": subagent_depth,
            "smt_z3_depth": smt_z3_depth,
            "model_key": model_key,
        }


if __name__ == "__main__":
    for lvl in ["low", "medium", "high", "xhigh", "ultra"]:
        cfg = ReasoningEffortController.get_config(lvl, model_key="gemini-3.6-flash", prompt_tokens=10000)
        print(f"Level: {lvl.upper():<7} -> ThinkingBudget: {cfg['thinking_budget']:<6} | MCTS: {cfg['mcts_simulations']:<4} | REPL: {cfg['repl_steps']:<3}")
