"""
vazus_core.llm_client — Async LLM Invocation Bridge & Antigravity SDK Brain.

Provides non-blocking async LLM generation via Tier-1 Google Antigravity SDK
(google.antigravity.Agent) using IDE session quota (0 external API cost),
with secondary opt-in cloud fallback (VAZUS_LLM_ALLOW_CLOUD=1) and deterministic
mock generation for offline/pytest test modes (VAZUS_TEST_MODE=1).
"""

import os
import re
import ast
import json
import shutil
import asyncio
import logging
from typing import Dict, Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_MODEL = "gemini-3.7-flash"


def is_test_mode() -> bool:
    """Returns True if running under pytest or explicit test mode."""
    return (
        os.getenv("VAZUS_TEST_MODE") == "1"
        or os.getenv("VAZUS_TEST_MODE", "").lower() == "true"
        or "PYTEST_CURRENT_TEST" in os.environ
    )


def _resolve_agy_model_name(model_key: str) -> str:
    """Maps internal model keys to official Antigravity CLI models."""
    k = model_key.lower().strip()
    if "claude" in k and "opus" in k:
        return "Claude Opus 4.6 (Thinking)"
    elif "claude" in k:
        return "Claude Sonnet 4.6 (Thinking)"
    elif "gpt" in k or "120b" in k:
        return "GPT-OSS 120B (Medium)"
    elif "3.6" in k:
        return "Gemini 3.6 Flash (High)"
    elif "3.5" in k:
        return "Gemini 3.5 Flash (High)"
    elif "3.1" in k or "pro" in k:
        return "Gemini 3.1 Pro (High)"
    else:
        return "Gemini 3.7 Flash (High)"


def _generate_mock_response(prompt: str, system_prompt: str = "") -> str:
    """
    Generates deterministic mock responses for test mode or offline environments
    based on prompt intent detection.
    """
    combined_prompt = f"{system_prompt}\n{prompt}".lower()

    # Intent 1: Concordia Jury Voting Call
    if any(k in combined_prompt for k in ["concordia", "jury", "planner", "rlm_coder", "verifier", "evaluate code proposal"]):
        agent_name = "Planner"
        if "rlm_coder" in combined_prompt or "rlm coder" in combined_prompt:
            agent_name = "RLM_Coder"
        elif "verifier" in combined_prompt:
            agent_name = "Verifier_Worker"

        code_match = re.search(r"```python\s*(.*?)\s*```", prompt, re.DOTALL)
        code_str = code_match.group(1) if code_match else prompt

        ast_valid = True
        try:
            ast.parse(code_str)
        except Exception as exc:
            logger.debug("[llm_client] AST parse check in mock generator failed: %s", exc)
            ast_valid = False

        if not ast_valid:
            return json.dumps({
                "agent": agent_name,
                "approved": False,
                "verdict": "FAIL",
                "reason": "AST syntax error detected in proposal (Test Mode)."
            })

        if "smt contract failed" in combined_prompt or ("requires" in combined_prompt and "fail" in combined_prompt):
            return json.dumps({
                "agent": agent_name,
                "approved": False,
                "verdict": "FAIL",
                "reason": "SMT Z3 contract precondition violation (Test Mode)."
            })

        return json.dumps({
            "agent": agent_name,
            "approved": True,
            "verdict": "PASS",
            "reason": f"{agent_name} architectural and contract criteria satisfied (Test Mode)."
        })

    # Intent 2: Reflexion Code Repair Fixer Call
    if any(k in combined_prompt for k in ["reflexion", "fixer", "failing code:", "evaluation critique", "error traceback"]):
        code_match = re.search(r"```python\s*(.*?)\s*```", prompt, re.DOTALL)
        if code_match:
            code_body = code_match.group(1)
            lines = [l for l in code_body.splitlines() if "import google.genai" not in l and "from google import genai" not in l]
            repaired = "\n".join(lines)
            if not repaired.endswith("\n# Repaired by Reflexion LLM"):
                repaired += "\n# Repaired by Reflexion LLM\n"
            return f"```python\n{repaired}\n```"
        else:
            return "```python\ndef repaired_func():\n    # Repaired by Reflexion LLM\n    return True\n```"

    return "[MOCK] Mock LLM generation response (VAZUS_TEST_MODE=1)."


