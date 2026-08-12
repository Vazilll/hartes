"""
C:\vazus\.agents\teamwork_preview_challenger_m2_1\stress_test_kgb_extractor.py

Empirical Stress Testing & Boundary Validation Harness
for vazus_core/kgb_analytical_extractor.py
"""

import os
import sys
import json
import sqlite3
import traceback
import tempfile
from typing import Dict, Any, List

# Ensure vazus root is in sys.path
sys.path.insert(0, r"C:\vazus")

from vazus_core.kgb_analytical_extractor import (
    KGBAnalyticalExtractor,
    extract_kgb_analytics,
    evaluate_ach_hypotheses,
    persist_kgb_analytics_to_supergraph,
    ThesisNode,
    ProtocolNode
)

REPORT_RESULTS = {}


def log_test(test_name: str, passed: bool, details: str, data: Any = None):
    print(f"[{'PASS' if passed else 'FAIL'}] {test_name}: {details}")
    REPORT_RESULTS[test_name] = {
        "passed": passed,
        "details": details,
        "data": data
    }


def test_boundary_1_empty_input():
    print("\n--- Test 1: Empty / Null Inputs ---")
    try:
        # Case 1.1: Completely empty dict
        res1 = extract_kgb_analytics({})
        assert res1["status"] == "SUCCESS", "Empty dict should return SUCCESS status"
        assert len(res1["thesis_nodes"]) == 0, "Thesis count should be 0 for empty dict"
        assert len(res1["protocol_nodes"]) == 0, "Protocol count should be 0 for empty dict"
        assert len(res1["edges"]) == 0, "Edge count should be 0 for empty dict"

        # Case 1.2: Whitespace only string
        res2 = extract_kgb_analytics({"transcript": "   \n\t  \xa0  "})
        assert len(res2["thesis_nodes"]) == 0, "Whitespace transcript should yield 0 thesis nodes"

        # Case 1.3: None transcript
        res3 = extract_kgb_analytics({"transcript": None})
        assert len(res3["thesis_nodes"]) == 0, "None transcript should yield 0 thesis nodes"

        # Case 1.4: Short text (< 8 chars)
        res4 = extract_kgb_analytics({"transcript": "Да. Нет."})
        assert len(res4["thesis_nodes"]) == 0, "Short text under 8 chars should be skipped"

        log_test("Boundary_EmptyInput", True, "Successfully handled empty, whitespace, None, and short inputs without errors.")
    except Exception as e:
        log_test("Boundary_EmptyInput", False, f"Exception occurred: {e}\n{traceback.format_exc()}")


def test_boundary_2_noisy_russian_transcripts():
    print("\n--- Test 2: Noisy Russian Transcripts ---")
    try:
        noisy_text = (
            "[00:01:23] (музыка) (смех) Э-э-э, приём   дозировки 5000 МЕ Витамина D3   ежедневно "
            "(аплодисменты)\u200b\xa0 стимулирует синтез остеокальцина... (пауза) Однако следует "
            "обязательно принимать 100 мкг Витамина K2 в течение 4 недель для предотвращения "
            "кальцификации сосудов! (кашель) [шум в зале]"
        )
        res = extract_kgb_analytics({
            "scene_id": "scene_noisy_01",
            "transcript": noisy_text
        })

        theses = res["thesis_nodes"]
        protocols = res["protocol_nodes"]
        requires_edges = res["requires_edges"]

        # Check noise removal
        for t in theses:
            assert "(музыка)" not in t["statement"], "Noise tag (музыка) should be stripped"
            assert "(аплодисменты)" not in t["statement"], "Noise tag (аплодисменты) should be stripped"

        # Check protocol parsing under noise
        assert len(protocols) >= 1, "Should detect protocol directive 'следует обязательно принимать'"
        p0 = protocols[0]
        assert "100 мкг" in p0["frequency_periodicity"] or "4 недель" in p0["frequency_periodicity"], \
            f"Periodicity regex failed on noisy transcript: {p0['frequency_periodicity']}"

        log_test("Boundary_NoisyTranscripts", True, f"Cleaned noise tags and extracted {len(theses)} theses and {len(protocols)} protocols successfully.", {
            "theses": [t["statement"] for t in theses],
            "protocols": [p["name"] for p in protocols]
        })
    except Exception as e:
        log_test("Boundary_NoisyTranscripts", False, f"Exception: {e}\n{traceback.format_exc()}")


