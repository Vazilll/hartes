#!/usr/bin/env python3
"""dnts-rlm MCP — Recursive Language Model worker server.

Routes RLM tasks to vazus_core.workers.rlm (MIT RLM engine).
Each run is multi-step reasoning with tool execution.
"""
import sys
import json

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
sys.path.insert(0, "C:/vazus/pyenv")

from fastmcp import FastMCP
from vazus_core import database
from vazus_core.workers import rlm as _rlm

MCP = FastMCP("dnts-rlm")


@MCP.tool(description=(
    "Run a multi-step RLM (Recursive Language Model) reasoning task. "
    "The model iterates, uses tools, and self-corrects until it solves the task. "
    "Returns the final answer. May take 10-120s depending on complexity."
))
def run_rlm(
    prompt: str,
    context: str = "",
    max_iterations: int = 5,
    max_depth: int = 3,
    task_id: str = "rlm-mcp",
) -> str:
    try:
        result = _rlm.run_rlm(
            prompt=prompt,
            context=context,
            max_iterations=max_iterations,
            max_depth=max_depth,
            task_id=task_id,
        )
        if result.get("success"):
            return result.get("result", "(no output)")
        return f"RLM failed: {result.get('error', 'unknown')}"
    except Exception as e:
        return f"Error: {e}"


@MCP.tool(description="List recent RLM tasks and their statuses from the database.")
def list_rlm_tasks(limit: int = 20) -> str:
    try:
        tasks = database.list_tasks(limit=limit)
        if not tasks:
            return "No tasks found."
        lines = []
        for t in tasks:
            tid = t.get("task_id", "?")
            status = t.get("status", "?")
            ts = t.get("created_at", "")[:19]
            lines.append(f"[{status}] {tid} ({ts})")
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"


@MCP.tool(description="Get detailed result of a specific RLM task by task_id.")
def get_rlm_task(task_id: str) -> str:
    try:
        tasks = database.list_tasks()
        for t in tasks:
            if t.get("task_id") == task_id:
                return json.dumps(t, ensure_ascii=False, indent=2, default=str)
        return f"Task '{task_id}' not found."
    except Exception as e:
        return f"Error: {e}"


if __name__ == "__main__":
    MCP.run()
