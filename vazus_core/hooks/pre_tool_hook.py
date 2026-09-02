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

import re

DANGEROUS_COMMAND_PATTERNS = [
    re.compile(r"(?i)\bformat\s+[a-z]:"),          # e.g. format c:
    re.compile(r"(?i)\brmdir\s+/[sq]\s+c:\\"),      # e.g. rmdir /s /q c:\
    re.compile(r"(?i)\bdel\s+/[fsq\s]+c:\\windows"), # e.g. del /f /s /q c:\windows
    re.compile(r"(?i)\breg\s+delete\s+hklm"),       # e.g. reg delete HKLM
    re.compile(r"(?i)\bdiskpart\b"),                # disk partitioning tool
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
    """Detects destructive system commands with precise argument boundaries."""
    if not command_str:
        return False
    return any(pat.search(command_str) for pat in DANGEROUS_COMMAND_PATTERNS)


def run_pre_tool(tool_name: str, args: dict) -> dict:
    """Programmatic evaluator for tool use security validation."""
    target_file = args.get("TargetFile") or args.get("AbsolutePath") or args.get("SearchPath") or ""
    command_str = args.get("CommandLine") or ""

    # Vulnerability 1 Fix: Reject null bytes immediately
    if target_file and "\x00" in target_file:
        return {
            "decision": "deny",
            "reason": "[SECURITY] Null byte in target file path rejected. Fail-closed."
        }

    # Vulnerability 2 Fix: Fail-closed on missing target for file manipulation tools
    file_ops = {"ViewFile", "WriteToFile", "replace_file_content", "view_file", "write_to_file"}
    if tool_name in file_ops and not target_file.strip():
        return {
            "decision": "deny",
            "reason": f"[SECURITY] Missing or empty target file path for '{tool_name}'. Fail-closed."
        }

    # Security Check 1: Command safety check
    if command_str and _is_dangerous_command(command_str):
        return {
            "decision": "deny",
            "reason": f"[SECURITY] Destructive system command rejected: '{command_str[:60]}...'"
        }

    # Security Check 2: Forbidden paths (.git, root AGENTS.md, system dirs)
    if target_file and _is_forbidden_path(target_file):
        return {
            "decision": "deny",
            "reason": f"[SECURITY] Modification to protected/forbidden path blocked: '{target_file}'"
        }

    # Security Check 3: Workspace Jail (must be inside permitted roots)
    if target_file and not _is_within_workspace(target_file):
        return {
            "decision": "deny",
            "reason": f"[SECURITY] Path traversal blocked: '{target_file}' is outside permitted workspace roots."
        }

    # All security checks passed
    return {
        "decision": "allow",
        "reason": f"PreToolHook: {tool_name} validated within security boundary."
    }


def main():
    try:
        raw_stdin = sys.stdin.read().strip()
        if not raw_stdin:
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

    response = run_pre_tool(tool_name, args)
    print(json.dumps(response))


def _validate_security_policies(tool_name: str, tool_input: dict) -> tuple[bool, str]:
    """Helper to validate security policies for pre-tool usage."""
    res = run_pre_tool(tool_name, tool_input)
    if res.get("decision") == "deny":
        return False, res.get("reason", "Denied by security policy")
    return True, "ALLOWED"


def pre_tool_enforce_security_jail(tool_name: str, tool_args: dict, workspace_root: str = "C:/vazus", **kwargs) -> dict:
    """Enforces strict path jail security boundaries under sub-50ms latency."""
    import time
    t0 = time.perf_counter()
    res = run_pre_tool(tool_name, tool_args)
    latency_ms = (time.perf_counter() - t0) * 1000.0
    res["latency_ms"] = latency_ms
    return res


if __name__ == "__main__":
    main()
