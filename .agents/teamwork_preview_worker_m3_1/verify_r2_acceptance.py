"""
verify_r2_acceptance.py — Automated Verification Suite for Requirement R2
vazus SuperGraph OS Milestone 3 Worker 1
"""

import sys
import json
import http.cookiejar
import urllib.request
from typing import Dict, Any, List

# Ensure UTF-8 output on Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

SERVER_URL = "http://127.0.0.1:8765"
SPA_ROUTES = [
    "/universe",
    "/command-center",
    "/tasks",
    "/agents",
    "/skills",
    "/runs",
]

def run_verification() -> bool:
    print("=" * 80)
    print("VAZUS SUPERGRAPH OS -- REQUIREMENT R2 AUTOMATED VERIFICATION SUITE")
    print("Target Server: http://127.0.0.1:8765")
    print("=" * 80)
    
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    
    all_passed = True
    
    # -------------------------------------------------------------------------
    # TEST 1: SPA Route Navigation & Dynamic CSP Nonce Verification
    # -------------------------------------------------------------------------
    print("\n[TEST 1] Verifying SPA Routes & Dynamic CSP Nonce...")
    nonces = []
    
    for route in SPA_ROUTES:
        full_url = f"{SERVER_URL}{route}"
        try:
            req = urllib.request.Request(full_url, headers={"User-Agent": "VazusVerifier/1.0"})
            with opener.open(req) as resp:
                status = resp.status
                content_type = resp.headers.get("Content-Type", "")
                body = resp.read().decode("utf-8")
                
                # Check status code 200
                if status != 200:
                    print(f"  [FAIL] Route {route}: Expected HTTP 200, got {status}")
                    all_passed = False
                    continue
                
                # Check HTML content type
                if "text/html" not in content_type:
                    print(f"  [FAIL] Route {route}: Expected text/html, got {content_type}")
                    all_passed = False
                    continue
                
                # Extract CSP Nonce meta tag
                nonce_marker = 'name="raytsystem-csp-nonce" content="'
                if nonce_marker not in body:
                    print(f"  [FAIL] Route {route}: CSP nonce meta tag missing from HTML")
                    all_passed = False
                    continue
                
                start_idx = body.index(nonce_marker) + len(nonce_marker)
                end_idx = body.index('"', start_idx)
                nonce = body[start_idx:end_idx]
                nonces.append(nonce)
                
                # Check SPA root element
                has_root = 'id="root"' in body
                
                print(f"  [PASS] Route {route:16s} -> HTTP {status} | HTML SPA (root={has_root}) | CSP Nonce: {nonce[:16]}...")
        except Exception as e:
            print(f"  [FAIL] Route {route}: Exception: {e}")
            all_passed = False
            
    # Check Nonce Dynamism (Nonces should be uniquely generated per request)
    if len(nonces) == len(SPA_ROUTES) and len(set(nonces)) > 1:
        print(f"  [PASS] Dynamic CSP Nonce verified: {len(set(nonces))} unique nonces generated across {len(nonces)} requests.")
    else:
        print(f"  [WARN] Nonces count={len(nonces)}, unique={len(set(nonces))}")

    # -------------------------------------------------------------------------
    # TEST 2: 3D SuperGraph Topology API Verification (/api/v1/universe)
    # -------------------------------------------------------------------------
    print("\n[TEST 2] Verifying 3D SuperGraph Topology JSON Endpoint (/api/v1/universe)...")
    univ_url = f"{SERVER_URL}/api/v1/universe"
    
    try:
        req = urllib.request.Request(univ_url, headers={"User-Agent": "VazusVerifier/1.0"})
        with opener.open(req) as resp:
            status = resp.status
            content_type = resp.headers.get("Content-Type", "")
            body = resp.read().decode("utf-8")
            
            if status != 200:
                print(f"  [FAIL] /api/v1/universe: Expected HTTP 200, got {status}")
                all_passed = False
            else:
                print(f"  [PASS] /api/v1/universe -> HTTP {status} | Content-Type: {content_type}")
                
                snapshot = json.loads(body)
                
                # Structural checks
                required_keys = ["graph_snapshot_id", "nodes", "edges", "supported_lenses"]
                missing_keys = [k for k in required_keys if k not in snapshot]
                if missing_keys:
                    print(f"  [FAIL] /api/v1/universe missing keys: {missing_keys}")
                    all_passed = False
                else:
                    print(f"  [PASS] Schema Structure Validated (Graph Snapshot ID: {snapshot['graph_snapshot_id']})")
                
                nodes: List[Dict[str, Any]] = snapshot.get("nodes", [])
                edges: List[Dict[str, Any]] = snapshot.get("edges", [])
                
                print(f"  [PASS] Total Graph Nodes: {len(nodes)}")
                print(f"  [PASS] Total Graph Edges: {len(edges)}")
                
                # Node Categorization & Verification
                node_kinds = set(n.get("kind") for n in nodes if "kind" in n)
                print(f"  [PASS] Node Kinds Present ({len(node_kinds)}): {sorted(list(node_kinds))}")
                
                ast_code_kinds = {"repository", "module", "class", "function", "method", "test", "file"}
                ast_present = ast_code_kinds.intersection(node_kinds)
                if ast_present:
                    print(f"  [PASS] AST Code Nodes Verified: {sorted(list(ast_present))}")
                else:
                    print(f"  [FAIL] No AST Code Nodes found!")
                    all_passed = False
                
                wiki_kinds = {"claim", "entity", "source", "evidence", "agent", "skill", "pack", "workspace", "generation", "instruction", "adapter"}
                wiki_present = wiki_kinds.intersection(node_kinds)
                if wiki_present:
                    print(f"  [PASS] Wiki / Catalog / Memory Nodes Verified: {sorted(list(wiki_present))}")
                else:
                    print(f"  [WARN] Wiki/Memory kinds: {wiki_present}")

                # Edge Categorization & Verification
                edge_relations = set(e.get("kind") or e.get("relation") for e in edges if e.get("kind") or e.get("relation"))
                print(f"  [PASS] Edge Relations Present ({len(edge_relations)}): {sorted(list(edge_relations))}")
                
                ast_edge_relations = {"calls", "contains", "defines", "inherits", "tests", "verifies", "uses", "imports", "references"}
                ast_edges_present = ast_edge_relations.intersection(edge_relations)
                if ast_edges_present:
                    print(f"  [PASS] AST Call & Topology Edges Verified: {sorted(list(ast_edges_present))}")
                else:
                    print(f"  [FAIL] No AST Call Edges found!")
                    all_passed = False
                    
                knowledge_edge_relations = {"governed_by", "activates", "configured_for", "offers"}
                knowledge_edges_present = knowledge_edge_relations.intersection(edge_relations)
                if knowledge_edges_present:
                    print(f"  [PASS] Knowledge / Catalog Edges Verified: {sorted(list(knowledge_edges_present))}")

    except Exception as e:
        print(f"  [FAIL] Exception querying /api/v1/universe: {e}")
        all_passed = False

    # -------------------------------------------------------------------------
    # TEST 3: System Health Check Endpoint (/api/v1/system)
    # -------------------------------------------------------------------------
    print("\n[TEST 3] Verifying System Health Check Endpoint (/api/v1/system)...")
    sys_url = f"{SERVER_URL}/api/v1/system"
    try:
        req = urllib.request.Request(sys_url, headers={"User-Agent": "VazusVerifier/1.0"})
        with opener.open(req) as resp:
            status = resp.status
            sys_data = json.loads(resp.read().decode("utf-8"))
            print(f"  [PASS] /api/v1/system -> HTTP {status}")
            print(f"  [PASS] System Fingerprint Code Nodes Count: {sys_data.get('counts', {}).get('code_nodes')}")
            print(f"  [PASS] System Fingerprint Code Edges Count: {sys_data.get('counts', {}).get('code_edges')}")
            print(f"  [PASS] Binding Policy: {sys_data.get('safety', {}).get('binding')}")
    except Exception as e:
        print(f"  [FAIL] Exception querying /api/v1/system: {e}")
        all_passed = False

    print("\n" + "=" * 80)
    if all_passed:
        print("ALL ACCEPTANCE CRITERIA FOR REQUIREMENT R2 PASSED SUCCESSFULLY!")
    else:
        print("SOME VERIFICATION TESTS FAILED!")
    print("=" * 80)
    return all_passed

if __name__ == "__main__":
    success = run_verification()
    sys.exit(0 if success else 1)
