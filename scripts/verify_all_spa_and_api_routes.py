"""
scripts/verify_all_spa_and_api_routes.py — Comprehensive verification of all Raytsystem SPA and API routes.

Checks:
1. All 12 SPA client routes defined in app.py (_SPA_ROUTES).
2. All underlying REST API endpoints (/api/v1/...).
3. Reports status, content length, and diagnostic state.
"""

import sys
import json
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

BASE_URL = "http://127.0.0.1:8765"


SPA_ROUTES = [
    "",
    "command-center",
    "handbook",
    "documents",
    "onboarding",
    "tasks",
    "universe",
    "runs",
    "agents",
    "skills",
    "context",
    "safety",
    "systems",
]

API_ENDPOINTS = [
    "/api/v1/code-graph/status",
    "/api/v1/system",
    "/api/v1/handbook",
    "/api/v1/execution/features",
    "/api/v1/catalog",
    "/api/v1/skills",
    "/api/v1/execution/runtime-health",
    "/api/v1/tasks",
    "/api/v1/agents",
]


def test_spa_routes():
    print("=" * 70)
    print("🖥️ 1. TESTING SPA CLIENT-SIDE ROUTES (Single Page App HTML Fallback)")
    print("=" * 70)

    for route in SPA_ROUTES:
        url = f"{BASE_URL}/{route}" if route else BASE_URL
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Route-Checker/1.0"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                status = resp.status
                body = resp.read().decode("utf-8", errors="ignore")
                has_root = '<div id="root">' in body
                has_script = "index-qPGf_in8.js" in body
                is_valid_spa = has_root and has_script
                print(f"   - Status {status} | Route: /{route:20s} | SPA HTML Valid: {'✅ YES' if is_valid_spa else '❌ NO'} | Size: {len(body)}B")
        except Exception as e:
            print(f"   - ❌ ERROR  | Route: /{route:20s} | {e}")


def test_api_endpoints():
    print("\n" + "=" * 70)
    print("⚙️ 2. TESTING BACKEND REST API ENDPOINTS (/api/v1/...)")
    print("=" * 70)

    for endpoint in API_ENDPOINTS:
        url = f"{BASE_URL}{endpoint}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Route-Checker/1.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                status = resp.status
                data = resp.read().decode("utf-8", errors="ignore")
                parsed = json.loads(data)
                keys = list(parsed.keys())[:4] if isinstance(parsed, dict) else f"Array len={len(parsed)}"
                print(f"   - Status {status} | Endpoint: {endpoint:35s} | Response: {keys}")
        except Exception as e:
            print(f"   - ❌ ERROR  | Endpoint: {endpoint:35s} | {e}")


if __name__ == "__main__":
    test_spa_routes()
    test_api_endpoints()
