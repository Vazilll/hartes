"""
C:\\vazus\\.agents\\teamwork_preview_challenger_m2_2\\stress_test_harness.py
Adversarial Stress Test Harness for KGB/FSB Analytical Knowledge Extractor Engine.
"""

import os
import sys
import json
import time
import tempfile
import sqlite3
import threading
import traceback
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, r"C:\vazus")

sys.stdout.reconfigure(encoding='utf-8')

from vazus_core.kgb_analytical_extractor import (
    ThesisNode,
    ProtocolNode,
    KGBAnalyticalExtractor,
    extract_kgb_analytics,
    evaluate_ach_hypotheses,
    persist_kgb_analytics_to_supergraph
)

def log_test(name, result, msg=""):
    status = "PASS" if result else "FAIL"
    print(f"[{status}] {name} {('- ' + msg) if msg else ''}", flush=True)

def run_all_stress_tests():
    print("=== STARTING ADVERSARIAL STRESS TESTS FOR KGB/FSB ANALYTICAL EXTRACTOR ===")
    
    # 1. ACH Matrix Stress & Mathematical Consistency Test
    test_ach_multi_hypotheses()

    # 2. Causal Cycle Detection & DAG Acyclicity Stress Test
    test_causal_cycle_prevention()

    # 3. Pathological Text & Malformed Inputs Stress Test
    test_pathological_inputs()

    # 4. Multi-Threaded Concurrent SQLite Persistence & Locking Test
    test_concurrent_persistence()

    # 5. Vector Embedding Dimension & Fallback Verification
    test_embedding_dimension_and_fallback()

    print("=== ADVERSARIAL STRESS TESTING COMPLETED ===")

def test_ach_multi_hypotheses():
    print("\n--- Test 1: ACH Matrix Multi-Hypothesis Stress & Inconsistency Scoring ---")
    try:
        hypotheses = [
            {"id": "H1", "label": "Препарат А снижает уровень кортизола и нормализует сон"},
            {"id": "H2", "label": "Препарат А увеличивает кортизол и вызывает бессонницу"},
            {"id": "H3", "label": "Препарат А не имеет никакого влияния на кортизол"},
            {"id": "H4", "label": "Препарат А опасен для нервной системы"},
        ]
        evidence = [
            {"id": "E1", "statement": "Клинические исследования подтверждают: Препарат А существенно снижает кортизол.", "confidence": 0.95},
            {"id": "E2", "statement": "Наблюдения показывают, что Препарат А вызывает бессонницу у 10% пациентов.", "confidence": 0.70},
            {"id": "E3", "statement": "Анализы крови свидетельствуют: Препарат А безопасен и нормализует сон.", "confidence": 0.90},
            {"id": "E4", "statement": "Утверждение что Препарат А ошибочно увеличивает кортизол опровергается тестами.", "confidence": 0.85},
        ]

        ach_res = evaluate_ach_hypotheses(hypotheses, evidence)
        matrix = ach_res.get("matrix", [])
        scores = ach_res.get("inconsistency_scores", {})
        ranked = ach_res.get("ranked_hypotheses", [])
        contradictions = ach_res.get("contradictions_detected", [])

        # Check ranking ordering
        log_test("ACH Matrix Generation", len(matrix) == len(evidence), f"Matrix rows: {len(matrix)}")
        log_test("ACH Inconsistency Scores Computed", len(scores) == len(hypotheses), f"Scores: {scores}")
        log_test("ACH Hypothesis Ranking", len(ranked) == len(hypotheses), f"Ranked: {ranked}")

        # Check top-ranked hypothesis status
        top_h = ranked[0]
        log_test("ACH Top Hypothesis Accepted", top_h["ach_status"] == "ACCEPTED", f"Top hypothesis: {top_h}")
        
    except Exception as e:
        log_test("ACH Multi-Hypothesis Test", False, f"Exception: {e}\n{traceback.format_exc()}")

def safe_remove(path):
    try:
        if os.path.exists(path):
            import gc
            gc.collect()
            os.remove(path)
    except Exception as e:
        print(f"[Cleanup Note] Could not remove {path}: {e}", flush=True)

def test_causal_cycle_prevention():
    print("\n--- Test 2: Causal Cycle Prevention & DAG Acyclicity Test ---")
    temp_fd, temp_path = tempfile.mkstemp(suffix=".db")
    os.close(temp_fd)
    try:
        text = (
            "Событие А приводит к событию Б. "
            "Событие Б приводит к событию В. "
            "Событие В приводит к событию А."
        )
        res = extract_kgb_analytics({"transcript": text}, db_path=temp_path)
        causes = res.get("causes_edges", [])

        adj = {}
        for edge in causes:
            src, dst = edge["source_id"], edge["target_id"]
            adj.setdefault(src, set()).add(dst)

        def find_cycle(node, visited, rec_stack):
            visited.add(node)
            rec_stack.add(node)
            for neighbor in adj.get(node, []):
                if neighbor not in visited:
                    if find_cycle(neighbor, visited, rec_stack):
                        return True
                elif neighbor in rec_stack:
                    return True
            rec_stack.remove(node)
            return False

        has_cycle = False
        visited = set()
        rec_stack = set()
        for node in list(adj.keys()):
            if node not in visited:
                if find_cycle(node, visited, rec_stack):
                    has_cycle = True
                    break

        log_test("Causal Graph Acyclicity Check", not has_cycle, f"Extracted causes edges: {len(causes)}, Has Cycle: {has_cycle}")
    except Exception as e:
        log_test("Causal Cycle Prevention Test", False, f"Exception: {e}\n{traceback.format_exc()}")
    finally:
        safe_remove(temp_path)