def test_boundary_3_complex_nested_protocols():
    print("\n--- Test 3: Complex Nested Protocols ---")
    try:
        complex_text = (
            "Протокол фазы 1: Необходимо выполнять разминку 15 минут ежедневно перед тренировкой. "
            "Протокол фазы 2: Следует принимать 10 мг Бора ежедневно в течение 2 недель. "
            "Приём Бора требует обязательного предварительного приёма 400 мг Магния в день. "
            "Протокол фазы 3: Обязательно делать 1 неделю перерыв для предотвращения десенсибилизации рецепторов."
        )

        res = extract_kgb_analytics({
            "scene_id": "scene_complex_protocol",
            "transcript": complex_text
        })

        protocols = res["protocol_nodes"]
        requires_edges = res["requires_edges"]

        # Verify protocols sequence and metadata
        assert len(protocols) >= 3, f"Expected at least 3 protocol nodes, got {len(protocols)}"
        seq_orders = [p["sequence_order"] for p in protocols]
        assert seq_orders == sorted(seq_orders), "Sequence orders should be sequentially ordered"

        # Check for REQUIRES edges connecting sequential steps and prerequisites
        assert len(requires_edges) >= 2, f"Expected at least 2 REQUIRES edges, got {len(requires_edges)}"

        # Check safety warnings extraction
        p_cycl = [p for p in protocols if "десенсибилизации" in p["action_instruction"]]
        assert len(p_cycl) >= 1, "Should identify safety warning protocol"
        assert len(p_cycl[0]["safety_warnings"]) >= 1, "Safety warning should be populated in properties"

        log_test("Boundary_NestedProtocols", True, f"Extracted {len(protocols)} ordered steps, {len(requires_edges)} REQUIRES edges, and safety warnings.", {
            "sequence_orders": seq_orders,
            "requires_count": len(requires_edges)
        })
    except Exception as e:
        log_test("Boundary_NestedProtocols", False, f"Exception: {e}\n{traceback.format_exc()}")


def test_boundary_4_conflicting_theses_and_ach():
    print("\n--- Test 4: Conflicting Theses & ACH Evaluation ---")
    try:
        transcript = (
            "Гипотеза Альфа: Высокие дозы Витамина D3 в монотерапии стимулируют укрепление костей и абсолютно безопасны. "
            "Гипотеза Бета: Высокие дозы Витамина D3 без Витамина K2 вызывают токсичность и противоречат безопасности, приводя к опасной кальцификации артерий."
        )

        custom_hypotheses = [
            {"id": "H_SAFE", "label": "Витамин D3 в монотерапии безопасен"},
            {"id": "H_TOXIC", "label": "Витамин D3 в монотерапии не безопасен и вызывает токсичность"}
        ]

        res = extract_kgb_analytics({
            "scene_id": "scene_ach_conflict",
            "transcript": transcript,
            "hypotheses": custom_hypotheses
        })

        contradicts_edges = res["contradicts_edges"]
        ach_summary = res["ach_matrix_summary"]

        assert len(contradicts_edges) >= 1, f"Should detect CONTRADICTS edge between opposing statements, got {len(contradicts_edges)}"

        ranked = ach_summary.get("ranked_hypotheses", [])
        assert len(ranked) == 2, "ACH summary should rank both hypotheses"

        # Check statuses
        theses = res["thesis_nodes"]
        statuses = [t["ach_status"] for t in theses]
        assert any(s in ["REJECTED", "DISPROVED"] for s in statuses), f"Contradicted claim should be marked REJECTED or DISPROVED, got {statuses}"

        log_test("Boundary_ConflictingThesesACH", True, f"Detected {len(contradicts_edges)} CONTRADICTS edges. ACH matrix ranked hypotheses correctly.", {
            "contradicts": contradicts_edges,
            "ach_ranked": ranked
        })
    except Exception as e:
        log_test("Boundary_ConflictingThesesACH", False, f"Exception: {e}\n{traceback.format_exc()}")


def test_boundary_5_circular_causal_graphs():
    print("\n--- Test 5: Circular Causal Graphs ---")
    try:
        # A causes B, B causes C, C causes A
        # Let's see how extract_graph_edges handles nodes that might form a cycle
        t1 = ThesisNode(id="thesis_A", name="Узел A", statement="Повышение уровня соматотропина вызывает гипертрофию тканей.")
        t2 = ThesisNode(id="thesis_B", name="Узел B", statement="Гипертрофия тканей вызывает повышенный расход глюкозы.")
        t3 = ThesisNode(id="thesis_C", name="Узел C", statement="Повышенный расход глюкозы вызывает повышение уровня соматотропина.")

        extractor = KGBAnalyticalExtractor()
        causes_edges, requires_edges, contradicts_edges, belongs_to_edges = extractor.extract_graph_edges(
            theses=[t1, t2, t3],
            protocols=[],
            scene_id="scene_cycle_test"
        )

        # Print detected causes edges
        print(f"Cycle test causes edges count: {len(causes_edges)}")
        for edge in causes_edges:
            print(f"  Edge: {edge['source_id']} -> {edge['target_id']} ({edge['relation']})")

        # Check if cycle was prevented (has_path check)
        # If A->B and B->C are added, when checking C->A: has_path(A, C) returns True, so C->A must NOT be added.
        edge_pairs = [(e["source_id"], e["target_id"]) for e in causes_edges]

        has_ab = ("thesis_A", "thesis_B") in edge_pairs or ("thesis_B", "thesis_A") in edge_pairs
        has_bc = ("thesis_B", "thesis_C") in edge_pairs or ("thesis_C", "thesis_B") in edge_pairs
        has_ca = ("thesis_C", "thesis_A") in edge_pairs or ("thesis_A", "thesis_C") in edge_pairs

        # Check if all 3 edges forming a loop exist simultaneously
        # Forward or backward: if cycle exists in directed graph
        is_cyclic = (("thesis_A", "thesis_B") in edge_pairs and
                     ("thesis_B", "thesis_C") in edge_pairs and
                     ("thesis_C", "thesis_A") in edge_pairs)

        assert not is_cyclic, "Causal DAG enforcement FAILED! Circular graph cycle A->B->C->A was formed."

        log_test("Boundary_CircularCausalGraphs", True, f"DAG cycle check prevented circular causal loop. Total causes edges: {len(causes_edges)}", {
            "edge_pairs": edge_pairs,
            "is_cyclic": is_cyclic
        })
    except Exception as e:
        log_test("Boundary_CircularCausalGraphs", False, f"Exception: {e}\n{traceback.format_exc()}")


