"""
vazus_core.reasoning_effort_controller — Execution & Orchestration Policy Controller.

Maps Effort score [0.0, 1.0] or level ('low', 'medium', 'high', 'xhigh', 'ultra') to concrete
subsystem execution budgets:
- subagent_model: Recommended model tier for invoke_subagent ("flash", "inherit", "pro")
- smt_z3_depth: Formal logic contract proof depth (5 to 30)
- repl_max_iterations: Maximum LocalREPL code trial iterations (3 to 25)
- repl_timeout_seconds: REPL execution timeout in sandbox (5s to 60s)
- verification_tier: Verification gate intensity ("fast", "standard", "strict")
- thinking_budget: Advisory token budget for external blueprints (Note: host agent thinking is controlled by Antigravity UI)
"""

import logging
from typing import Dict, Any, Union

logger = logging.getLogger(__name__)

LEVEL_PRESETS = {
    "low": 0.1,
    "medium": 0.35,
    "high": 0.65,
    "xhigh": 0.85,
    "ultra": 1.0
}

# 2026 Model Context & Max Output Token Limits (advisory for external API wrappers)
MODEL_LIMITS = {
    "gemini-3.6-flash": {"max_output": 65536, "context_window": 1048576},
    "gemini-3.1-pro": {"max_output": 65536, "context_window": 2097152},
    "claude-sonnet-4.6": {"max_output": 128000, "context_window": 200000},
    "gpt-oss-120b": {"max_output": 16384, "context_window": 131072},
    "default": {"max_output": 32768, "context_window": 131072},
}


class ExecutionPolicyController:
    """
    Controller for local execution policies, verification depths, sandbox budgets,
    and subagent model dispatching.
    """

    @staticmethod
    def _parse_effort_level(effort: Union[str, float, None]) -> tuple[float, str]:
        """Safely normalizes optional effort level strings or floats into [0.0, 1.0] score."""
        if effort is None:
            return 0.65, "high"
        if isinstance(effort, str):
            eff_lower = effort.lower().strip()
            score = LEVEL_PRESETS.get(eff_lower, 0.65)
            return score, eff_lower if eff_lower in LEVEL_PRESETS else "high"
        try:
            score = max(0.0, min(1.0, float(effort)))
            if score <= 0.2:
                return score, "low"
            if score <= 0.5:
                return score, "medium"
            if score <= 0.75:
                return score, "high"
            if score <= 0.9:
                return score, "xhigh"
            return score, "ultra"
        except (ValueError, TypeError):
            return 0.65, "high"

    @staticmethod
    def _compute_thinking_token_budget(
        score: float, model_key: str, prompt_tokens: int, safety_headroom: int
    ) -> tuple[int, int]:
        raw_tokens = int(1024 * ((65536 / 1024) ** (score ** 1.2)))
        limits = MODEL_LIMITS.get(model_key.lower(), MODEL_LIMITS["default"])
        max_output = limits["max_output"]
        context_window = limits["context_window"]
        available_headroom = max(1024, context_window - prompt_tokens - safety_headroom)
        clamped_thinking_budget = min(raw_tokens, max_output - safety_headroom, available_headroom)
        return max(0, clamped_thinking_budget), max_output

    @staticmethod
    def _derive_subsystem_budgets(score: float) -> dict[str, Any]:
        if score <= 0.2:
            return {"subagent_model": "flash", "repl_steps": 3, "repl_timeout": 5.0, "smt_z3_depth": 5, "verification_tier": "fast"}
        if score <= 0.5:
            return {"subagent_model": "flash", "repl_steps": 5, "repl_timeout": 10.0, "smt_z3_depth": 10, "verification_tier": "standard"}
        if score <= 0.75:
            return {"subagent_model": "inherit", "repl_steps": 10, "repl_timeout": 20.0, "smt_z3_depth": 15, "verification_tier": "strict"}
        if score <= 0.9:
            return {"subagent_model": "pro", "repl_steps": 15, "repl_timeout": 30.0, "smt_z3_depth": 20, "verification_tier": "strict"}
        return {"subagent_model": "pro", "repl_steps": 25, "repl_timeout": 60.0, "smt_z3_depth": 30, "verification_tier": "strict"}

    @classmethod
    def get_config(
        cls,
        effort: Union[str, float, None] = "high",
        model_key: str = "gemini-3.6-flash",
        prompt_tokens: int = 0,
        safety_headroom: int = 4096
    ) -> Dict[str, Any]:
        """
        Calculates concrete execution parameters for local workers, Z3 verification,
        and subagent delegation.
        """
        score, level_name = cls._parse_effort_level(effort)
        clamped_thinking_budget, max_output = cls._compute_thinking_token_budget(
            score, model_key, prompt_tokens, safety_headroom
        )
        budgets = cls._derive_subsystem_budgets(score)
        subagent_depth = int(1 + 5 * score)

        return {
            "level": level_name,
            "effort_score": round(score, 3),
            "subagent_model": budgets["subagent_model"],
            "subagent_depth": subagent_depth,
            "smt_z3_depth": budgets["smt_z3_depth"],
            "mcts_simulations": 0,
            "repl_steps": budgets["repl_steps"],
            "repl_max_iterations": budgets["repl_steps"],
            "repl_timeout_seconds": budgets["repl_timeout"],
            "verification_tier": budgets["verification_tier"],
            "thinking_budget": clamped_thinking_budget,
            "max_output_tokens": max_output,
            "prompt_tokens": prompt_tokens,
            "model_key": model_key,
        }


# Backwards compatibility alias
ReasoningEffortController = ExecutionPolicyController
