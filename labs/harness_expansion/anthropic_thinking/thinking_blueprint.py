"""
labs.harness_expansion.anthropic_thinking.thinking_blueprint
Anthropic Extended Thinking Token Budget Controller & Model Selector Blueprint.
"""

import sys
from pathlib import Path
from typing import Dict, Any, Union

PYENV_DIR = Path(r"C:\vazus")
if str(PYENV_DIR) not in sys.path:
    sys.path.insert(0, str(PYENV_DIR))

from vazus_core.reasoning_effort_controller import ReasoningEffortController
from vazus_core.model_selector import ModelSelector
from vazus_core.context_caching import context_compactor


class AnthropicThinkingBlueprint:
    """
    Anthropic Extended Thinking Token Budget & Dynamic Model Selection Blueprint.
    Computes dynamic Test-Time Compute (TTC) budgets and manages model hot-reloading.
    """

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "harness_id": "anthropic_thinking",
            "name": "Anthropic Extended Thinking & Reasoning Effort Harness",
            "lab": "Anthropic",
            "domain": "test_time_compute_scaling",
            "description": "Logarithmic effort slider budget calculation, model selector, and prefix context caching.",
            "features": ["reasoning_effort_slider", "model_selector", "prefix_caching"],
        }

    def compute_thinking_budget(self, effort: Union[str, float]) -> Dict[str, Any]:
        """Computes concrete token, MCTS, REPL, subagent, and SMT Z3 search budgets for effort level."""
        return ReasoningEffortController.get_config(effort)

    def select_model(self, task_type: str, effort_level: str = "high") -> Dict[str, Any]:
        """Maps task requirement to model key and updates agent configuration."""
        if "reasoning" in task_type.lower() or "math" in task_type.lower():
            model_key = "claude-sonnet-4.6"
        elif "code" in task_type.lower():
            model_key = "gemini-3.6-flash"
        else:
            model_key = "gpt-oss-120b"

        res = ModelSelector.set_agent_configuration(model_key, effort_level)
        return {
            "task_type": task_type,
            "selected_model": res["model"],
            "effort_config": res["effort"],
        }

    def configure_prefix_caching(self, prompt_prefix: str, system_instruction: str = "") -> Dict[str, Any]:
        """Compresses context prefix and builds Mermaid visual graph."""
        res = context_compactor.compact_context_graph(prompt_prefix, task_context=system_instruction)
        return {
            "cache_status": res.get("status"),
            "raw_hash": res.get("raw_hash"),
            "compacted_summary": res.get("compacted_summary"),
            "mermaid_graph": res.get("mermaid_graph"),
        }

    def execute_reasoning_step(self, prompt: str, effort: Union[str, float] = "high") -> Dict[str, Any]:
        """Executes dynamic reasoning step plan combining budget, model selection, and context compaction."""
        budget = self.compute_thinking_budget(effort)
        model_info = self.select_model("reasoning", effort_level=budget["level"])
        caching_info = self.configure_prefix_caching(prompt, system_instruction="Anthropic Thinking Step")

        return {
            "status": "SUCCESS",
            "prompt": prompt,
            "thinking_budget_tokens": budget.get("thinking_budget", 0),
            "mcts_simulations": budget.get("mcts_simulations", 0),
            "repl_steps": budget.get("repl_steps", 0),
            "active_model": model_info["selected_model"],
            "context_cache": caching_info["cache_status"],
        }
