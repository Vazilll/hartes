"""
verify_kgb_extractor_empirical.py
Empirical Verification & Stress Test Suite for KGB Analytical Extractor (Milestone 2)
Author: Challenger 2
Location: C:\\vazus\\.agents\\teamwork_preview_challenger_m2_2\\verify_kgb_extractor_empirical.py
"""

import os
import sys
import json
import sqlite3
import tempfile
import math
import traceback
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

# Add project root to sys.path
PROJECT_ROOT = Path(r"C:\vazus")
sys.path.insert(0, str(PROJECT_ROOT))

from vazus_core.kgb_analytical_extractor import (
    ThesisNode,
    ProtocolNode,
    KGBAnalyticalExtractor,
    extract_kgb_analytics,
    evaluate_ach_hypotheses,
    persist_kgb_analytics_to_supergraph
)
from vazus_core.embeddings import UnifiedEmbeddingManager


def run_embedding_format_tests():
    print("\n--- TEST SUITE 1: 768D Vector Embedding Format & Dimensionality ---")
    embedder = UnifiedEmbeddingManager(dimension=768)
    
    sample_text = "Исследование биологических активностей бора и витамина D3"
    vec = embedder.get_embedding(sample_text)
    
    print(f"[Check 1.1] Vector type: {type(vec)}")
    assert isinstance(vec, list), f"Expected list, got {type(vec)}"
    print(f"[Check 1.2] Vector length: {len(vec)}")
    assert len(vec) == 768, f"Expected 768D vector, got {len(vec)}"
    
    assert all(isinstance(x, (float, int)) for x in vec), "Vector contains non-numeric values"
    assert not any(math.isnan(x) or math.isinf(x) for x in vec), "Vector contains NaN or Inf values"
    print("[Check 1.3] Vector elements are valid float numbers with no NaN/Inf.")
    
    temp_db_fd, temp_db = tempfile.mkstemp(suffix=".db")
    os.close(temp_db_fd)
        
    try:
        sample_input = {
            "scene_id": "scene_emb_test_01",
            "transcript": "Цинк и Селен играют важную роль в иммунном ответе и синтезе тестостерона."
        }
        res = extract_kgb_analytics(sample_input, db_path=temp_db)
        conn = sqlite3.connect(temp_db)
        cur = conn.cursor()
        rows = cur.execute("SELECT id, name, embedding_json FROM kg_nodes").fetchall()
        conn.close()

        assert len(rows) > 0, "No nodes inserted in kg_nodes"
        for row in rows:
            node_id, name, emb_json_str = row
            assert emb_json_str is not None, f"Node {node_id} has NULL embedding_json"
            parsed_emb = json.loads(emb_json_str)
            assert isinstance(parsed_emb, list), f"Parsed embedding for {node_id} is not list"
            assert len(parsed_emb) == 768, f"Parsed embedding for {node_id} length is {len(parsed_emb)}, expected 768"
            assert not any(math.isnan(x) or math.isinf(x) for x in parsed_emb), f"Parsed embedding for {node_id} has NaN/Inf"
            print(f"[Check 1.4] Persistence Node (ID: {node_id}): verified 768D embedding JSON string (length={len(parsed_emb)})")
    finally:
        if os.path.exists(temp_db):
            try:
                os.remove(temp_db)
            except Exception:
                pass
            
    print("-> PASS: 768D Vector Embedding Format & Dimensionality")


