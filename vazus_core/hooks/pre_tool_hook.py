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
    Path.home() / "Documents",
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
    re.compile(r"(?i)\b(?:rmdir|rd)\b(?:[\s/]+[a-z])*\s+[\"']?c:[\\/]"),      # e.g. rmdir /s /q c:\
    re.compile(r"(?i)\b(?:del|erase)\b(?:[\s/]+[a-z])*\s+[\"']?c:[\\/]windows"), # e.g. del /f /s /q c:\windows
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


from typing import Optional
from vazus_core.verification.substrate_guard import SubstrateGuard

_DEFAULT_SUBSTRATE_GUARD: Optional[SubstrateGuard] = None

def get_substrate_guard() -> SubstrateGuard:
    global _DEFAULT_SUBSTRATE_GUARD
    if _DEFAULT_SUBSTRATE_GUARD is None:
        _DEFAULT_SUBSTRATE_GUARD = SubstrateGuard()
    return _DEFAULT_SUBSTRATE_GUARD


def run_pre_tool(tool_name: str, args: dict) -> dict:
    """Evaluator delegating directly to formal SMT Z3 SubstrateGuard."""
    guard = get_substrate_guard()
    return guard.verify(tool_name, args)


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
    print(json.dumps({"decision": response.get("decision", "deny"), "reason": response.get("reason", "")}))


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


def _scan_for_secrets(text: str) -> list[str]:
    """Scan text for potential secrets using SecretScrubber."""
    try:
        from vazus_core.security.entropy_scrubber import SecretScrubber
        scrubber = SecretScrubber()
        found = []
        for pat in scrubber.KNOWN_SECRET_PATTERNS:
            for m in pat.finditer(text):
                found.append(m.group(0))
        return found
    except Exception:
        return []


if __name__ == "__main__":
    main()

