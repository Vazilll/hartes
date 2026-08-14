"""
vazus_core.model_selector — Subagent Model & Execution Effort Selector.

Manages subagent model tier presets (Gemini Flash, Claude Sonnet, GPT-OSS) and execution effort levels.
Stores active preferences in environment variables (VAZUS_MODEL, VAZUS_REASONING_EFFORT).
Note: Primary Antigravity agent model is selected directly via the Antigravity IDE UI.
"""

import asyncio
import logging
import os
from typing import Dict, Any
from vazus_core.engine.reasoning_effort_controller import ReasoningEffortController

logger = logging.getLogger(__name__)

AVAILABLE_MODELS = {
    "gemini-3.6-flash": "Gemini 3.6 Flash (High)",
    "gemini-3.5-flash": "Gemini 3.5 Flash",
    "gemini-3.1-pro": "Gemini 3.1 Pro",
    "claude-sonnet-4.6": "Claude Sonnet 4.6 (Thinking)",
    "claude-opus-4.6": "Claude Opus 4.6 (Thinking)",
    "gpt-oss-120b": "GPT-OSS 120B (Medium)"
}


class ModelSelector:
    """Manages subagent model presets and execution effort parameters."""

    @staticmethod
    def set_agent_configuration(model_key: str, effort_level: str = "high") -> Dict[str, Any]:
        full_model_name = AVAILABLE_MODELS.get(model_key.lower(), model_key)
        effort_cfg = ReasoningEffortController.get_config(effort_level)

        os.environ["VAZUS_MODEL"] = full_model_name
        os.environ["VAZUS_REASONING_EFFORT"] = effort_level

        logger.debug(f"[ModelSelector] Configured subagent model '{full_model_name}' (Effort: {effort_level.upper()})")

        return {
            "model": full_model_name,
            "effort": effort_cfg
        }

    @staticmethod
    async def set_agent_configuration_async(model_key: str, effort_level: str = "high") -> Dict[str, Any]:
        """Asynchronously updates model configuration using non-blocking thread offloading."""
        return await asyncio.to_thread(ModelSelector.set_agent_configuration, model_key, effort_level)

    @staticmethod
    def get_active_model() -> str:
        """Returns the currently active model key or default gemini-3.6-flash."""
        full_name = os.environ.get("VAZUS_MODEL", "Gemini 3.6 Flash (High)")
        for k, v in AVAILABLE_MODELS.items():
            if v == full_name or k == full_name.lower():
                return k
        return "gemini-3.6-flash"

