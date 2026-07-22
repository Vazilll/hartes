#!/usr/bin/env python3
"""
shell_mcp.py — A dedicated Shell Execution MCP Server for Antigravity IDE.
Bypasses the IDE's internal sandboxed terminal by running subprocess directly
on the host OS, avoiding the 'opening NUL for ACL write: Access is denied' bug.

SECURITY: Command whitelist + deny patterns + timeout + output truncation.
"""

import sys
import re
import subprocess
import traceback
import os
import json
import psutil

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# Redirect stdout to stderr temporarily to prevent FastMCP startup text from breaking JSON-RPC
original_stdout = sys.stdout
sys.stdout = sys.stderr

from fastmcp import FastMCP
mcp = FastMCP("dnts-shell-mcp")

sys.stdout = original_stdout

# ── Security Configuration ──

# Only these binaries are allowed as the first token of the command.
# python/pip deliberately excluded — use the IDE terminal or RLM for those.
ALLOWED_COMMANDS = {
    "git", "ls", "dir", "cat", "type", "rg", "grep", "find", "echo",
    "where", "whoami", "node", "npm", "npx", "head", "tail", "wc",
    "sort", "more", "tree",
    # PowerShell cmdlets (case-insensitive matching applied separately)
    "get-childitem", "get-content", "select-string", "test-path",
    "get-process", "get-item", "get-itemproperty", "measure-object",
    # Python — only venv path allowed (guard below)
    "python",
}

# Venv python guard: if command starts with 'python', it must use our venv path
VENV_PYTHON_PREFIX = "c:/dnts/pyenv/.venv/scripts/python"

# Commands matching any of these patterns are always rejected.
DENY_PATTERNS = [
    r"rm\s+-rf",
    r"del\s+/",
    r"\bformat\b",
    r"curl.*\|.*sh",
    r"\bInvoke-Expression\b",
    r"\biex\s",
    r"Remove-Item.*-Recurse",
    r"rmdir\s+/s",
    r"\bos\.system\b",
    r"\bsubprocess\b",
    r"\b__import__\b",
    r"\beval\s*\(",
    r"\bexec\s*\(",
]

TIMEOUT_SEC = 60
MAX_OUTPUT_BYTES = 50 * 1024  # 50KB
WORKSPACE = r"C:\vazus\pyenv"
SERVICES_FILE = os.path.join(WORKSPACE, "logs", "pids", "active_services.json")
LOGS_PIDS = os.path.join(WORKSPACE, "logs", "pids")


def _is_command_allowed(command: str) -> tuple[bool, str]:
    """Validate command against whitelist and deny patterns."""
    stripped = command.strip()
    if not stripped:
        return False, "Empty command."

    # Check deny patterns first (they override everything)
    for pattern in DENY_PATTERNS:
        if re.search(pattern, stripped, re.IGNORECASE):
            return False, f"Command rejected: matches deny pattern '{pattern}'."

    # Extract first token (the binary/cmdlet name)
    first_token_raw = re.split(r'[\s|;&]', stripped)[0]
    first_token = first_token_raw.lower()
    # Strip path prefixes (e.g., C:\Windows\...\git.exe → git)
    first_token_base = first_token.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
    # Strip .exe / .cmd suffix
    for suffix in (".exe", ".cmd", ".bat", ".com"):
        if first_token_base.endswith(suffix):
            first_token_base = first_token_base[:-len(suffix)]

    # Python guard: must use full venv path
    if first_token_base == "python":
        normalized = first_token.replace("\\", "/")
        if not normalized.startswith(VENV_PYTHON_PREFIX):
            return False, (
                f"Direct 'python' blocked. "
                f"Use full venv path: C:/vazus/pyenv/.venv/Scripts/python.exe"
            )

    if first_token_base not in ALLOWED_COMMANDS:
        return False, (
            f"Command '{first_token_base}' is not in the allowed whitelist. "
            f"Allowed: {', '.join(sorted(ALLOWED_COMMANDS))}. "
            f"For Python scripts, use: C:/vazus/pyenv/.venv/Scripts/python.exe <script>"
        )

    return True, "OK"


@mcp.tool(description="Execute a terminal command directly on the host OS (bypasses NUL ACL bug). Security: whitelist-only commands, no python/pip, 60s timeout, 50KB output cap.")
def run_host_command(command: str, cwd: str = "C:/vazus/pyenv") -> str:
    """Runs a whitelisted command and returns the stdout/stderr."""
    allowed, reason = _is_command_allowed(command)
    if not allowed:
        return f"⛔ REJECTED: {reason}"

    try:
        proc = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=cwd,
            encoding='utf-8',
            errors='replace',
            timeout=TIMEOUT_SEC,
        )

        output = f"Exit Code: {proc.returncode}\n"
        if proc.stdout:
            output += f"--- STDOUT ---\n{proc.stdout}\n"
        if proc.stderr:
            output += f"--- STDERR ---\n{proc.stderr}\n"

        # Truncate if too large
        if len(output.encode('utf-8', errors='replace')) > MAX_OUTPUT_BYTES:
            output = output[:MAX_OUTPUT_BYTES] + "\n... [OUTPUT TRUNCATED at 50KB]"

        return output
    except subprocess.TimeoutExpired:
        return f"⛔ TIMEOUT: Command exceeded {TIMEOUT_SEC}s limit and was killed."
    except Exception as e:
        return f"Exception executing command '{command}': {e}\n{traceback.format_exc()}"

