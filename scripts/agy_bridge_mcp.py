#!/usr/bin/env python3
"""
agy_bridge_mcp.py — REWRITTEN v2
Uses `agy` CLI (OAuth) instead of google.antigravity Python SDK.
No GEMINI_API_KEY dependency. No free tier quotas. Safe from ToS bans.

Based on official Antigravity CLI (agy) — Google's own product.
"""
import asyncio
import os
import sys
import logging
import shutil
from typing import List
from fastmcp import FastMCP

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("agy-cli-bridge")

mcp = FastMCP("Antigravity CLI Bridge")

# --- Find agy binary ---
AGY_PATH = shutil.which("agy")
if not AGY_PATH:
    # Common Windows paths
    for p in [
        r"C:\Users\Vaz\AppData\Local\agy\bin\agy.exe",
        r"C:\vazus\pyenv\.venv\Scripts\agy.exe",
        r"C:\vazus\pyenv\.venv\Scripts\agy",
    ]:
        if os.path.isfile(p):
            AGY_PATH = p
            break

if not AGY_PATH:
    logger.warning("agy CLI not found! Install from https://antigravity.google/docs/cli-getting-started")

logger.info(f"Using agy: {AGY_PATH}")

# Concurrency: 5 parallel max (safe for OAuth rate limits)
CONCURRENCY_LIMIT = 5
semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)


async def _run_agy(prompt: str, model: str = "gemini-3.5-flash",
                   timeout_sec: int = 300) -> str:
    """Run agy CLI as subprocess — pure OAuth, no API keys."""
    cmd = [
        AGY_PATH, "-p", prompt,
        "--model", model,
        "--print-timeout", f"{timeout_sec}s",
        "--dangerously-skip-permissions",
    ]
    async with semaphore:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout_sec + 15
            )
            if proc.returncode != 0 and proc.returncode != 124:
                err = stderr.decode('utf-8', errors='replace')[:300]
                logger.warning(f"agy exit {proc.returncode}: {err}")
                return f"[agy error: exit {proc.returncode}]"
            return stdout.decode('utf-8', errors='replace').strip()
        except asyncio.TimeoutError:
            proc.kill()
            return "[agy timeout]"


@mcp.tool()
async def run_antigravity_agent(
    prompt: str,
    system_instructions: str = "",
    model: str = "gemini-3.5-flash",
) -> str:
    """Runs a single Antigravity agent via agy CLI (OAuth).
    Use for: standalone tasks, research questions, code generation.
    """
    full_prompt = f"{system_instructions}\n\n{prompt}" if system_instructions else prompt
    return await _run_agy(full_prompt, model=model)


@mcp.tool()
async def run_parallel_antigravity_agents(
    prompts: List[str],
    system_instructions: str = "",
    model: str = "gemini-3.5-flash",
) -> List[str]:
    """Concurrently executes multiple Antigravity agents (max 5 parallel).
    Use for: deep research, parallel code review, multi-angle analysis.
    Each agent is independent — results come back as a list.
    """
    logger.info(f"Running {len(prompts)} parallel agents (concurrency={CONCURRENCY_LIMIT})")
    full_prompts = [
        f"{system_instructions}\n\n{p}" if system_instructions else p
        for p in prompts
    ]
    tasks = [_run_agy(p, model=model) for p in full_prompts]
    return await asyncio.gather(*tasks)


@mcp.tool()
async def run_antigravity_subagents(
    task_description: str,
    num_subagents: int = 5,
    context: str = "",
) -> str:
    """Sequential decomposition planner via agy CLI.
    Breaks task into steps, solves each, synthesizes final report.
    """
    prompt = (
        f"You are a Sequential Decomposition Planner.\n"
        f"Task: '{task_description}'.\n"
        f"Context: {context}\n\n"
        f"1. Break this task into {num_subagents} sequential sub-tasks.\n"
        f"2. Solve each step one by one, maintaining progress.\n"
        f"3. Combine all outputs into a structured final synthesis report."
    )
    return await _run_agy(prompt)


@mcp.tool()
async def run_vision_agent(
    prompt: str,
    image_path: str,
    model: str = "gemini-2.5-flash",
) -> str:
    """Vision analysis via agy CLI (if supported) or Gemini API.
    NOTE: agy CLI may not support direct image input.
    Falls back to Gemini API key if available.
    """
    # Try agy CLI with image first (if future version supports it)
    # For now, use the Gemini API key approach as fallback
    import base64
    api_key = os.environ.get('GEMINI_API_KEY', '')
    if api_key:
        try:
            from google import genai
            if not os.path.isfile(image_path):
                return f"Image not found: {image_path}"
            ext = os.path.splitext(image_path)[1].lower()
            mime_map = {'.png': 'image/png', '.jpg': 'image/jpeg',
                       '.jpeg': 'image/jpeg', '.webp': 'image/webp',
                       '.gif': 'image/gif', '.bmp': 'image/bmp',
                       '.tiff': 'image/tiff', '.tif': 'image/tiff'}
            mime = mime_map.get(ext, 'image/png')
            client = genai.Client(api_key=api_key)
            with open(image_path, 'rb') as f:
                img_data = f.read()
            b64 = base64.b64encode(img_data).decode()
            response = client.models.generate_content(
                model=model,
                contents=[prompt, {'inline_data': {'mime_type': mime, 'data': b64}}]
            )
            return response.text
        except Exception as e:
            return f"Vision via API failed: {e}"
    return "Vision unavailable: no GEMINI_API_KEY and agy CLI doesn't support images"


if __name__ == "__main__":
    mcp.run()
