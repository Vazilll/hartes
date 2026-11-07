"""
hartes.llm.gemini_planner - Real Gemini API backend for AgentHarness.

Auth: reads GEMINI_API_KEY or GOOGLE_API_KEY from environment only.
Never hardcode credentials. Set with:
    PowerShell: $env:GEMINI_API_KEY = "your-key"
    Bash:       export GEMINI_API_KEY=your-key

Usage:
    from llm.gemini_planner import GeminiPlanner
    planner = GeminiPlanner()
    result = planner.plan("Optimize this code...", history=[])
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("vazus.llm.gemini")

GEMINI_MODELS = {
    "flash-lite": "gemini-2.0-flash-lite",
    "flash":      "gemini-2.0-flash",
    "pro":        "gemini-2.5-pro",
}
DEFAULT_MODEL = "gemini-2.0-flash-lite"
MAX_RETRIES = 3
RETRY_BACKOFF_S = 2.0
_KEY_NAMES = ("GEMINI_API_KEY", "GOOGLE_API_KEY")


def _read_api_key() -> str:
    for name in _KEY_NAMES:
        val = os.environ.get(name, "")
        if val:
            return val
    raise EnvironmentError(
        "GEMINI_API_KEY environment variable not set.\n"
        "Set it with:\n"
        "  PowerShell: $env:GEMINI_API_KEY = 'your-key'\n"
        "  Bash:       export GEMINI_API_KEY=your-key"
    )


class GeminiPlanner:
    """
    Thin adapter implementing planner_fn interface for AgentHarness.

    Returns dict with keys:
        thought, thought_signature, response, tool_calls, model, usage
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        temperature: float = 0.7,
        max_output_tokens: int = 8192,
    ):
        self._model_name = GEMINI_MODELS.get(model, model)
        self._temperature = temperature
        self._max_output_tokens = max_output_tokens
        self._client = self._build_client(_read_api_key())

    def _build_client(self, key: str):
        try:
            import google.generativeai as genai
            genai.configure(api_key=key)
            return genai.GenerativeModel(
                model_name=self._model_name,
                generation_config={
                    "temperature": self._temperature,
                    "max_output_tokens": self._max_output_tokens,
                    "response_mime_type": "text/plain",
                },
            )
        except ImportError as exc:
            raise ImportError(
                "google-generativeai not installed.\n"
                "Run: C:\\vazus\\.venv\\Scripts\\pip install google-generativeai"
            ) from exc

    def plan(self, user_input: str, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Core planner callable. Compatible with AgentHarness.execute_turn()."""
        chat_history = []
        for turn in history[-10:]:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            if isinstance(content, dict):
                content = content.get("final_answer", str(content))
            if role in ("user", "model"):
                chat_history.append({"role": role, "parts": [content]})

        last_error: Optional[Exception] = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                chat = self._client.start_chat(history=chat_history)
                resp = chat.send_message(user_input)
                text = resp.text or ""
                usage = {}
                if hasattr(resp, "usage_metadata") and resp.usage_metadata:
                    um = resp.usage_metadata
                    usage = {
                        "prompt_tokens": getattr(um, "prompt_token_count", 0),
                        "completion_tokens": getattr(um, "candidates_token_count", 0),
                    }
                sig = hashlib.sha256(text.encode()).hexdigest()[:16]
                return {
                    "thought": "",
                    "thought_signature": sig,
                    "response": text,
                    "tool_calls": [],
                    "model": self._model_name,
                    "usage": usage,
                }
            except Exception as exc:
                last_error = exc
                wait = RETRY_BACKOFF_S * (2 ** (attempt - 1))
                logger.warning("Gemini attempt %d/%d: %s, retry in %.1fs", attempt, MAX_RETRIES, exc, wait)
                time.sleep(wait)

        raise RuntimeError(f"Gemini API failed after {MAX_RETRIES} attempts: {last_error}")

    def __call__(self, user_input: str, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        return self.plan(user_input, history)