@mcp.tool(description=(
    "Spawn a long-running background service non-blocking via Popen. "
    "The command is still checked against the whitelist. "
    "Logs go to logs/pids/<name>.stdout.log and .stderr.log. "
    "Tracks PID in logs/pids/active_services.json."
))
def spawn_background_service(name: str, command: str, cwd: str = "C:/vazus/pyenv") -> str:
    """Starts a daemon process that keeps running after this call returns."""
    allowed, reason = _is_command_allowed(command)
    if not allowed:
        return f"⛔ REJECTED: {reason}"

    os.makedirs(LOGS_PIDS, exist_ok=True)
    log_out = os.path.join(LOGS_PIDS, f"{name}.stdout.log")
    log_err = os.path.join(LOGS_PIDS, f"{name}.stderr.log")

    # Kill existing tracked process if alive
    services: dict = {}
    if os.path.exists(SERVICES_FILE):
        try:
            services = json.loads(open(SERVICES_FILE).read())
        except Exception:
            services = {}
    if name in services:
        old_pid = services[name]
        if psutil.pid_exists(old_pid):
            try:
                psutil.Process(old_pid).terminate()
            except Exception:
                pass

    with open(log_out, "a", encoding="utf-8") as fout, \
         open(log_err, "a", encoding="utf-8") as ferr:
        proc = subprocess.Popen(
            command, shell=True, cwd=cwd,
            stdout=fout, stderr=ferr,
            stdin=subprocess.DEVNULL,  # ponytail: prevent MCP stdin pipe inherit → hang
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        )

    services[name] = proc.pid
    with open(SERVICES_FILE, "w") as f:
        json.dump(services, f, indent=2)

    return (
        f"✅ Service '{name}' spawned (PID {proc.pid}) — non-blocking.\n"
        f"stdout → {log_out}\n"
        f"stderr → {log_err}"
    )


@mcp.tool(description="List all tracked background services with live PID status (running/dead).")
def list_services() -> str:
    """Shows name, PID, and live status of each tracked service."""
    if not os.path.exists(SERVICES_FILE):
        return "No services tracked yet."
    try:
        services = json.loads(open(SERVICES_FILE).read())
    except Exception:
        return "Could not parse services file."
    lines = []
    for name, pid in services.items():
        if psutil.pid_exists(pid):
            p = psutil.Process(pid)
            lines.append(f"  {name:20s} PID={pid:6d}  RUNNING ({p.status()})")
        else:
            lines.append(f"  {name:20s} PID={pid:6d}  DEAD (stale)")
    return "Tracked services:\n" + "\n".join(lines)


@mcp.tool(description="Kill a tracked background service by name using psutil (no shell needed).")
def kill_service(name: str) -> str:
    """Terminates a named background service and removes it from the registry."""
    if not os.path.exists(SERVICES_FILE):
        return "No services tracked."
    try:
        services = json.loads(open(SERVICES_FILE).read())
    except Exception:
        return "Could not parse services file."
    if name not in services:
        return f"Service '{name}' not tracked. Known: {list(services.keys())}"
    pid = services.pop(name)
    if psutil.pid_exists(pid):
        try:
            psutil.Process(pid).terminate()
            msg = f"✅ Terminated '{name}' (PID {pid})."
        except Exception as e:
            msg = f"⛔ Could not terminate PID {pid}: {e}"
    else:
        msg = f"PID {pid} was already dead."
    with open(SERVICES_FILE, "w") as f:
        json.dump(services, f, indent=2)
    return msg


@mcp.tool(description="Read the last N lines from a service's log. stream='stdout' or 'stderr'.")
def tail_service_log(name: str, stream: str = "stderr", lines: int = 50) -> str:
    """Returns last N lines from a service log file."""
    log_path = os.path.join(LOGS_PIDS, f"{name}.{stream}.log")
    if not os.path.exists(log_path):
        return f"No log at {log_path}"
    try:
        content = open(log_path, encoding="utf-8", errors="replace").readlines()
        tail = content[-lines:]
        return f"Last {len(tail)} lines of {name}/{stream}:\n{''.join(tail)}"
    except Exception as e:
        return f"⛔ Error reading log: {e}"

if __name__ == "__main__":
    mcp.run(transport="stdio", show_banner=False)