def run_ach_matrix_stress_tests():
    print("\n--- TEST SUITE 2: ACH Heuer Matrix Stress & Edge Case Evaluation ---")
    
    # 1. Opposing Claims Stress Test
    hypotheses = [
        {"id": "H1", "label": "Монотерапия Витамином D3 безопасна для сердечно-сосудистой системы"},
        {"id": "H2", "label": "Монотерапия Витамином D3 вызывает опасную кальцификацию артерий без K2"},
        {"id": "H3", "label": "Витамин D3 вообще не оказывает никакого физиологического эффекта"}
    ]
    
    evidence = [
        {"id": "E1", "statement": "Монотерапия Витамином D3 без K2 приводит к опасной кальцификации артерий и отложению кальция.", "confidence": 0.95},
        {"id": "E2", "statement": "Исследования показывают, что Витамин D3 стимулирует остеокальцин.", "confidence": 0.90},
        {"id": "E3", "statement": "Витамин D3 без сопроводительного приёма K2 противоречит безопасному приёму.", "confidence": 0.85}
    ]
    
    ach_res = evaluate_ach_hypotheses(hypotheses, evidence)
    
    print("[ACH Test 1] Inconsistency scores:")
    for h_id, score in ach_res["inconsistency_scores"].items():
        print(f"  - {h_id}: {score}")
        
    print("[ACH Test 1] Ranked Hypotheses:")
    for r in ach_res["ranked_hypotheses"]:
        print(f"  - Rank: {r['hypothesis_id']} => Status: {r['ach_status']} (Inconsistency Score: {r['inconsistency_score']})")
        
    h1_score = ach_res["inconsistency_scores"].get("H1", 0.0)
    h2_score = ach_res["inconsistency_scores"].get("H2", 0.0)
    assert h1_score > h2_score, f"Expected H1 inconsistency score ({h1_score}) > H2 inconsistency score ({h2_score})"
    
    top_h = ach_res["ranked_hypotheses"][0]
    assert top_h["ach_status"] == "ACCEPTED", f"Top hypothesis status should be ACCEPTED, got {top_h['ach_status']}"
    print("[Check 2.1] Opposing claims ACH scoring correctly ranked supported hypothesis over contradicted hypothesis.")

    # 2. Empty Evidence Edge Case
    empty_ach = evaluate_ach_hypotheses([], [])
    assert empty_ach["matrix"] == [], "Empty hypotheses matrix should be empty"
    assert empty_ach["ranked_hypotheses"] == [], "Empty ranked hypotheses should be empty"
    print("[Check 2.2] Handled empty hypotheses & evidence input gracefully.")
    
    # 3. CONTRADICTS & Status propagation via full extractor pipeline (BUG DEMONSTRATION)
    input_text = {
        "scene_id": "scene_opposing_stress",
        "transcript": (
            "Утверждение 1: Приём омега-3 жирных кислот абсолютно безопасен в любых дозах. "
            "Утверждение 2: Приём высоких доз омега-3 противоречит безопасному приёму и вызывает разжижение крови и опасные кровотечения."
        )
    }
    ext_res = extract_kgb_analytics(input_text)
    
    print(f"[ACH Test 3] Extracted Thesis Nodes count: {len(ext_res['thesis_nodes'])}")
    print(f"[ACH Test 3] Extracted CONTRADICTS Edges count: {len(ext_res['contradicts_edges'])}")
    
    assert len(ext_res['contradicts_edges']) >= 1, "Should detect at least 1 CONTRADICTS edge"
    
    statuses = [t["ach_status"] for t in ext_res["thesis_nodes"]]
    print(f"[ACH Test 3] Thesis ACH statuses: {statuses}")
    
    # Empirical Bug check
    has_rejected_or_disproved = any(s in ["REJECTED", "DISPROVED"] for s in statuses)
    if not has_rejected_or_disproved:
        print("[EMPIRICAL BUG DETECTED]: Contradictory statements both remained marked as 'ACCEPTED'!")
        print("Reason: Line 538 in vazus_core/kgb_analytical_extractor.py checks `if t.ach_status == 'HYPOTHESIS':` but t.ach_status was already set to 'ACCEPTED' by evaluate_ach_hypotheses rank assignment.")
        raise AssertionError("BUG CONFIRMED: Contradicted thesis nodes failed to update status from ACCEPTED to REJECTED/DISPROVED.")
    else:
        print("[Check 2.3] Extractor pipeline correctly extracted CONTRADICTS edges and updated ACH statuses.")

    # 4. DAG Cycle Prevention Stress Test (CAUSES edges)
    theses_cycle = [
        ThesisNode(id="t1", name="Приём кофеина", statement="Приём кофеина повышает уровень дофамина и вызывает бодрость."),
        ThesisNode(id="t2", name="Повышение дофамина", statement="Повышение дофамина приводит к улучшению внимания."),
        ThesisNode(id="t3", name="Улучшение внимания", statement="Улучшение внимания вызывает снижение утомляемости.")
    ]
    extractor = KGBAnalyticalExtractor(db_path=r"C:\vazus\vazus.db")
    causes, reqs, contrs, bel = extractor.extract_graph_edges(theses_cycle, [], scene_id="scene_cycle_test")
    
    causal_adj = {}
    for edge in causes:
        src = edge["source_id"]
        dst = edge["target_id"]
        causal_adj.setdefault(src, set()).add(dst)
        
    def check_cycle(node, visited, rec_stack):
        visited.add(node)
        rec_stack.add(node)
        for neighbor in causal_adj.get(node, []):
            if neighbor not in visited:
                if check_cycle(neighbor, visited, rec_stack):
                    return True
            elif neighbor in rec_stack:
                return True
        rec_stack.remove(node)
        return False

    visited = set()
    rec_stack = set()
    has_cycle = False
    for node in list(causal_adj.keys()):
        if node not in visited:
            if check_cycle(node, visited, rec_stack):
                has_cycle = True
                break
                
    assert not has_cycle, "Causal DAG graph contains a cycle!"
    print("[Check 2.4] Causal edge graph verified acyclic (DAG condition maintained).")


