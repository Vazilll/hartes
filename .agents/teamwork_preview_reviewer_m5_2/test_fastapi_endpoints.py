import sys
import json
from pathlib import Path

ROOT_DIR = Path("C:/vazus")
for p in [str(ROOT_DIR), str(ROOT_DIR / "labs" / "raytsystem" / "src")]:
    if p not in sys.path:
        sys.path.insert(0, p)

from raytsystem.webapp import create_app
from fastapi.testclient import TestClient

app = create_app(ROOT_DIR / "labs" / "raytsystem")
client = TestClient(app, headers={"host": "127.0.0.1:8765"})

endpoints = [
    "/",
    "/api/v1/system",
    "/api/v1/universe",
    "/api/v1/ledger",
    "/api/v1/full-graph",
    "/api/v1/code-graph/status"
]

print("=== FASTAPI TEST CLIENT ENDPOINT VERIFICATION ===", flush=True)
for ep in endpoints:
    r = client.get(ep)
    print(f"Endpoint '{ep}': HTTP Status = {r.status_code}, Length = {len(r.content)} bytes", flush=True)
    if r.status_code == 200 and ep.startswith("/api"):
        try:
            data = r.json()
            if isinstance(data, dict):
                print(f"   Keys: {list(data.keys())[:8]}", flush=True)
            elif isinstance(data, list):
                print(f"   Items count: {len(data)}", flush=True)
        except Exception as e:
            print(f"   JSON parse note: {e}", flush=True)

print("=== END OF VERIFICATION ===", flush=True)
