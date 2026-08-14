import os
import sys
import time
import json
import urllib.request
import subprocess
from pathlib import Path
import psutil

if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

pid_file = Path("C:/vazus/vazus.pid")

# Ensure clean state: kill any running system_daemon processes and remove pid file
print("Ensuring clean state...")
subprocess.run([sys.executable, "-m", "vazus_core.system_daemon", "stop"], capture_output=True)
if pid_file.exists():
    try:
        pid_file.unlink()
    except Exception:
        pass
time.sleep(1)

# Launch daemon via transient parent process
print("Launching daemon via transient parent process...")
launcher = subprocess.run(
    [sys.executable, "-m", "vazus_core.system_daemon", "start"],
    capture_output=True, text=True, encoding="utf-8"
)
print("Launcher returncode:", launcher.returncode)
print("Launcher stdout:", repr(launcher.stdout.strip()))
print("Launcher stderr:", repr(launcher.stderr.strip()))

time.sleep(1)
print("PID file exists?:", pid_file.exists())
if pid_file.exists():
    pid = int(pid_file.read_text().strip())
    print("PID from file:", pid)
    print("Is PID running in psutil?:", psutil.pid_exists(pid))
    if psutil.pid_exists(pid):
        try:
            p = psutil.Process(pid)
            print(f"Process name: {p.name()}, status: {p.status()}, cmdline: {p.cmdline()}")
        except Exception as e:
            print("Could not inspect process:", e)
else:
    pid = None

print("\nWaiting 4 seconds to check if background process survived launcher termination...")
time.sleep(4)

try:
    with urllib.request.urlopen("http://127.0.0.1:8765/healthz", timeout=3) as resp:
        body = json.loads(resp.read().decode("utf-8"))
        print("HTTP healthz SUCCESS:", resp.status, body)
except Exception as e:
        print("HTTP healthz FAILED:", e)

if pid and psutil.pid_exists(pid):
    print("Stopping daemon...")
    subprocess.run([sys.executable, "-m", "vazus_core.system_daemon", "stop"], capture_output=True)