def run_multi_database_tests():
    print("\n--- TEST SUITE 3: Multi-Database Compatibility & Persistence ---")
    
    db_paths = [
        r"C:\vazus\vazus.db",
        r"C:\vazus\memory\dnts.db",
        r"C:\vazus\services\memory\vazus.db"
    ]
    
    sample_input = {
        "scene_id": "scene_multidb_verification",
        "transcript": "Протокол приема Магния: принимать 400 мг Цитрата Магния перед сном для расслабления ЦНС."
    }
    
    res = extract_kgb_analytics(sample_input)
    persisted_count = res.get("persisted_counts", {}).get("total_entities", 0)
    print(f"[MultiDB] Total entities persisted by helper: {persisted_count}")
    assert persisted_count > 0, "Persisted count must be > 0"
    
    for dbp in db_paths:
        p = Path(dbp)
        if not p.exists():
            print(f"[MultiDB Note] Database path {dbp} does not exist on disk, skipping read check.")
            continue
            
        print(f"[MultiDB Inspection] Checking SQLite DB at: {dbp}")
        conn = sqlite3.connect(dbp)
        cur = conn.cursor()
        
        tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        assert "kg_nodes" in tables, f"'kg_nodes' table missing in {dbp}"
        assert "kg_edges" in tables, f"'kg_edges' table missing in {dbp}"
        
        node_count = cur.execute("SELECT COUNT(*) FROM kg_nodes").fetchone()[0]
        edge_count = cur.execute("SELECT COUNT(*) FROM kg_edges").fetchone()[0]
        print(f"  - {dbp}: kg_nodes row count = {node_count}, kg_edges row count = {edge_count}")
        assert node_count > 0, f"kg_nodes is empty in {dbp}"
        
        columns = [col[1] for col in cur.execute("PRAGMA table_info(kg_nodes)").fetchall()]
        expected_cols = ["id", "name", "domain", "node_type", "description", "tags", "properties", "embedding_json"]
        for ec in expected_cols:
            assert ec in columns, f"Column '{ec}' missing in kg_nodes table in {dbp}"
            
        sample_emb_str = cur.execute("SELECT embedding_json FROM kg_nodes WHERE embedding_json IS NOT NULL LIMIT 1").fetchone()[0]
        parsed = json.loads(sample_emb_str)
        assert len(parsed) == 768, f"Expected 768D in {dbp}, got {len(parsed)}"
        
        conn.close()
        print(f"[Check 3.1] DB {dbp} passed schema, node count, edge count, and 768D embedding format check.")

    print("-> PASS: Multi-Database Compatibility & Persistence")


if __name__ == "__main__":
    print("==========================================================")
    print("  KGB Analytical Extractor Empirical Challenge Harness   ")
    print("==========================================================")
    
    try:
        run_embedding_format_tests()
        run_ach_matrix_stress_tests()
        run_multi_database_tests()
        print("\n==========================================================")
        print(" ALL EMPIRICAL VERIFICATION TESTS PASSED SUCCESSFULLY! ")
        print("==========================================================")
    except Exception as e:
        print(f"\n[EMPIRICAL TEST FAIL]: {e}")
        traceback.print_exc()
        sys.exit(1)
