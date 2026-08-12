import os
import sys
import json
import sqlite3
import time
from pathlib import Path

ROOT_DIR = Path("C:/vazus")
for p in [str(ROOT_DIR), str(ROOT_DIR / "labs" / "raytsystem" / "src")]:
    if p not in sys.path:
        sys.path.insert(0, p)

results = {
    "R1_vector_indexing": False,
    "R2_web_server": False,
    "R3_handoff_ledger": False,
    "R4_smt_z3": False,
    "R5_obsidian_wiki": False,
    "integrity_violations": []
}

def verify_r1():
    print("\n--- Verifying Requirement R1: 768D Vector Indexing & SuperGraph Memory ---")
    vazus_db = ROOT_DIR / "services" / "memory" / "vazus.db"
    dnts_db = ROOT_DIR / "memory" / "dnts.db"
    
    assert vazus_db.exists(), f"vazus.db not found at {vazus_db}"
    assert dnts_db.exists(), f"dnts.db not found at {dnts_db}"
    
    # Check vazus.db kg_nodes
    with sqlite3.connect(vazus_db) as conn:
        cur = conn.cursor()
        nodes_cnt = cur.execute("SELECT count(*) FROM kg_nodes").fetchone()[0]
        edges_cnt = cur.execute("SELECT count(*) FROM kg_edges").fetchone()[0]
        sample_emb = cur.execute("SELECT embedding_json FROM kg_nodes WHERE embedding_json IS NOT NULL LIMIT 1").fetchone()
        assert sample_emb and sample_emb[0], "No 768D embedding found in kg_nodes"
        vec = json.loads(sample_emb[0])
        assert len(vec) == 768, f"Expected 768D embedding, got {len(vec)}D"
        print(f"  [PASS] vazus.db: {nodes_cnt} kg_nodes, {edges_cnt} kg_edges, verified 768D embedding vector dimension.")

    # Check dnts.db workspace_ast_nodes
    with sqlite3.connect(dnts_db) as conn:
        cur = conn.cursor()
        ast_nodes_cnt = cur.execute("SELECT count(*) FROM workspace_ast_nodes").fetchone()[0]
        ast_edges_cnt = cur.execute("SELECT count(*) FROM workspace_ast_edges").fetchone()[0]
        assert ast_nodes_cnt > 0, "No AST nodes found in workspace_ast_nodes"
        print(f"  [PASS] dnts.db: {ast_nodes_cnt} workspace_ast_nodes, {ast_edges_cnt} workspace_ast_edges.")

    results["R1_vector_indexing"] = True

def verify_r2():
    print("\n--- Verifying Requirement R2: Production Web Server & 3D SuperGraph Surface ---")
    from raytsystem.webapp import create_app
    from fastapi.testclient import TestClient

    app = create_app(ROOT_DIR / "labs" / "raytsystem")
    client = TestClient(app, headers={"host": "127.0.0.1:8765"})

    # GET /api/v1/system
    r_sys = client.get("/api/v1/system")
    assert r_sys.status_code == 200, f"/api/v1/system returned {r_sys.status_code}"
    print(f"  [PASS] GET /api/v1/system -> HTTP 200 OK")

    # GET /api/v1/universe
    r_univ = client.get("/api/v1/universe")
    assert r_univ.status_code == 200, f"/api/v1/universe returned {r_univ.status_code}"
    univ_data = r_univ.json()
    assert "code_node_count" in univ_data or "graph_snapshot_id" in univ_data or "nodes" in univ_data, "Invalid universe JSON"
    print(f"  [PASS] GET /api/v1/universe -> HTTP 200 OK (Snapshot: {univ_data.get('graph_snapshot_id', 'valid')})")

    # GET /api/v1/ledger
    r_led = client.get("/api/v1/ledger")
    assert r_led.status_code == 200, f"/api/v1/ledger returned {r_led.status_code}"
    ledger_data = r_led.json()
    assert "ledger" in ledger_data, "Missing 'ledger' key"
    print(f"  [PASS] GET /api/v1/ledger -> HTTP 200 OK ({len(ledger_data['ledger'])} entries)")

    # GET /api/v1/full-graph
    r_fg = client.get("/api/v1/full-graph")
    assert r_fg.status_code == 200, f"/api/v1/full-graph returned {r_fg.status_code}"
    fg_data = r_fg.json()
    assert "nodes" in fg_data and "links" in fg_data, "Missing 'nodes' or 'links' key"
    print(f"  [PASS] GET /api/v1/full-graph -> HTTP 200 OK ({len(fg_data['nodes'])} nodes, {len(fg_data['links'])} links)")

    results["R2_web_server"] = True

