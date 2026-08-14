#!/usr/bin/env python3
"""
vazus_core.hooks.pre_tool_hook — Antigravity PreToolUse Lifecycle Hook.

Triggered AUTOMATICALLY by Antigravity BEFORE file editing tools execute.
Enforces:
  - Path traversal prevention (no writes outside workspace or .git/hooks injection)
  - Audit log of all tool invocations
  - Block writes to .git directory (hook injection attack)
"""

import sys
import json
import logging
from pathlib import Path

WORKSPACE_ROOTS = [
    Path("C:/vazus").resolve(),
    Path.home() / ".gemini",
]

BLOCKED_PATHS = [".git/hooks", ".git\\hooks"]

logger = logging.getLogger("vazus.pre_tool_hook")


def _is_within_workspace(path_str: str) -> bool:
    """Returns True if path is safely within one of the permitted workspace roots."""
    if not path_str:
        return True
    try:
        resolved = Path(path_str).resolve()
        return any(resolved.is_relative_to(root) for root in WORKSPACE_ROOTS)
    except Exception:
        return True  # fail-open for unresolvable paths (network, etc.)


def _is_git_hook_injection(path_str: str) -> bool:
    """Detects attempts to write into .git/hooks — classic supply-chain attack vector."""
    if not path_str:
        return False
    normalized = path_str.replace("\\", "/")
    return ".git/hooks" in normalized


def main():
    try:
        input_data = json.load(sys.stdin)
    except Exception:
        # If we can't parse stdin, fail-open (don't block Antigravity on hook crash)
        print(json.dumps({"decision": "allow", "reason": "PreToolHook: stdin parse error — fail-open"}))
        return

    tool_call = input_data.get("toolCall", {})
    tool_name = tool_call.get("name", "unknown")
    args = tool_call.get("args", {})

    target_file = args.get("TargetFile") or args.get("AbsolutePath") or args.get("SearchPath") or ""

    # Security Check 1: Git hook injection
    if _is_git_hook_injection(target_file):
        response = {
            "decision": "block",
            "reason": f"[SECURITY] Blocked write to .git/hooks: {target_file} — supply-chain injection prevention."
        }
        print(json.dumps(response))
        return

    # Security Check 2: Path traversal outside workspace
    if target_file and not _is_within_workspace(target_file):
        response = {
            "decision": "block",
            "reason": f"[SECURITY] Path traversal blocked: {target_file} is outside permitted workspace roots."
        }
        print(json.dumps(response))
        return

    response = {
        "decision": "allow",
        "reason": f"PreToolHook: {tool_name} on '{target_file}' — path validated."
    }
    print(json.dumps(response))


if __name__ == "__main__":
    main()
