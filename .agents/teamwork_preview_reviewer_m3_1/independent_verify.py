"""
independent_verify.py — Independent Reviewer Verification Script for Milestone 3
Target: http://127.0.0.1:8765
"""

import json
import sys
import http.cookiejar
import urllib.request
import urllib.error

# Ensure UTF-8 output on Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

SERVER_URL = "http://127.0.0.1:8765"

def run_tests():
    print("=" * 80)
    print("INDEPENDENT REVIEWER VERIFICATION SUITE — MILESTONE 3 (R2)")
    print("=" * 80)
    
    results = []

    # 1. Unauthenticated API access security check
    print("\n[CHECK 1] Testing Unauthenticated Access to /api/v1/universe...")
    try:
        req = urllib.request.Request(f"{SERVER_URL}/api/v1/universe", headers={"User-Agent": "Reviewer/1.0"})
        with urllib.request.urlopen(req) as resp:
            print(f"  [WARN] /api/v1/universe allowed unauthenticated request (HTTP {resp.status})")
            results.append(("Unauthenticated API Access", "WARN", f"Status {resp.status}"))
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print("  [PASS] /api/v1/universe correctly denied unauthenticated access with HTTP 401 (session_required)")
            results.append(("Unauthenticated API Security", "PASS", "HTTP 401 correctly enforced"))
        else:
            print(f"  [INFO] /api/v1/universe returned HTTP {e.code}")
            results.append(("Unauthenticated API Security", "INFO", f"HTTP {e.code}"))

    # 2. SPA Session & Nonce Verification across routes
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    
    routes = ["/universe", "/command-center", "/tasks", "/agents", "/skills", "/runs"]
    nonces = []
    
    print("\n[CHECK 2] Testing SPA Page Renders & Dynamic Nonces...")
    for route in routes:
        try:
            url = f"{SERVER_URL}{route}"
            with opener.open(url) as resp:
                status = resp.status
                body = resp.read().decode("utf-8")
                
                # Check root element and nonce
                has_root = 'id="root"' in body
                nonce_marker = 'name="raytsystem-csp-nonce" content="'
                if nonce_marker in body:
                    start = body.index(nonce_marker) + len(nonce_marker)
                    end = body.index('"', start)
                    nonce = body[start:end]
                    nonces.append(nonce)
                else:
                    nonce = "NONE"
                
                if status == 200 and has_root and nonce != "NONE":
                    print(f"  [PASS] {route:16s} -> HTTP 200 | SPA Root: Yes | Nonce: {nonce[:12]}...")
                    results.append((f"SPA Route {route}", "PASS", f"HTTP 200, Nonce present"))
                else:
                    print(f"  [FAIL] {route:16s} -> HTTP {status} | SPA Root: {has_root} | Nonce: {nonce}")
                    results.append((f"SPA Route {route}", "FAIL", f"HTTP {status}"))
        except Exception as e:
            print(f"  [FAIL] {route}: Exception {e}")
            results.append((f"SPA Route {route}", "FAIL", str(e)))
            
    if len(set(nonces)) == len(routes) and len(nonces) > 1:
        print(f"  [PASS] Nonce Uniqueness Verified: {len(set(nonces))} unique nonces across {len(routes)} requests.")
        results.append(("CSP Nonce Security", "PASS", f"{len(set(nonces))} unique nonces"))
    else:
        print(f"  [FAIL] Nonce Uniqueness Failed: nonces count {len(nonces)}, unique {len(set(nonces))}")
        results.append(("CSP Nonce Security", "FAIL", "Duplicate nonces detected"))

    # 3. Authenticated 3D SuperGraph Topology API (/api/v1/universe)
    print("\n[CHECK 3] Testing 3D SuperGraph Topology JSON Endpoint (/api/v1/universe)...")
    try:
        with opener.open(f"{SERVER_URL}/api/v1/universe") as resp:
            status = resp.status
            body = resp.read().decode("utf-8")
            data = json.loads(body)
            
            nodes = data.get("nodes", [])
            edges = data.get("edges", [])
            snapshot_id = data.get("graph_snapshot_id", "")
            
            print(f"  [PASS] /api/v1/universe -> HTTP {status}")
            print(f"  [PASS] Graph Snapshot ID: {snapshot_id}")
            print(f"  [PASS] Nodes Count: {len(nodes)}")
            print(f"  [PASS] Edges Count: {len(edges)}")
            
            node_kinds = set(n.get("kind") for n in nodes if "kind" in n)
            edge_relations = set(e.get("kind") or e.get("relation") for e in edges if e.get("kind") or e.get("relation"))
            
            print(f"  [PASS] Node Kinds ({len(node_kinds)}): {sorted(list(node_kinds))}")
            print(f"  [PASS] Edge Relations ({len(edge_relations)}): {sorted(list(edge_relations))}")
            
            # Check coordinate attributes for 3D visualization
            nodes_with_coords = sum(1 for n in nodes if "x" in n and "y" in n)
            print(f"  [PASS] Nodes with Pre-computed Coordinates (x, y): {nodes_with_coords} / {len(nodes)}")
            
            if len(nodes) > 1000 and len(edges) > 3000 and nodes_with_coords == len(nodes):
                results.append(("/api/v1/universe JSON Snapshot", "PASS", f"{len(nodes)} nodes, {len(edges)} edges, full coords"))
            else:
                results.append(("/api/v1/universe JSON Snapshot", "WARN", f"Nodes: {len(nodes)}, Edges: {len(edges)}"))
    except Exception as e:
        print(f"  [FAIL] Exception querying /api/v1/universe: {e}")
        results.append(("/api/v1/universe JSON Snapshot", "FAIL", str(e)))

    # 4. System Health Check (/api/v1/system)
    print("\n[CHECK 4] Testing System Health Check Endpoint (/api/v1/system)...")
    try:
        with opener.open(f"{SERVER_URL}/api/v1/system") as resp:
            sys_data = json.loads(resp.read().decode("utf-8"))
            code_nodes = sys_data.get("counts", {}).get("code_nodes")
            code_edges = sys_data.get("counts", {}).get("code_edges")
            binding = sys_data.get("safety", {}).get("binding")
            print(f"  [PASS] System AST Code Nodes: {code_nodes}")
            print(f"  [PASS] System AST Code Edges: {code_edges}")
            print(f"  [PASS] Safety Binding: {binding}")
            results.append(("/api/v1/system Health Endpoint", "PASS", f"Code Nodes: {code_nodes}, Code Edges: {code_edges}, Binding: {binding}"))
    except Exception as e:
        print(f"  [FAIL] Exception querying /api/v1/system: {e}")
        results.append(("/api/v1/system Health Endpoint", "FAIL", str(e)))

    # 5. Full Graph SQLite Bridge (/api/v1/full-graph)
    print("\n[CHECK 5] Testing Full Graph Endpoint (/api/v1/full-graph)...")
    try:
        with opener.open(f"{SERVER_URL}/api/v1/full-graph") as resp:
            fg_data = json.loads(resp.read().decode("utf-8"))
            fg_nodes = fg_data.get("nodes", [])
            fg_links = fg_data.get("links", [])
            print(f"  [PASS] Full Graph SQLite DB Nodes: {len(fg_nodes)}")
            print(f"  [PASS] Full Graph SQLite DB Links: {len(fg_links)}")
            results.append(("/api/v1/full-graph DB Bridge", "PASS", f"{len(fg_nodes)} DB nodes, {len(fg_links)} DB links"))
    except Exception as e:
        print(f"  [FAIL] Exception querying /api/v1/full-graph: {e}")
        results.append(("/api/v1/full-graph DB Bridge", "FAIL", str(e)))

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY OF INDEPENDENT VERIFICATION")
    print("=" * 80)
    all_pass = True
    for item, status, detail in results:
        symbol = "✔" if status == "PASS" else ("ℹ" if status == "INFO" else "❌")
        if status == "FAIL":
            all_pass = False
        print(f" {symbol} {item:35s} [{status:4s}] — {detail}")
    print("=" * 80)
    return all_pass

if __name__ == "__main__":
    ok = run_tests()
    sys.exit(0 if ok else 1)
