import urllib.request
import urllib.error
import json

base_url = "http://127.0.0.1:8765"
endpoints = [
    "/",
    "/api/v1/system",
    "/api/v1/universe",
    "/api/v1/ledger",
    "/api/v1/full-graph",
    "/api/v1/code-graph/status"
]

print("=== TESTING LIVE WEB SERVER ENDPOINTS ON PORT 8765 ===")
for ep in endpoints:
    url = f"{base_url}{ep}"
    req = urllib.request.Request(url, headers={"Host": "127.0.0.1:8765"})
    try:
        with urllib.request.urlopen(req) as resp:
            data = resp.read()
            print(f"[PASS] {ep} -> Status: {resp.status}, Content Length: {len(data)} bytes")
            if ep.startswith("/api"):
                try:
                    parsed = json.loads(data.decode("utf-8"))
                    print(f"       Keys: {list(parsed.keys())}")
                except Exception:
                    pass
    except urllib.error.HTTPError as e:
        print(f"[FAIL] {ep} -> HTTP {e.code}: {e.reason}")
    except Exception as e:
        print(f"[ERROR] {ep} -> {e}")