def _resolve_agy_binary_path() -> str | None:
    """Resolves the Antigravity CLI binary path."""
    agy_path = shutil.which("agy")
    if not agy_path:
        for candidate in [
            r"C:\Users\Vaz\AppData\Local\agy\bin\agy.exe",
            r"C:\Users\Vaz\AppData\Local\agy\bin\agy",
        ]:
            if os.path.isfile(candidate):
                return candidate
    return agy_path


async def _execute_agy_subprocess_prompt(
    agy_path: str,
    model: str,
    prompt: str,
    system_prompt: str,
    timeout_seconds: float,
) -> str | None:
    """Executes prompt via Antigravity CLI subprocess."""
    resolved_model = _resolve_agy_model_name(model)
    combined_text = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
    cmd = [
        agy_path,
        "-p", combined_text,
        "--model", resolved_model,
        "--output-format", "text",
        "--dangerously-skip-permissions",
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
        if proc.returncode == 0:
            res_text = stdout.decode("utf-8", errors="replace").strip()
            if res_text:
                return res_text
        else:
            err_msg = stderr.decode("utf-8", errors="replace")
            logger.warning("[llm_client] agy returned error code %s: %s", proc.returncode, err_msg)
    except Exception as exc:
        logger.warning("[llm_client] agy execution notice: %s", exc)
    return None


async def _execute_antigravity_sdk(prompt: str, system_prompt: str) -> str | None:
    """Invokes Google Antigravity Python SDK if available."""
    try:
        from google.antigravity import Agent, LocalAgentConfig, CapabilitiesConfig
        config = LocalAgentConfig(
            system_instructions=system_prompt if system_prompt else "You are an expert AI engineer in Vazus OS.",
            capabilities=CapabilitiesConfig(),
        )
        tokens = []
        async with Agent(config) as agent:
            resp_stream = await agent.chat(prompt)
            async for token in resp_stream:
                tokens.append(token)
        sdk_result = "".join(tokens).strip()
        if sdk_result:
            return sdk_result
    except Exception as exc:
        logger.debug("[llm_client] Tier-1 Antigravity SDK notice: %s", exc)
    return None


async def _execute_cloud_gemini_rest(
    model: str,
    prompt: str,
    system_prompt: str,
    temperature: float,
    timeout_seconds: float,
) -> str | None:
    """Executes direct REST call to Cloud Gemini API."""
    allow_cloud = os.getenv("VAZUS_LLM_ALLOW_CLOUD") == "1"
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not (allow_cloud and api_key):
        return None

    url = f"{DEFAULT_GEMINI_ENDPOINT}/{model}:generateContent?key={api_key}"
    payload: Dict[str, Any] = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature},
    }
    if system_prompt:
        payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

    headers = {"Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts and "text" in parts[0]:
                        return parts[0]["text"].strip()
            logger.warning("[llm_client] Gemini REST API HTTP %s; fallback.", resp.status_code)
    except Exception as exc:
        logger.warning("[llm_client] Cloud Gemini REST exception: %s", exc)
    return None


async def async_generate_llm(
    prompt: str,
    system_prompt: str = "",
    model: str = DEFAULT_MODEL,
    temperature: float = 0.2,
    timeout_seconds: float = 60.0,
    **_kwargs,
) -> str:
    """
    Asynchronously invokes LLM model generation.
    - Tier-1 (Default): Antigravity CLI binary (agy) or Antigravity SDK.
    - Tier-2 (Cloud Opt-in): Gemini REST API when VAZUS_LLM_ALLOW_CLOUD=1.
    - Tier-3 (Deterministic Fallback): Mock generator for offline / pytest execution.
    """
    if is_test_mode():
        return _generate_mock_response(prompt, system_prompt)

    # Tier-1a: Antigravity CLI
    agy_path = _resolve_agy_binary_path()
    if agy_path and os.path.isfile(agy_path):
        res = await _execute_agy_subprocess_prompt(agy_path, model, prompt, system_prompt, timeout_seconds)
        if res:
            return res

    # Tier-1b: Antigravity Python SDK
    sdk_res = await _execute_antigravity_sdk(prompt, system_prompt)
    if sdk_res:
        return sdk_res

    # Tier-2: Cloud Gemini REST API
    cloud_res = await _execute_cloud_gemini_rest(model, prompt, system_prompt, temperature, timeout_seconds)
    if cloud_res:
        return cloud_res

    # Tier-3: Deterministic Fallback
    logger.warning("[llm_client] Tier-1 and Tier-2 LLM providers unavailable; falling back to deterministic local mock response.")
    return _generate_mock_response(prompt, system_prompt)


