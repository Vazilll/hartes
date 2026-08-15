import sys
import time
import json
import urllib.request
import subprocess

print("=== STEP 1: py_compile vazus_core/system_daemon.py ===", flush=True)
comp = subprocess.run([sys.executable, "-m", "py_compile", "vazus_core/system_daemon.py"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
print(f"py_compile exit code: {comp.returncode}", flush=True)
assert comp.returncode == 0, "py_compile failed"

print("\n=== STEP 2: python -m vazus_core.system_daemon start ===", flush=True)
start_res = subprocess.run([sys.executable, "-m", "vazus_core.system_daemon", "start"], stdout=None, stderr=None, text=True)
print(f"start exit code: {start_res.returncode}", flush=True)
assert start_res.returncode == 0, "start failed"

time.sleep(2)

print("\n=== STEP 3: python -m vazus_core.system_daemon status ===", flush=True)
status_res = subprocess.run([sys.executable, "-m", "vazus_core.system_daemon", "status"], stdout=None, stderr=None, text=True)
print(f"status exit code: {status_res.returncode}", flush=True)
assert status_res.returncode == 0, "status failed"

print("\n=== STEP 4: HTTP GET http://127.0.0.1:8765/status ===", flush=True)
try:
    with urllib.request.urlopen("http://127.0.0.1:8765/status", timeout=5) as resp:
        code = resp.getcode()
        body_text = resp.read().decode("utf-8")
        payload = json.loads(body_text)
        print(f"HTTP response code: {code}", flush=True)
        print(f"HTTP JSON status payload:\n{json.dumps(payload, indent=2)}", flush=True)
        assert code == 200, f"Expected 200 OK, got {code}"
        assert payload.get("status") in ["ok", "degraded"], "Invalid payload status"
except Exception as e:
    print(f"HTTP GET failed: {e}", flush=True)
    raise

print("\n=== STEP 5: python -m vazus_core.system_daemon stop ===", flush=True)
stop_res = subprocess.run([sys.executable, "-m", "vazus_core.system_daemon", "stop"], stdout=None, stderr=None, text=True)
print(f"stop exit code: {stop_res.returncode}", flush=True)
assert stop_res.returncode == 0, "stop failed"

print("\n=== ALL 5 VERIFICATION STEPS PASSED SUCCESSFULLY ===", flush=True)