def test_pathological_inputs():
    print("\n--- Test 3: Pathological Text & Malformed Inputs Stress Test ---")
    inputs_to_test = [
        ("Empty dict", {}),
        ("Empty string transcript", {"transcript": ""}),
        ("Whitespace string", {"transcript": "   \n\t  "}),
        ("Non-string transcript", {"transcript": 12345}),
        ("SQL injection attempt in text", {"transcript": "DROP TABLE kg_nodes; DELETE FROM kg_edges; --"}),
        ("Huge transcript (200 lines)", {"transcript": "Регулярный прием Витамина D3 стимулирует иммунитет.\n" * 200}),
        ("Special characters & null bytes", {"transcript": "Заблуждение \x00 и \u0000 ошибочно приводит к <script>alert(1)</script>"}),
    ]

    temp_fd, temp_path = tempfile.mkstemp(suffix=".db")
    os.close(temp_fd)

    try:
        extractor = KGBAnalyticalExtractor(db_path=temp_path)
        for label, inp in inputs_to_test:
            try:
                res = extractor.extract(inp if isinstance(inp, dict) else {"text": str(inp)})
                log_test(f"Pathological Input: {label}", res.get("status") == "SUCCESS", f"Theses: {res.get('theses_extracted')}, Protocols: {res.get('protocols_extracted')}")
            except Exception as e:
                log_test(f"Pathological Input: {label}", False, f"Crash/Exception: {e}")
    finally:
        safe_remove(temp_path)

def test_concurrent_persistence():
    print("\n--- Test 4: Multi-Threaded Concurrent SQLite Persistence & Locking Test ---")
    temp_fd, temp_path = tempfile.mkstemp(suffix=".db")
    os.close(temp_fd)

    errors = []
    threads = []

    def worker(thread_idx):
        try:
            extractor = KGBAnalyticalExtractor(db_path=temp_path)
            sample_data = {
                "scene_id": f"scene_thread_{thread_idx}",
                "transcript": f"Поток {thread_idx}: Приём Бора 10 мг ежедневно стимулирует синтез тестостерона и требует циклирования."
            }
            res = extractor.extract(sample_data)
            if res.get("status") != "SUCCESS":
                errors.append(f"Thread {thread_idx} extraction status failed")
        except Exception as e:
            errors.append(f"Thread {thread_idx} exception: {e}")

    try:
        for i in range(5):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        log_test("Concurrent Persistence Test (5 threads)", len(errors) == 0, f"Errors encountered: {errors}")

        conn = sqlite3.connect(temp_path)
        cur = conn.cursor()
        nodes_count = cur.execute("SELECT COUNT(*) FROM kg_nodes").fetchone()[0]
        edges_count = cur.execute("SELECT COUNT(*) FROM kg_edges").fetchone()[0]
        conn.close()

        log_test("SQLite Concurrent Insert Consistency", nodes_count > 0 and edges_count > 0, f"Total nodes in DB: {nodes_count}, Total edges: {edges_count}")

    finally:
        safe_remove(temp_path)

def test_embedding_dimension_and_fallback():
    print("\n--- Test 5: Vector Embedding Dimension & Fallback Verification ---")
    temp_fd, temp_path = tempfile.mkstemp(suffix=".db")
    os.close(temp_fd)

    try:
        res = extract_kgb_analytics({
            "transcript": "Утверждение для проверки вектора эмбеддинга 768D в SQLite."
        }, db_path=temp_path)

        conn = sqlite3.connect(temp_path)
        cur = conn.cursor()
        rows = cur.execute("SELECT id, name, embedding_json FROM kg_nodes").fetchall()
        conn.close()

        log_test("SQLite Nodes Count for Embedding Check", len(rows) > 0, f"Nodes: {len(rows)}")

        vector_dim_correct = True
        for row_id, name, emb_json in rows:
            emb = json.loads(emb_json)
            if not isinstance(emb, list) or len(emb) != 768:
                vector_dim_correct = False
                log_test(f"Embedding Dim Check ({row_id})", False, f"Actual len: {len(emb) if isinstance(emb, list) else type(emb)}")
                break

        if vector_dim_correct:
            log_test("All Persisted Embeddings are 768D", True, f"Checked {len(rows)} nodes")

    finally:
        safe_remove(temp_path)


if __name__ == "__main__":
    run_all_stress_tests()
