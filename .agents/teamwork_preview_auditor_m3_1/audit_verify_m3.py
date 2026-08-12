"""
audit_verify_m3.py -- Forensic Auditor Empirical Test Suite for Milestone 3 (Requirement R2)
"""

import sys
import json
import urllib.request
import urllib.parse
import http.cookiejar
from pathlib import Path

BASE_URL = "http://127.0.0.1:8765"

def run_forensic_audit():
    print("=" * 80)
    print("VAZUS SUPERGRAPH OS -- MILESTONE 3 (REQUIREMENT R2) FORENSIC INTEGRITY TEST")
    print(f"Target Server: {BASE_URL}")
    print("=" * 80)

    # 1. SPA Routes & Dynamic CSP Nonce Verification
    print("\n[CHECK 1] Verifying SPA Routes & Dynamic CSP Nonce...")
    spa_routes = ["/universe", "/command-center", "/tasks", "/agents", "/skills", "/runs"]
    nonces = []
    
    for route in spa_routes:
        url = f"{BASE_URL}{route}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200, f"Route {route} returned status {resp.status}"
            content = resp.read().decode("utf-8")
            assert '<meta name="raytsystem-csp-nonce" content="' in content, f"Route {route} missing CSP nonce tag"
            
            # Extract nonce
            start = content.find('<meta name="raytsystem-csp-nonce" content="') + len('<meta name="raytsystem-csp-nonce" content="')
            end = content.find('"', start)
            nonce = content[start:end]
            nonces.append(nonce)
            print(f"  [PASS] Route {route:16} -> HTTP 200 | CSP Nonce: {nonce[:16]}...")

    assert len(set(nonces)) == len(spa_routes), f"Nonces were not unique! Got {len(set(nonces))} unique out of {len(spa_routes)}"
    print(f"  [PASS] Dynamic CSP Nonce verified: {len(set(nonces))} unique nonces generated across {len(spa_routes)} requests.")

    # 2. Host Validation / Security Middleware Verification
    print("\n[CHECK 2] Verifying Host Header Security Middleware...")
    try:
        req = urllib.request.Request(f"{BASE_URL}/api/v1/system", headers={"Host": "unauthorized-domain.com"})
        with urllib.request.urlopen(req) as resp:
            print(f"  [FAIL] Security check failed, request with Host 'unauthorized-domain.com' succeeded with {resp.status}")
            sys.exit(1)
    except urllib.error.HTTPError as e:
        assert e.code in (400, 421, 403), f"Unexpected status code for host rejection: {e.code}"
        print(f"  [PASS] Rejected non-loopback Host header 'unauthorized-domain.com' with HTTP {e.code}")

    # 3. 3D SuperGraph Topology Snapshot (/api/v1/universe) Verification
    print("\n[CHECK 3] Verifying 3D SuperGraph Topology JSON (/api/v1/universe)...")
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    
    # First get SPA page to establish session cookie
    r1 = opener.open(f"{BASE_URL}/universe")
    assert r1.status == 200
    
    # Request /api/v1/universe with session cookie
    r2 = opener.open(f"{BASE_URL}/api/v1/universe")
    assert r2.status == 200
    data = json.loads(r2.read().decode("utf-8"))
    
    snapshot_id = data.get("graph_snapshot_id")
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    
    print(f"  [PASS] /api/v1/universe -> HTTP 200 | Snapshot ID: {snapshot_id}")
    print(f"  [PASS] Total Graph Nodes: {len(nodes)}")
    print(f"  [PASS] Total Graph Edges: {len(edges)}")
    
    assert len(nodes) > 100, f"Node count too low: {len(nodes)}"
    assert len(edges) > 100, f"Edge count too low: {len(edges)}"
    
    node_kinds = sorted(list(set(n["kind"] for n in nodes)))
    edge_kinds = sorted(list(set(e["kind"] for e in edges)))
    print(f"  [PASS] Node Kinds ({len(node_kinds)}): {node_kinds}")
    print(f"  [PASS] Edge Kinds ({len(edge_kinds)}): {edge_kinds}")
    
    # Verify presence of AST code kinds and Catalog memory kinds
    code_kinds = [k for k in node_kinds if k in ['class', 'file', 'function', 'method', 'module', 'repository', 'test']]
    catalog_kinds = [k for k in node_kinds if k in ['workspace', 'generation', 'instruction', 'pack', 'skill', 'agent', 'adapter']]
    assert len(code_kinds) > 0, "No AST code kinds found in graph nodes"
    assert len(catalog_kinds) > 0, "No catalog/memory kinds found in graph nodes"
    print(f"  [PASS] AST Code Node Kinds Present: {code_kinds}")
    print(f"  [PASS] Catalog / Memory Node Kinds Present: {catalog_kinds}")

    # Verify coordinates calculation
    coords_valid = all(isinstance(n.get("x"), (int, float)) and isinstance(n.get("y"), (int, float)) for n in nodes)
    assert coords_valid, "Invalid node coordinates detected"
    print(f"  [PASS] Polar ring layout coordinates (x, y) verified for all {len(nodes)} nodes.")

    # 4. System Endpoint Verification (/api/v1/system)
    print("\n[CHECK 4] Verifying System Health Endpoint (/api/v1/system)...")
    r_sys = opener.open(f"{BASE_URL}/api/v1/system")
    assert r_sys.status == 200
    sys_data = json.loads(r_sys.read().decode("utf-8"))
    
    counts = sys_data.get("counts", {})
    safety = sys_data.get("safety", {})
    print(f"  [PASS] System Fingerprint Code Nodes Count: {counts.get('code_nodes')}")
    print(f"  [PASS] System Fingerprint Code Edges Count: {counts.get('code_edges')}")
    print(f"  [PASS] Binding Policy: {safety.get('binding')}")
    assert counts.get('code_nodes', 0) > 1000
    assert safety.get('binding') == "loopback_only"

    # 5. Full Graph SQLite Query Endpoint (/api/v1/full-graph)
    print("\n[CHECK 5] Verifying Full Graph Endpoint (/api/v1/full-graph)...")
    r_fg = opener.open(f"{BASE_URL}/api/v1/full-graph")
    assert r_fg.status == 200
    fg_data = json.loads(r_fg.read().decode("utf-8"))
    fg_nodes = fg_data.get("nodes", [])
    fg_links = fg_data.get("links", [])
    print(f"  [PASS] /api/v1/full-graph -> HTTP 200 | DB Nodes: {len(fg_nodes)} | DB Links: {len(fg_links)}")
    assert len(fg_nodes) > 0, "No nodes returned from dnts.db"

    # 6. Stream Universe Endpoint (/api/v1/stream/universe)
    print("\n[CHECK 6] Verifying SSE Event Stream Endpoint (/api/v1/stream/universe)...")
    req_stream = urllib.request.Request(f"{BASE_URL}/api/v1/stream/universe")
    with urllib.request.urlopen(req_stream) as resp_stream:
        assert resp_stream.status == 200
        content_type = resp_stream.headers.get("content-type", "")
        assert "text/event-stream" in content_type.lower(), f"Unexpected Content-Type: {content_type}"
        line = resp_stream.readline().decode("utf-8")
        print(f"  [PASS] SSE Content-Type: {content_type}")
        print(f"  [PASS] First SSE Frame: {line.strip()}")

    print("\n" + "=" * 80)
    print("ALL EMPIRICAL FORENSIC INTEGRITY CHECKS PASSED SUCCESSFULLY!")
    print("=" * 80)

if __name__ == "__main__":
    run_forensic_audit()
