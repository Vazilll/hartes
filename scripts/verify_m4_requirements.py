"""
verify_m4_requirements.py — Fast Automated Verification Suite for Milestone 4 (R3, R4, R5).

vazus SuperGraph OS Architecture Verification
"""

import json
import os
import sqlite3
import sys
import time
from pathlib import Path

ROOT_DIR = Path("C:/vazus")
DB_PATH = ROOT_DIR / "services" / "memory" / "vazus.db"
WIKI_DIR = ROOT_DIR / "services" / "memory" / "semantic" / "wiki"
TARGET_DBS = [
    ROOT_DIR / "services" / "memory" / "vazus.db",
    ROOT_DIR / "memory" / "vazus.db",
    ROOT_DIR / "vazus.db",
]


def init_database_schemas():
    """Initializes DB connections safely and auto-creates missing tables across target database paths."""
    for db_path in TARGET_DBS:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS raytsystem_ledger (
                    handoff_id TEXT PRIMARY KEY,
                    from_agent TEXT,
                    to_agent TEXT,
                    task_name TEXT,
                    status TEXT,
                    payload TEXT,
                    timestamp TEXT,
                    id TEXT,
                    workflow TEXT,
                    source_agent TEXT,
                    target_agent TEXT,
                    payload_summary TEXT,
                    vector_768d BLOB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS kg_nodes (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    domain TEXT,
                    node_type TEXT,
                    description TEXT,
                    tags TEXT,
                    properties TEXT,
                    embedding_json TEXT
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS kg_edges (
                    source_id TEXT,
                    target_id TEXT,
                    relation TEXT,
                    strength REAL,
                    properties TEXT,
                    PRIMARY KEY (source_id, target_id, relation)
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tutor_cards (
                    id TEXT PRIMARY KEY,
                    entity_id TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    question_type TEXT NOT NULL,
                    question_text TEXT NOT NULL,
                    target_answer TEXT NOT NULL,
                    repetition_n INTEGER DEFAULT 0,
                    ease_factor REAL DEFAULT 2.5,
                    interval_days REAL DEFAULT 0.0,
                    lapses INTEGER DEFAULT 0,
                    last_review_at TEXT,
                    next_review_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tutor_reviews (
                    id TEXT PRIMARY KEY,
                    card_id TEXT NOT NULL,
                    score_percent REAL NOT NULL,
                    q_rating INTEGER NOT NULL,
                    user_response TEXT NOT NULL,
                    feedback_rationale TEXT NOT NULL,
                    response_time_sec REAL DEFAULT 0,
                    reviewed_at TEXT NOT NULL,
                    FOREIGN KEY (card_id) REFERENCES tutor_cards(id) ON DELETE CASCADE
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS subagent_dialogues (
                    dialogue_id TEXT PRIMARY KEY,
                    session_id TEXT,
                    parent_id TEXT,
                    agent_name TEXT,
                    prompt TEXT,
                    response TEXT,
                    vector_768d BLOB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS subagent_memory_traces (
                    trace_id TEXT PRIMARY KEY,
                    dialogue_id TEXT,
                    agent_name TEXT,
                    trace_kind TEXT,
                    summary TEXT,
                    content TEXT,
                    obsidian_note_path TEXT,
                    vector_768d BLOB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.execute("DROP VIEW IF EXISTS kg_flashcards;")
            conn.execute("CREATE VIEW IF NOT EXISTS kg_flashcards AS SELECT * FROM tutor_cards;")
            conn.execute("DROP VIEW IF EXISTS kg_review_logs;")
            conn.execute("CREATE VIEW IF NOT EXISTS kg_review_logs AS SELECT * FROM tutor_reviews;")
            conn.commit()


for p in [str(ROOT_DIR), str(ROOT_DIR / "labs" / "raytsystem" / "src")]:
    if p not in sys.path:
        sys.path.insert(0, p)

from vazus_core.agent_handoff import handoff_manager
from vazus_core.dialogue_persister import dialogue_persister
from vazus_core.smt_z3_verifier import smt_verifier


def test_r3_subagent_handoff_ledger():
    print("\n--- Testing Requirement R3: Subagent Handoff Ledger Integration ---")
    
    # 1. Execute handoffs for research, rlm, verifier
    h1 = handoff_manager.execute_handoff("RESEARCH", "open_deep_researcher", "system", {"query": "SuperGraph test", "dry_run": True}, require_jury=False)
    h2 = handoff_manager.execute_handoff("SAVE", "rlm_code_engineer", "system", {"prompt": "Write test func", "dry_run": True}, require_jury=False)
    h3 = handoff_manager.execute_handoff("REVIEW", "verifier_worker", "system", {"smt_status": "UNSAT", "overall_success": True}, require_jury=False)

    print(f"  [PASS] Direct handoffs executed: {h1['handoff_id']}, {h2['handoff_id']}, {h3['handoff_id']}")

    # 2. Query SQLite vazus.db raytsystem_ledger
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("""
            CREATE TABLE IF NOT EXISTS raytsystem_ledger (
                id TEXT PRIMARY KEY,
                workflow TEXT,
                source_agent TEXT,
                target_agent TEXT,
                payload_summary TEXT,
                vector_768d BLOB,
                status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        rows = conn.execute("SELECT id, workflow, source_agent, target_agent, status, created_at FROM raytsystem_ledger ORDER BY created_at DESC LIMIT 10").fetchall()
        assert len(rows) > 0, "No records found in raytsystem_ledger table"
        print(f"  [PASS] Found {len(rows)} recent handoff records in raytsystem_ledger table:")
        for r in rows[:5]:
            print(f"    - [{r['created_at']}] ID: {r['id']} | Workflow: {r['workflow']} | Source: {r['source_agent']} | Status: {r['status']}")
    finally:
        conn.close()

    # 3. Test FastAPI /api/v1/ledger endpoint
    from raytsystem.webapp import create_app
    from fastapi.testclient import TestClient
    
    app = create_app(ROOT_DIR / "labs" / "raytsystem")
    client = TestClient(app, headers={"host": "127.0.0.1:8765"})
    
    response = client.get("/api/v1/ledger")
    assert response.status_code == 200, f"/api/v1/ledger returned status {response.status_code}"
    data = response.json()
    assert "ledger" in data, "Response JSON missing 'ledger' key"
    assert len(data["ledger"]) > 0, "Ledger endpoint returned empty list"
    print(f"  [PASS] GET /api/v1/ledger HTTP 200 OK. Returned {len(data['ledger'])} ledger entries.")


def test_r4_smt_z3_verification():
    print("\n--- Testing Requirement R4: SMT Z3 Code Contract Verification ---")
    
    # Check that z3 is imported and available
    from vazus_core.smt_z3_verifier import Z3_AVAILABLE
    assert Z3_AVAILABLE is True, "z3-solver must be installed and Z3_AVAILABLE must be True"

    # Test 1: Valid contract (UNSAT counterexample = SATISFIED contract)
    valid_code = """
def check_positive(n: int) -> int:
    \"\"\"
    :requires: n >= 0
    :ensures: result >= 0
    \"\"\"
    return n + 1
"""
    res_valid = smt_verifier.verify_code_contracts(valid_code, depth=10)
    assert res_valid["success"] is True, f"Expected valid contract verification to succeed, got: {res_valid}"
    assert res_valid["status"] == "UNSAT", f"Expected UNSAT status, got: {res_valid['status']}"
    assert res_valid["model_checking"]["solver"] == "Z3_SMT_Solver", f"Expected Z3_SMT_Solver, got: {res_valid['model_checking']['solver']}"
    print(f"  [PASS] Valid contract test: SMT Status = {res_valid['status']} (Satisfied: {res_valid['contract_satisfied']}, Solver: {res_valid['model_checking']['solver']})")

    # Test 2: Invalid contract (SAT counterexample found = FAILED contract)
    invalid_code = """
def check_invalid(n: int) -> int:
    \"\"\"
    :requires: n >= 0
    :ensures: result < 0
    \"\"\"
    return n + 1
"""
    res_invalid = smt_verifier.verify_code_contracts(invalid_code, depth=10)
    assert res_invalid["success"] is False, f"Expected invalid contract verification to fail, got: {res_invalid}"
    assert res_invalid["status"] == "SAT", f"Expected SAT status (counterexample), got: {res_invalid['status']}"
    assert res_invalid["details"][0]["smt_result"]["counterexample"] is not None, "Counterexample model should be returned"
    print(f"  [PASS] Invalid contract test: SMT Status = {res_invalid['status']} (Contract Satisfied: {res_invalid['contract_satisfied']}, Counterexample: {res_invalid['details'][0]['smt_result']['counterexample']})")

    # Test 3: Non-trivial mathematical contract (x > 10 => result > 20 for return x * 2)
    nontrivial_code = """
def double_value(x: int) -> int:
    \"\"\"
    :requires: x > 10
    :ensures: result > 20
    \"\"\"
    return x * 2
"""
    res_nontrivial = smt_verifier.verify_code_contracts(nontrivial_code, depth=10)
    assert res_nontrivial["success"] is True, f"Expected non-trivial contract verification to succeed, got: {res_nontrivial}"
    assert res_nontrivial["status"] == "UNSAT", f"Expected UNSAT status, got: {res_nontrivial['status']}"
    print(f"  [PASS] Non-trivial math contract test (x > 10 => result > 20): SMT Status = {res_nontrivial['status']} (Satisfied: {res_nontrivial['contract_satisfied']})")

    # Test 4: Flawed non-trivial contract (x > 10 => result > 25 for return x * 2, fails for x=11, result=22)
    flawed_code = """
def double_value_flawed(x: int) -> int:
    \"\"\"
    :requires: x > 10
    :ensures: result > 25
    \"\"\"
    return x * 2
"""
    res_flawed = smt_verifier.verify_code_contracts(flawed_code, depth=10)
    assert res_flawed["success"] is False, f"Expected flawed contract verification to fail, got: {res_flawed}"
    assert res_flawed["status"] == "SAT", f"Expected SAT status, got: {res_flawed['status']}"
    print(f"  [PASS] Flawed math contract test (x > 10 => result > 25): SMT Status = {res_flawed['status']} (Counterexample: {res_flawed['details'][0]['smt_result']['counterexample']})")

    # Test 5: Multi-parameter contract (a > 5 and b > 5 => result > 10 for return a + b)
    multiparam_code = """
def sum_positive(a: int, b: int) -> int:
    \"\"\"
    :requires: a > 5 and b > 5
    :ensures: result > 10
    \"\"\"
    return a + b
"""
    res_multi = smt_verifier.verify_code_contracts(multiparam_code, depth=10)
    assert res_multi["success"] is True, f"Expected multi-parameter contract verification to succeed, got: {res_multi}"
    assert res_multi["status"] == "UNSAT", f"Expected UNSAT status, got: {res_multi['status']}"
    print(f"  [PASS] Multi-parameter contract test (a > 5, b > 5 => result > 10): SMT Status = {res_multi['status']} (Satisfied: {res_multi['contract_satisfied']})")

    # Test 6: Invalid contract (result == 999 for return n + 1)
    invalid_999_code = """
def check_invalid_999(n: int) -> int:
    \"\"\"
    :requires: n >= 0
    :ensures: result == 999
    \"\"\"
    return n + 1
"""
    res_999 = smt_verifier.verify_code_contracts(invalid_999_code, depth=10)
    assert res_999["success"] is False, f"Expected result == 999 contract verification to fail, got: {res_999}"
    assert res_999["status"] == "SAT", f"Expected SAT status, got: {res_999['status']}"
    assert res_999["details"][0]["smt_result"]["counterexample"] is not None, "Counterexample model should be returned"
    print(f"  [PASS] Invalid result == 999 contract test: SMT Status = {res_999['status']} (Contract Satisfied: {res_999['contract_satisfied']}, Counterexample: {res_999['details'][0]['smt_result']['counterexample']})")



def test_r5_dialogue_and_memory_persistence():
    print("\n--- Testing Requirement R5: Dialogue & Memory Persistence ---")
    
    dlg_res = dialogue_persister.record_dialogue(
        session_id="verification_session",
        parent_id="orchestrator",
        agent_name="verifier_worker",
        prompt="Verify SMT Z3 contract for fibonacci",
        response="SMT Z3 verification UNSAT (contract satisfied)."
    )
    trace_res = dialogue_persister.record_memory_trace(
        agent_name="verifier_worker",
        trace_kind="CONTRACT_VERIFICATION",
        summary="SMT Z3 contract verified UNSAT",
        content="Precondition: n >= 0; Postcondition: result >= 0",
        dialogue_id=dlg_res["dialogue_id"],
        title="Verifier_Contract_Verification_Note"
    )

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        dlgs = conn.execute("SELECT dialogue_id, session_id, agent_name, prompt, created_at FROM subagent_dialogues ORDER BY created_at DESC LIMIT 5").fetchall()
        traces = conn.execute("SELECT trace_id, agent_name, trace_kind, summary, obsidian_note_path, created_at FROM subagent_memory_traces ORDER BY created_at DESC LIMIT 5").fetchall()

        assert len(dlgs) > 0, "subagent_dialogues table is empty"
        assert len(traces) > 0, "subagent_memory_traces table is empty"
        
        print(f"  [PASS] Found {len(dlgs)} dialogues in subagent_dialogues table:")
        for d in dlgs:
            print(f"    - Dialogue ID: {d['dialogue_id']} | Agent: {d['agent_name']} | Session: {d['session_id']}")

        print(f"  [PASS] Found {len(traces)} memory traces in subagent_memory_traces table:")
        for t in traces:
            print(f"    - Trace ID: {t['trace_id']} | Kind: {t['trace_kind']} | Obsidian Note: {t['obsidian_note_path']}")

    # Check Obsidian wiki files in memory/semantic/wiki
    wiki_notes = list(WIKI_DIR.glob("*.md"))
    generated_notes = [note for note in wiki_notes if any(k in note.name for k in ["Research", "RLM", "Verifier", "SuperGraph", "open_deep", "rlm_", "verifier_"])]
    assert len(generated_notes) > 0, "No generated subagent wiki notes found"
    print(f"  [PASS] Found {len(generated_notes)} generated subagent Markdown wiki notes in {WIKI_DIR}:")
    for note in generated_notes[:5]:
        content = note.read_text(encoding="utf-8")
        assert "---" in content and "[[" in content, f"Note {note.name} missing frontmatter or wikilinks"
        print(f"    - Note: {note.name} ({len(content)} bytes)")


def main():
    print("=================================================================")
    print("STARTING MILESTONE 4 AUTOMATED VERIFICATION SUITE (R3, R4, R5)")
    print("=================================================================")
    init_database_schemas()
    test_r3_subagent_handoff_ledger()
    test_r4_smt_z3_verification()
    test_r5_dialogue_and_memory_persistence()
    print("\n=================================================================")
    print("ALL MILESTONE 4 VERIFICATION TESTS PASSED SUCCESSFULLY! (R3, R4, R5)")
    print("=================================================================")


if __name__ == "__main__":
    main()
