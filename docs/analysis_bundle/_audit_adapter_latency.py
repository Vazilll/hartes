"""Localise the 44s latency of the :5001 agy adapter.

Breaks the call chain into stages so we can attribute the cost:
  1. agy.exe --version      -> pure 183MB binary startup (no network)
  2. agy.exe -p (twice)     -> startup + IDE gateway round trip
  3. adapter POST (twice)   -> stage 2 + FastAPI/thread overhead
Read-only, no side effects other than one scratch/last_request.json write
performed by the adapter itself.
"""
import json
import subprocess
import time
import urllib.request

AGY = r"C:/Users/Vaz/AppData/Local/agy/bin/agy.exe"
PROMPT = "Reply with one word: OK"
MODEL = "Gemini 3.7 Flash (High)"
results = {}


def timed(label, fn):
    t = time.time()
    try:
        out = fn()
        el = time.time() - t
        print(f"{label}: {el:.1f}s -> {str(out)[:70]!r}", flush=True)
    except Exception as e:  # noqa: BLE001
        el = time.time() - t
        print(f"{label}: {el:.1f}s EXC {type(e).__name__}: {e}", flush=True)
        out = None
    results[label] = el
    return out


def agy_version():
    p = subprocess.run([AGY, "--version"], capture_output=True, timeout=120)
    return p.stdout.decode("utf-8", "replace").strip()


def agy_prompt():
    p = subprocess.run(
        [AGY, "-p", PROMPT, "--model", MODEL, "--print-timeout", "300s",
         "--output-format", "text", "--dangerously-skip-permissions"],
        capture_output=True, timeout=310,
    )
    return p.stdout.decode("utf-8", "replace").strip()


def adapter_post():
    payload = {"model": "gemini-3.7-flash", "messages": [{"role": "user", "content": PROMPT}]}
    req = urllib.request.Request(
        "http://127.0.0.1:5001/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=310) as r:  # noqa: S310
        body = json.loads(r.read().decode("utf-8", "replace"))
    return body.get("choices", [{}])[0].get("message", {}).get("content")


timed("1_agy_version_startup", agy_version)
timed("2_agy_prompt_cold", agy_prompt)
timed("3_agy_prompt_warm", agy_prompt)
timed("4_adapter_post", adapter_post)

print("\n== ATTRIBUTION ==")
v = results.get("1_agy_version_startup", 0)
w = results.get("3_agy_prompt_warm", 0)
a = results.get("4_adapter_post", 0)
print(f"binary startup (no net)   : {v:.1f}s")
print(f"agy prompt (warm)         : {w:.1f}s  -> network/model = {max(w - v, 0):.1f}s")
print(f"adapter POST              : {a:.1f}s  -> adapter overhead = {max(a - w, 0):.1f}s")
