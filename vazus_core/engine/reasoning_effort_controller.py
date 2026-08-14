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
    def get_config(
        effort: Union[str, float],
        model_key: str = "gemini-3.6-flash",
        prompt_tokens: int = 0,
        safety_headroom: int = 4096
    ) -> Dict[str, Any]:
        """
        Calculates concrete execution parameters for local workers, Z3 verification,
        and subagent delegation.
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

        # Advisory token budget calculation for external blueprint callers
        raw_tokens = int(1024 * ((65536 / 1024) ** (score ** 1.2)))
        limits = MODEL_LIMITS.get(model_key.lower(), MODEL_LIMITS["default"])
        max_output = limits["max_output"]
        context_window = limits["context_window"]
        available_headroom = max(1024, context_window - prompt_tokens - safety_headroom)
        clamped_thinking_budget = min(raw_tokens, max_output - safety_headroom, available_headroom)
        clamped_thinking_budget = max(0, clamped_thinking_budget)

        # Concrete local execution parameters
        if score <= 0.2:
            subagent_model = "flash"
            repl_steps = 3
            repl_timeout = 5.0
            smt_z3_depth = 5
            verification_tier = "fast"
        elif score <= 0.5:
            subagent_model = "flash"
            repl_steps = 5
            repl_timeout = 10.0
            smt_z3_depth = 10
            verification_tier = "standard"
        elif score <= 0.75:
            subagent_model = "inherit"
            repl_steps = 10
            repl_timeout = 20.0
            smt_z3_depth = 15
            verification_tier = "strict"
        elif score <= 0.9:
            subagent_model = "pro"
            repl_steps = 15
            repl_timeout = 30.0
            smt_z3_depth = 20
            verification_tier = "strict"
        else:
            subagent_model = "pro"
            repl_steps = 25
            repl_timeout = 60.0
            smt_z3_depth = 30
            verification_tier = "strict"

        subagent_depth = int(1 + 5 * score)

        return {
            "level": level_name,
            "effort_score": round(score, 3),
            "subagent_model": subagent_model,
            "subagent_depth": subagent_depth,
            "smt_z3_depth": smt_z3_depth,
            "mcts_simulations": 0,
            "repl_steps": repl_steps,
            "repl_max_iterations": repl_steps,
            "repl_timeout_seconds": repl_timeout,
            "verification_tier": verification_tier,
            # Advisory token envelope (host LLM thinking is configured via Antigravity UI)
            "thinking_budget": clamped_thinking_budget,
            "max_output_tokens": max_output,
            "prompt_tokens": prompt_tokens,
            "model_key": model_key,
        }


# Backwards compatibility alias
ReasoningEffortController = ExecutionPolicyController
