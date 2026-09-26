"""
hartes.llm.agy_planner — Antigravity (AGY) CLI Headless Planner Adapter.

Connects AgentHarness and Hartes Tasks to the local `agy.exe` runtime,
consuming Google Antigravity session quotas (Gemini 3.8 Flash, Gemini 3.1 Pro,
Claude Sonnet 4.6 Thinking) with 0 external API cost and no API keys required.

Based on vazus_core.workers.agy_bridge and vazus_core.engine.llm_client.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("hartes.llm.agy")

DEFAULT_AGY_PATH = (
    Path(os.environ.get("LOCALAPPDATA", r"C:\Users\Vaz\AppData\Local"))
    / "agy"
    / "bin"
    / "agy.exe"
)

# Canonical mapping from short aliases to official agy CLI model names
MODEL_ALIASES: Dict[str, str] = {
    "flash": "gemini-3.8-flash-high",
    "flash-lite": "gemini-3.7-flash-high",
    "pro": "gemini-3.1-pro-high",
    "pro-low": "gemini-3.1-pro-low",
    "sonnet": "claude-sonnet-4-6",
    "opus": "claude-opus-4-6-thinking",
    "gpt": "gpt-oss-120b-medium",
}

DEFAULT_MODEL = "gemini-3.8-flash-high"
DEFAULT_TIMEOUT_S = 180.0


def is_test_mode() -> bool:
    """Returns True if running under pytest or explicit test mode."""
    return (
        os.getenv("VAZUS_TEST_MODE") == "1"
        or os.getenv("VAZUS_TEST_MODE", "").lower() == "true"
        or "PYTEST_CURRENT_TEST" in os.environ
    )


def resolve_agy_binary(custom_path: Optional[Path] = None) -> Optional[Path]:
    """Finds agy.exe via custom path, DEFAULT_AGY_PATH, or PATH environment."""
    if custom_path and custom_path.exists():
        return custom_path
    if DEFAULT_AGY_PATH.exists():
        return DEFAULT_AGY_PATH
    which_path = shutil.which("agy")
    if which_path:
        p = Path(which_path)
        if p.exists():
            return p
    return None


def resolve_model_name(model_name: str) -> str:
    """Resolves short model names or aliases to official agy model keys."""
    k = model_name.lower().strip()
    if k in MODEL_ALIASES:
        return MODEL_ALIASES[k]
    # Check partial matches
    if "sonnet" in k or "claude" in k:
        return "claude-sonnet-4-6"
    if "opus" in k:
        return "claude-opus-4-6-thinking"
    if "120b" in k or "gpt" in k:
        return "gpt-oss-120b-medium"
    if "pro" in k or "3.1" in k:
        return "gemini-3.1-pro-high"
    if "3.7" in k:
        return "gemini-3.7-flash-high"
    if "3.8" in k or "flash" in k:
        return "gemini-3.8-flash-high"
    return model_name


def generate_mock_plan(user_input: str, model_name: str) -> Dict[str, Any]:
    """Generates deterministic mock response for unit tests and offline mode."""
    combined = user_input.lower()

    # If code optimization task, produce valid Python code block
    if "optimize" in combined or "def " in user_input:
        match = re.search(r"```python\s*(.*?)\s*```", user_input, re.DOTALL)
        if match:
            code_body = match.group(1).strip()
            repaired = f"# Optimized by AgyPlanner (Test Mode)\n{code_body}\n"
            resp = f"```python\n{repaired}```"
        elif "def " in user_input:
            repaired = f"# Optimized by AgyPlanner (Test Mode)\n{user_input.strip()}\n"
            resp = f"```python\n{repaired}```"
        else:
            resp = (
                "```python\n"
                "# Optimized by AgyPlanner (Test Mode)\n"
                "def optimized_func(*args, **kwargs):\n"
                "    return True\n"
                "```"
            )
    else:
        resp = f"[MOCK] AgyPlanner response for prompt ({model_name})"

    sig = hashlib.sha256(resp.encode()).hexdigest()[:16]
    return {
        "thought": "Deterministic offline test planning",
        "thought_signature": sig,
        "response": resp,
        "tool_calls": [],
        "model": model_name,
        "usage": {"prompt_tokens": len(user_input) // 4, "completion_tokens": len(resp) // 4},
    }


class AgyPlanner:
    """
    Adapter executing prompts via headless Antigravity CLI (agy.exe).
    Implements planner_fn interface for AgentHarness and Hartes tasks.
    """

    def __init__(
        self,
        model: str = "flash",
        agy_path: Optional[Path] = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_S,
        cwd: Optional[Path] = None,
        effort: Optional[str] = None,
    ):
        self.raw_model = model
        self.resolved_model = resolve_model_name(model)
        self.agy_path = resolve_agy_binary(agy_path)
        self.timeout_seconds = timeout_seconds
        self.cwd = cwd or Path(r"C:\vazus")
        self.effort = effort

    def is_available(self) -> bool:
        """Returns True if agy binary is accessible."""
        return self.agy_path is not None and self.agy_path.exists()

    def plan(
        self,
        user_input: str,
        history: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Executes turn via `agy.exe -p` and returns the standardized plan dict.
        """
        # Fast-path for unit tests and CI
        if is_test_mode():
            return generate_mock_plan(user_input, self.resolved_model)

        if not self.is_available():
            raise FileNotFoundError(
                f"Antigravity CLI (agy.exe) not found at {DEFAULT_AGY_PATH}. "
                "Ensure agy is installed in %LOCALAPPDATA%\\agy\\bin or added to PATH."
            )

        # Build prompt incorporating recent turns if provided
        history_context = ""
        if history:
            recent_turns = []
            for turn in history[-5:]:
                role = turn.get("role", "user")
                content = turn.get("content", "")
                if isinstance(content, dict):
                    content = content.get("final_answer", str(content))
                recent_turns.append(f"[{role}]: {content}")
            if recent_turns:
                history_context = "PREVIOUS CONVERSATION CONTEXT:\n" + "\n".join(recent_turns) + "\n\n"

        full_prompt = history_context + user_input

        cmd = [
            str(self.agy_path),
            "-p",
            full_prompt,
            "--model",
            self.resolved_model,
            "--output-format",
            "text",
            "--dangerously-skip-permissions",
        ]
        if self.effort in ("low", "medium", "high"):
            cmd.extend(["--effort", self.effort])

        logger.info(
            "Invoking agy.exe: model=%s, effort=%s, prompt_len=%d",
            self.resolved_model,
            self.effort,
            len(full_prompt),
        )

        t0 = time.perf_counter()
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout_seconds,
                cwd=str(self.cwd),
            )
            elapsed_s = time.perf_counter() - t0
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(
                f"agy.exe timed out after {self.timeout_seconds}s for model {self.resolved_model}"
            ) from exc
        except Exception as exc:
            raise RuntimeError(f"Failed to execute agy.exe: {exc}") from exc

        if proc.returncode != 0:
            err = proc.stderr.strip() or f"Process exited with code {proc.returncode}"
            logger.error("agy.exe execution failed: %s", err)
            raise RuntimeError(f"agy.exe error (code {proc.returncode}): {err}")

        output_text = proc.stdout.strip()
        sig = hashlib.sha256(output_text.encode()).hexdigest()[:16]

        est_prompt_tokens = len(full_prompt) // 4
        est_completion_tokens = len(output_text) // 4

        return {
            "thought": "",
            "thought_signature": sig,
            "response": output_text,
            "tool_calls": [],
            "model": self.resolved_model,
            "usage": {
                "prompt_tokens": est_prompt_tokens,
                "completion_tokens": est_completion_tokens,
                "latency_s": round(elapsed_s, 2),
            },
        }

    def __call__(
        self,
        user_input: str,
        history: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Makes AgyPlanner directly usable as a planner_fn callable."""
        return self.plan(user_input, history)
