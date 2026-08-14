#!/usr/bin/env python3
"""
vazus_core.hooks.pre_tool_hook — Antigravity PreToolUse Lifecycle Hook (Fail-Closed Security Gate).

Triggered AUTOMATICALLY by Antigravity BEFORE file editing and command execution tools run.
Enforces:
  - Fail-Closed Policy: Stdin parse errors or unhandled exceptions REJECT execution.
  - Strict Path Jail: Only paths inside C:/vazus and ~/.gemini are writable.
  - Core Contract Protection: Blocks writes to .git directory and root AGENTS.md.
  - Dangerous Command Filter: Rejects destructive OS/registry wipe attempts.
"""

import sys
import json
import logging
from pathlib import Path

WORKSPACE_ROOTS = [
    Path("C:/vazus").resolve(),
    Path.home() / ".gemini",
    Path.home() / ".hermes",
    Path.home() / ".mcp-colab",
]

# Sensitive paths forbidden for agent modification
FORBIDDEN_PATTERNS = [
    ".git/",
    ".git\\",
    "windows/system32",
    "windows\\system32",
    "/etc/",
    "C:/vazus/AGENTS.md",
    "C:\\vazus\\AGENTS.md",
]

DANGEROUS_COMMANDS = [
    "format ",
    "rmdir /s /q c:\\",
    "del /f /s /q c:\\windows",
    "reg delete",
    "diskpart",
]

logger = logging.getLogger("vazus.pre_tool_hook")


def _is_within_workspace(path_str: str) -> bool:
    """Returns True if path is safely within permitted workspace roots. Fail-Closed on error."""
    if not path_str:
        return False
    try:
        resolved = Path(path_str).resolve()
        return any(resolved.is_relative_to(root) for root in WORKSPACE_ROOTS)
    except Exception as e:
        logger.error(f"[PreToolHook] Failed to resolve path '{path_str}': {e}")
        return False  # FAIL-CLOSED


def _is_forbidden_path(path_str: str) -> bool:
    """Detects attempts to write into .git, system paths, or immutable AGENTS.md."""
    if not path_str:
        return False
    normalized = path_str.replace("\\", "/").lower()
    return any(p.lower().replace("\\", "/") in normalized for p in FORBIDDEN_PATTERNS)


def _is_dangerous_command(command_str: str) -> bool:
    """Detects destructive system commands."""
    if not command_str:
        return False
    cmd_lower = command_str.lower()
    return any(danger in cmd_lower for danger in DANGEROUS_COMMANDS)


def main():
    try:
        raw_stdin = sys.stdin.read()
        if not raw_stdin or not raw_stdin.strip():
            # FAIL-CLOSED on empty input
            print(json.dumps({"decision": "deny", "reason": "[SECURITY] PreToolHook: Empty stdin received. Fail-closed."}))
            return
        input_data = json.loads(raw_stdin)
    except Exception as e:
        # FAIL-CLOSED on stdin parse error
        print(json.dumps({"decision": "deny", "reason": f"[SECURITY] PreToolHook parse error ({e}). Fail-closed."}))
        return

    tool_call = input_data.get("toolCall", {})
    tool_name = tool_call.get("name", "unknown")
    args = tool_call.get("args", {})

    target_file = args.get("TargetFile") or args.get("AbsolutePath") or args.get("SearchPath") or ""
    command_str = args.get("CommandLine") or ""

    # Security Check 1: Command safety check
    if command_str and _is_dangerous_command(command_str):
        response = {
            "decision": "deny",
            "reason": f"[SECURITY] Destructive system command rejected: '{command_str[:60]}...'"
        }
        print(json.dumps(response))
        return

    # Security Check 2: Forbidden paths (.git, root AGENTS.md, system dirs)
    if target_file and _is_forbidden_path(target_file):
        response = {
            "decision": "deny",
            "reason": f"[SECURITY] Modification to protected/forbidden path blocked: '{target_file}'"
        }
        print(json.dumps(response))
        return

    # Security Check 3: Workspace Jail (must be inside permitted roots)
    if target_file and not _is_within_workspace(target_file):
        response = {
            "decision": "deny",
            "reason": f"[SECURITY] Path traversal blocked: '{target_file}' is outside permitted workspace roots."
        }
        print(json.dumps(response))
        return

    # All security checks passed
    response = {
        "decision": "allow",
        "reason": f"PreToolHook: {tool_name} validated within security boundary."
    }
    print(json.dumps(response))


if __name__ == "__main__":
    main()
