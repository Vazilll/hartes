#!/usr/bin/env python3
r"""
langfuse_bridge.py — Forward Hermes observability traces to Langfuse V2.
Reads credentials from C:\vazus\pyenv\langfuse.env
"""
import sys, os, json, time
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
host = os.environ.get("LANGFUSE_HOST", "http://213.165.36.252:3000")

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
