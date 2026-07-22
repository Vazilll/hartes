"""
dnts_core.model_selector — Interactive & Programmatic Model and Reasoning Effort Selector.
Supports Gemini 3.6 Flash, Claude Sonnet 4.6, GPT-OSS 120B, and preset configurations.
Hot-reloads settings.json and environment variables without service interruption.
"""

import json
import os
from typing import Dict, Any, Optional
from dnts_core.reasoning_effort_controller import ReasoningEffortController

AVAILABLE_MODELS = {
    "gemini-3.6-flash": "Gemini 3.6 Flash (High)",
    "gemini-3.5-flash": "Gemini 3.5 Flash",
    "gemini-3.1-pro": "Gemini 3.1 Pro",
    "claude-sonnet-4.6": "Claude Sonnet 4.6 (Thinking)",
    "claude-opus-4.6": "Claude Opus 4.6 (Thinking)",
    "gpt-oss-120b": "GPT-OSS 120B (Medium)"
}

SETTINGS_FILE = r"C:\Users\Vaz\.gemini\antigravity-cli\settings.json"

class ModelSelector:
    """Manages active LLM models and Reasoning Effort configuration."""

    @staticmethod
    def set_agent_configuration(model_key: str, effort_level: str = "high") -> Dict[str, Any]:
        full_model_name = AVAILABLE_MODELS.get(model_key.lower(), model_key)
        effort_cfg = ReasoningEffortController.get_config(effort_level)

        os.environ["DNTS_MODEL"] = full_model_name
        os.environ["DNTS_REASONING_EFFORT"] = effort_level
        os.environ["DNTS_THINKING_BUDGET"] = str(effort_cfg["thinking_budget"])

        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)

                data["model"] = full_model_name
                data["reasoningEffort"] = effort_level
                data["thinkingBudget"] = effort_cfg["thinking_budget"]

                with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

                print(f"[ModelSelector] Successfully updated model to '{full_model_name}' (Effort: {effort_level.upper()})")
            except Exception as e:
                print(f"[ModelSelector] Error updating settings.json: {e}")

        return {
            "model": full_model_name,
            "effort": effort_cfg
        }

if __name__ == "__main__":
    res = ModelSelector.set_agent_configuration("gemini-3.6-flash", "xhigh")
    print("Updated settings:", res)