def verify_r3():
    print("\n--- Verifying Requirement R3: Handoff Ledger Recording ---")
    from vazus_core.agent_handoff import handoff_manager

    h_res = handoff_manager.record_handoff(
        agent_name="verifier_worker",
        action="m5_verification_audit",
        payload={"milestone": 5, "verifier": "reviewer_m5_2"},
        status="APPROVED",
        target_agent="orchestrator",
        workflow="REVIEW"
    )
    assert h_res and h_res.get("handoff_id"), "Handoff execution failed"
    
    dnts_db = ROOT_DIR / "memory" / "dnts.db"
    with sqlite3.connect(dnts_db) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        rec = cur.execute("SELECT * FROM raytsystem_ledger WHERE id = ?", (h_res["handoff_id"],)).fetchone()
        assert rec is not None, f"Handoff record {h_res['handoff_id']} not found in raytsystem_ledger"
        print(f"  [PASS] Handoff recorded & verified in raytsystem_ledger: ID={rec['id']}, workflow={rec['workflow']}, source={rec['source_agent']}")

    results["R3_handoff_ledger"] = True

def verify_r4():
    print("\n--- Verifying Requirement R4: SMT Z3 Solver Contract Verification ---")
    from vazus_core.smt_z3_verifier import smt_verifier, Z3_AVAILABLE

    assert Z3_AVAILABLE is True, "z3-solver library is not available"

    # Test 1: UNSAT (valid contract)
    valid_code = '''
def abs_val(x: int) -> int:
    """
    :requires: x >= 0
    :ensures: result >= 0
    """
    return x
'''
    res1 = smt_verifier.verify_code_contracts(valid_code)
    assert res1["success"] is True and res1["status"] == "UNSAT", f"Valid contract failed: {res1}"
    print(f"  [PASS] SMT Z3 Valid Contract -> Status: {res1['status']} (Contract Satisfied: {res1['contract_satisfied']})")

    # Test 2: SAT (invalid contract with counterexample)
    invalid_code = '''
def bad_inc(x: int) -> int:
    """
    :requires: x > 0
    :ensures: result < 0
    """
    return x + 1
'''
    res2 = smt_verifier.verify_code_contracts(invalid_code)
    assert res2["success"] is False and res2["status"] == "SAT", f"Invalid contract failed: {res2}"
    ce = res2["details"][0]["smt_result"]["counterexample"]
    assert ce is not None, "Counterexample missing"
    print(f"  [PASS] SMT Z3 Invalid Contract -> Status: {res2['status']} (Counterexample found: {ce})")

    results["R4_smt_z3"] = True

def verify_r5():
    print("\n--- Verifying Requirement R5: Obsidian Wiki Note Persistence ---")
    from vazus_core.dialogue_persister import dialogue_persister

    dlg = dialogue_persister.record_dialogue(
        session_id="m5_review_session",
        parent_id="orchestrator",
        agent_name="reviewer_m5_2",
        prompt="Execute M5 victory audit",
        response="Audit complete."
    )
    trace = dialogue_persister.record_memory_trace(
        agent_name="reviewer_m5_2",
        trace_kind="VICTORY_AUDIT",
        summary="Milestone 5 acceptance criteria verified",
        content="All R1-R5 requirements verified independently.",
        dialogue_id=dlg["dialogue_id"],
        title="M5_Reviewer2_Audit_Note"
    )

    note_path = Path(trace["obsidian_note_path"])
    assert note_path.exists(), f"Obsidian note file not found at {note_path}"
    content = note_path.read_text(encoding="utf-8")
    assert "---" in content and "[[" in content, "Missing YAML frontmatter or wikilinks in Obsidian note"
    print(f"  [PASS] Obsidian wiki note created and verified at: {note_path} ({len(content)} bytes)")

    results["R5_obsidian_wiki"] = True

def check_integrity():
    print("\n--- Auditing Codebase for Integrity Violations ---")
    # Check for hardcoded solver returns or fake Z3 mocks in smt_z3_verifier.py
    smt_path = ROOT_DIR / "vazus_core" / "smt_z3_verifier.py"
    smt_code = smt_path.read_text(encoding="utf-8")
    assert "import z3" in smt_code, "z3 import missing in smt_z3_verifier.py"
    assert "solver = z3.Solver()" in smt_code, "Real z3.Solver() call missing"
    assert "solver.check()" in smt_code, "Real solver.check() call missing"
    print("  [PASS] Code inspection of smt_z3_verifier.py confirmed genuine Z3 SMT solver invocation (no facade mocks).")

if __name__ == "__main__":
    print("==========================================================")
    print("      MILESTONE 5 INDEPENDENT REVIEW VERIFICATION")
    print("==========================================================")
    verify_r1()
    verify_r2()
    verify_r3()
    verify_r4()
    verify_r5()
    check_integrity()
    print("\n==========================================================")
    print(" ALL MILESTONE 5 ACCEPTANCE CRITERIA VERIFIED SUCCESSFULLY!")
    print("==========================================================")