def test_boundary_6_sqlite_persistence_vazus_db():
    print("\n--- Test 6: SQLite Persistence in vazus.db ---")
    try:
        db_path = r"C:\vazus\vazus.db"

        sample_input = {
            "scene_id": "scene_challenger_verify_01",
            "source_file": "test_source_challenger.txt",
            "transcript": (
                "Дефицит Магния вызывает нарушение усвоения Витамина D3. "
                "Протокол восполнения: следует принимать 400 мг Цитрата Магния ежедневно перед сном в течение 8 недель. "
                "Данный прием требует предварительной консультации врача."
            ),
            "hypotheses": [
                {"id": "H_MG_D3", "label": "Магний необходим для усвоения Витамина D3"}
            ]
        }

        res = extract_kgb_analytics(sample_input, db_path=db_path)

        # Check result structure
        assert res["status"] == "SUCCESS", "Extraction failed"
        assert res["persisted_counts"]["total_entities"] > 0, "Persisted count must be > 0"

        # Direct SQLite Inspection of C:\vazus\vazus.db
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        # Query kg_nodes
        cur.execute("SELECT id, name, domain, node_type, description, tags, properties, embedding_json FROM kg_nodes WHERE id LIKE 'thesis_%' OR id LIKE 'protocol_%'")
        node_rows = cur.fetchall()
        assert len(node_rows) >= 2, f"Expected at least 2 nodes in kg_nodes, found {len(node_rows)}"

        # Verify fields and 768D vector format
        sample_node = node_rows[0]
        node_id, name, domain, node_type, desc, tags, props_json, emb_json = sample_node

        assert domain == "kgb_analytics", f"Domain mismatch: {domain}"
        assert node_type in ("ThesisNode", "ProtocolNode"), f"Invalid node_type: {node_type}"

        emb = json.loads(emb_json)
        assert isinstance(emb, list), "Embedding must be JSON array"
        assert len(emb) == 768, f"Embedding vector dimension must be 768, got {len(emb)}"

        # Query kg_edges
        cur.execute("SELECT source_id, target_id, relation, strength, properties FROM kg_edges")
        edge_rows = cur.fetchall()
        assert len(edge_rows) >= 1, f"Expected at least 1 edge in kg_edges, found {len(edge_rows)}"

        relations = set(r[2] for r in edge_rows)
        print(f"Persisted relation types in kg_edges: {relations}")

        conn.close()

        log_test("Boundary_SQLitePersistence", True, f"Verified vazus.db tables kg_nodes ({len(node_rows)} rows) and kg_edges ({len(edge_rows)} rows) with 768D embeddings.", {
            "node_count": len(node_rows),
            "edge_count": len(edge_rows),
            "sample_embedding_len": len(emb),
            "relation_types": list(relations)
        })
    except Exception as e:
        log_test("Boundary_SQLitePersistence", False, f"Exception: {e}\n{traceback.format_exc()}")


def run_all_tests():
    test_boundary_1_empty_input()
    test_boundary_2_noisy_russian_transcripts()
    test_boundary_3_complex_nested_protocols()
    test_boundary_4_conflicting_theses_and_ach()
    test_boundary_5_circular_causal_graphs()
    test_boundary_6_sqlite_persistence_vazus_db()

    print("\n==========================================")
    print("STRESS TEST SUMMARY:")
    all_passed = True
    for tname, tres in REPORT_RESULTS.items():
        status = "PASS" if tres["passed"] else "FAIL"
        if not tres["passed"]:
            all_passed = False
        print(f"  [{status}] {tname}")
    print("==========================================")

    # Save JSON summary to workspace directory
    summary_path = r"C:\vazus\.agents\teamwork_preview_challenger_m2_1\stress_test_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(REPORT_RESULTS, f, ensure_ascii=False, indent=2)

    return all_passed


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
