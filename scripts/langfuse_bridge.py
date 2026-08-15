#!/usr/bin/env python3
r"""
langfuse_bridge.py — Forward Hermes observability traces to Langfuse V2.
Reads credentials from C:\vazus\pyenv\langfuse.env
"""
import sys, os, time
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

# Read credentials from fixed path
env_path = Path(r"C:\vazus\pyenv\langfuse.env")
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v)

pk = os.environ.get("LANGFUSE_PK", "")
sk = os.environ.get("LANGFUSE_SK", "")
host = os.environ.get("LANGFUSE_HOST", "http://127.0.0.1:3000")

# Privacy gate (audit V-11): disabled by default; external hosts are blocked.
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _is_local_host(url: str) -> bool:
    try:
        hostname = url.split("://", 1)[-1].split("/", 1)[0].split(":", 1)[0].strip("[]")
    except Exception:
        return False
    return hostname.lower() in _LOCAL_HOSTS


if os.environ.get("LANGFUSE_DISABLED", "1") == "1":
    print("Langfuse bridge: disabled by policy (LANGFUSE_DISABLED=1).", file=sys.stderr)
    sys.exit(0)

if not _is_local_host(host):
    print(f"Langfuse bridge: refusing external host {host} (privacy policy).", file=sys.stderr)
    sys.exit(0)

if not pk or not sk:
    print("No Langfuse credentials in langfuse.env", file=sys.stderr)
    sys.exit(1)

from langfuse import Langfuse
lf = Langfuse(public_key=pk, secret_key=sk, host=host)

# Send traces
try:
    tid = lf.trace(name="hermes_session", metadata={"action": "hook_trigger", "time": time.time()})
    lf.flush()
    print(f"Langfuse: trace {tid.id} sent OK")
except Exception as e:
    print(f"Langfuse error: {e}", file=sys.stderr)
    sys.exit(1)
