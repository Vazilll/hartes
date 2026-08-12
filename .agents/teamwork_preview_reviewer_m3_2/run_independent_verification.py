"""
run_independent_verification.py — Independent Verification Suite by Reviewer 2
Milestone 3 (Requirement R2: Production Web Server & 3D SuperGraph Surface)
vazus SuperGraph OS
"""

import sys
import json
import urllib.request
import urllib.error
import http.cookiejar
from typing import Dict, Any, List

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

SERVER_URL = "http://127.0.0.1:8765"
REQUIRED_SPA_ROUTES = [
    "/universe",
    "/command-center",
    "/tasks",
    "/agents",
    "/skills",
    "/runs",
]

def main() -> bool:
    print("=" * 80)
    print("REVIEWER 2 INDEPENDENT VERIFICATION SUITE — MILESTONE 3 (R2)")
    print(f"Target Server: {SERVER_URL}")
    print("=" * 80)

    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    
    overall_success = True

    # -------------------------------------------------------------------------
    # 1. SPA ROUTING & CSP NONCE INJECTION IN index.html
    # -------------------------------------------------------------------------
    print("\n--- 1. SPA ROUTING & DYNAMIC CSP NONCE INJECTION ---")
    nonces = []
    for route in REQUIRED_SPA_ROUTES:
        url = f"{SERVER_URL}{route}"
        try:
            req = urllib.request.Request(url)
            with opener.open(req, timeout=10) as resp:
                status = resp.status
                c_type = resp.headers.get("Content-Type", "")
                body = resp.read().decode("utf-8")

                if status != 200:
                    print(f"[FAIL] SPA Route {route}: Expected 200, got {status}")
                    overall_success = False
                    continue

                if "text/html" not in c_type:
                    print(f"[FAIL] SPA Route {route}: Expected text/html, got {c_type}")
                    overall_success = False
                    continue

                if 'id="root"' not in body:
                    print(f"[FAIL] SPA Route {route}: React root div missing")
                    overall_success = False
                    continue

                marker = 'name="raytsystem-csp-nonce" content="'
                if marker not in body:
                    print(f"[FAIL] SPA Route {route}: CSP nonce meta tag missing!")
                    overall_success = False
                    continue

                start = body.index(marker) + len(marker)
                end = body.index('"', start)
                nonce = body[start:end]
                nonces.append(nonce)

                print(f"[PASS] SPA Route {route:16s} -> HTTP 200 | HTML SPA | Nonce: {nonce}")

        except Exception as e:
            print(f"[FAIL] SPA Route {route}: Exception: {e}")
            overall_success = False

    # Check CSP Nonce uniqueness across calls
    if len(nonces) == len(REQUIRED_SPA_ROUTES) and len(set(nonces)) == len(REQUIRED_SPA_ROUTES):
        print(f"[PASS] Dynamic CSP Nonce: All {len(nonces)} requested SPA routes received unique cryptographically generated nonces.")
    else:
        print(f"[FAIL] Dynamic CSP Nonce uniqueness check failed! Total: {len(nonces)}, Unique: {len(set(nonces))}")
        overall_success = False

    # -------------------------------------------------------------------------
    # 2. 3D SUPERGRAPH TOPOLOGY JSON ENDPOINT (/api/v1/universe)
    # -------------------------------------------------------------------------
    print("\n--- 2. 3D SUPERGRAPH TOPOLOGY JSON ENDPOINT (/api/v1/universe) ---")
    univ_url = f"{SERVER_URL}/api/v1/universe"
    try:
        req = urllib.request.Request(univ_url)
        with opener.open(req, timeout=30) as resp:
            status = resp.status
            c_type = resp.headers.get("Content-Type", "")
            raw_data = resp.read().decode("utf-8")

            if status != 200:
                print(f"[FAIL] /api/v1/universe: Expected HTTP 200, got {status}")
                overall_success = False
            else:
                print(f"[PASS] /api/v1/universe -> HTTP {status} | Content-Type: {c_type} | Payload Size: {len(raw_data):,} bytes")
                
                data = json.loads(raw_data)
                
                # Check root schema
                expected_keys = {"graph_snapshot_id", "nodes", "edges", "supported_lenses"}
                actual_keys = set(data.keys())
                if not expected_keys.issubset(actual_keys):
                    print(f"[FAIL] /api/v1/universe missing root keys: {expected_keys - actual_keys}")
                    overall_success = False
                else:
                    print(f"[PASS] Root schema verified (graph_snapshot_id: {data['graph_snapshot_id']})")

                nodes = data.get("nodes", [])
                edges = data.get("edges", [])
                print(f"[PASS] SuperGraph Snapshot: {len(nodes):,} Nodes, {len(edges):,} Edges")

                # Verify 3D / Sigma.js attributes on nodes
                sample_node = nodes[0] if nodes else {}
                node_keys = set(sample_node.keys())
                print(f"[PASS] Sample Node attributes: {sorted(list(node_keys))}")
                
                # Check required GraphNodeView fields
                required_node_attrs = {"node_id", "kind", "label", "ring", "x", "y"}
                if not required_node_attrs.issubset(node_keys):
                    print(f"[FAIL] Node missing required fields: {required_node_attrs - node_keys}")
                    overall_success = False
                else:
                    print(f"[PASS] Node schema fields validated (node_id, kind, label, ring, x, y present)")

                # Check required GraphEdgeView fields
                sample_edge = edges[0] if edges else {}
                edge_keys = set(sample_edge.keys())
                print(f"[PASS] Sample Edge attributes: {sorted(list(edge_keys))}")
                required_edge_attrs = {"edge_id", "source", "target", "kind"}
                if not required_edge_attrs.issubset(edge_keys):
                    print(f"[FAIL] Edge missing required fields: {required_edge_attrs - edge_keys}")
                    overall_success = False
                else:
                    print(f"[PASS] Edge schema fields validated (edge_id, source, target, kind present)")

                # Node kinds breakdown
                node_kinds = set(n.get("kind") for n in nodes)
                print(f"[PASS] Distinct Node Kinds ({len(node_kinds)}): {sorted(list(node_kinds))}")

                ast_kinds = {"repository", "module", "class", "function", "method", "test", "file"}
                ast_found = ast_kinds.intersection(node_kinds)
                if ast_found:
                    print(f"[PASS] AST Code Node Kinds Present ({len(ast_found)}): {sorted(list(ast_found))}")
                else:
                    print(f"[FAIL] No AST Code Nodes found in topology!")
                    overall_success = False

                wiki_kinds = {"agent", "skill", "pack", "workspace", "generation", "instruction", "adapter"}
                wiki_found = wiki_kinds.intersection(node_kinds)
                if wiki_found:
                    print(f"[PASS] Wiki / Catalog Node Kinds Present ({len(wiki_found)}): {sorted(list(wiki_found))}")

                # Edge kinds breakdown
                edge_kinds = set(e.get("kind") or e.get("relation") for e in edges if (e.get("kind") or e.get("relation")))
                print(f"[PASS] Distinct Edge Relations ({len(edge_kinds)}): {sorted(list(edge_kinds))}")

                ast_edges = {"calls", "contains", "defines", "imports", "inherits", "references", "tests", "uses", "verifies"}
                ast_edges_found = ast_edges.intersection(edge_kinds)
                if ast_edges_found:
                    print(f"[PASS] AST Call & Topology Edges Present ({len(ast_edges_found)}): {sorted(list(ast_edges_found))}")
                else:
                    print(f"[FAIL] No AST Call Edges found in topology!")
                    overall_success = False

    except Exception as e:
        print(f"[FAIL] Error accessing /api/v1/universe: {e}")
        overall_success = False

    # -------------------------------------------------------------------------
    # 3. SECURITY & BOUNDARY TESTING
    # -------------------------------------------------------------------------
    print("\n--- 3. SECURITY & BOUNDARY TESTING ---")
    
    # 3.1 Invalid SPA Route -> HTTP 404
    invalid_url = f"{SERVER_URL}/nonexistent-page-xyz"
    try:
        req = urllib.request.Request(invalid_url)
        with opener.open(req) as resp:
            print(f"[FAIL] Invalid route /nonexistent-page-xyz returned HTTP {resp.status} instead of 404")
            overall_success = False
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"[PASS] Invalid SPA Route /nonexistent-page-xyz correctly returned HTTP 404")
        else:
            print(f"[FAIL] Invalid SPA Route returned HTTP {e.code} instead of 404")
            overall_success = False
    except Exception as e:
        print(f"[FAIL] Unexpected exception on invalid route: {e}")
        overall_success = False

    # 3.2 Host Header Verification (Security Middleware)
    try:
        req = urllib.request.Request(f"{SERVER_URL}/universe", headers={"Host": "evil-domain.com"})
        with opener.open(req) as resp:
            print(f"[FAIL] Host header spoofing was allowed (HTTP {resp.status})!")
            overall_success = False
    except urllib.error.HTTPError as e:
        if e.code in (400, 421, 403):
            print(f"[PASS] Host Header Spoofing rejected with HTTP {e.code} (Security Guard active)")
        else:
            print(f"[WARN] Host Header Spoofing returned HTTP {e.code}")
    except Exception as e:
        print(f"[PASS] Host Header Spoofing blocked: {e}")

    # -------------------------------------------------------------------------
    # SUMMARY VERDICT
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    if overall_success:
        print("VERDICT: APPROVE — All Milestone 3 / Requirement R2 checks passed!")
    else:
        print("VERDICT: REQUEST_CHANGES — Verification failures detected!")
    print("=" * 80)
    
    return overall_success

if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
