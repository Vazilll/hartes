"""
Empirical Verification & Stress Test Harness for kgb_analytical_extractor.py
Created by Challenger 1 (Milestone 2 - R2: KGB/FSB Analytical Knowledge Extractor)
"""

import os
import sys
import unittest
import json
import sqlite3
import tempfile
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, r"C:\vazus")

from vazus_core.kgb_analytical_extractor import (
    ThesisNode,
    ProtocolNode,
    KGBAnalyticalExtractor,
    extract_kgb_analytics,
    evaluate_ach_hypotheses,
    persist_kgb_analytics_to_supergraph
)


class EdgeCaseAndSchemaStressTest(unittest.TestCase):

    def setUp(self):
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix="_test_kgb.db")
        os.close(self.temp_db_fd)
        self.extractor = KGBAnalyticalExtractor(db_path=self.temp_db_path)

    def tearDown(self):
        if os.path.exists(self.temp_db_path):
            try:
                os.remove(self.temp_db_path)
            except Exception:
                pass

    # -------------------------------------------------------------
    # Category 1: Empty and Null Input Edge Cases
    # -------------------------------------------------------------
    def test_empty_string_input(self):
        """Test empty string transcript/text handling."""
        inputs = [
            "",
            "   ",
            "\n\t  \n",
            {"transcript": ""},
            {"text": "   "},
            {"content": None},
            {"transcript": "[музыка] (аплодисменты) [шум]"}, # normalized to empty string
        ]
        for idx, inp in enumerate(inputs):
            with self.subTest(input_index=idx):
                res = extract_kgb_analytics(inp, db_path=self.temp_db_path)
                self.assertEqual(res["status"], "SUCCESS")
                self.assertEqual(res["theses_extracted"], 0)
                self.assertEqual(res["protocols_extracted"], 0)
                self.assertEqual(res["edges_extracted"], 0)
                self.assertIn("persisted_counts", res)

    # -------------------------------------------------------------
    # Category 2: Malformed Scene Structures (Empirical Robustness Check)
    # -------------------------------------------------------------
    def test_malformed_scene_structures(self):
        """Test malformed dictionaries with unexpected types, missing fields, or invalid timestamp formats."""
        malformed_inputs = [
            {}, # completely empty dict
            {"scene_id": 12345, "transcript": "Регулярный прием Витамина D3 стимулирует иммунитет."}, # scene_id as int
            {"transcript": "Сделайте разминку перед тренировкой.", "start_sec": "not_a_float", "end_sec": None}, # invalid timestamps
            {"transcript": "Прием Бора повышает свободный тестостерон.", "hypotheses": "not_a_list"}, # hypotheses as non-list / string
            {"transcript": "Тестовый текст", "hypotheses": [{"invalid_key": "val"}]}, # hypothesis without id/label
            {"transcript": 123456789}, # transcript is int
            {"content": ["List", "of", "strings"]}, # content is list instead of str
        ]
        failures = []
        for idx, inp in enumerate(malformed_inputs):
            try:
                res = extract_kgb_analytics(inp, db_path=self.temp_db_path)
                self.assertIn("status", res)
            except Exception as e:
                failures.append((idx, inp, type(e).__name__, str(e)))

        if failures:
            failure_msgs = [f"Input #{i} ({inp}): {err_type}: {err_msg}" for i, inp, err_type, err_msg in failures]
            self.fail(f"Extractor crashed on {len(failures)} malformed inputs:\n" + "\n".join(failure_msgs))

    # -------------------------------------------------------------
    # Category 3: Complex Multi-Clause Russian Text & Conflicting Hypotheses
    # -------------------------------------------------------------
    def test_complex_multiclause_russian_text(self):
        """Test long, multi-clause Russian analytical text with complex scientific terms and directives."""
        complex_text = (
            "Согласно проведенным мета-анализам, пероральный прием высокодозированного цинка (50 мг/сутки) "
            "стимулирует активности супероксиддисмутазы и приводит к снижению маркеров системного воспаления. "
            "Однако длительный монотерапевтический прием цинка без меди вызывает дефицит меди и влечет за собой гипохромную анемию. "
            "Поэтому в рамках протокола необходимо обязательно принимать 2 мг меди на каждые 15 мг цинка. "
            "В отличие от традиционных рекомендаций, прием цинка натощак ошибочно считается безопасным, "
            "напротив, это вызывает сильную тошноту и раздражение слизистой оболочки желудка."
        )
        scene = {
            "scene_id": "scene_complex_ru_01",
            "transcript": complex_text,
            "hypotheses": [
                {"id": "H1", "label": "Прием цинка стимулирует супероксиддисмутазу"},
                {"id": "H2", "label": "Прием цинка не стимулирует супероксиддисмутазу"},
                {"id": "H3", "label": "Прием цинка натощак безопасен"},
                {"id": "H4", "label": "Прием цинка натощак ошибочно считается безопасным и вызывает тошноту"}
            ]
        }
        res = extract_kgb_analytics(scene, db_path=self.temp_db_path)

        self.assertGreater(res["theses_extracted"], 0, "Should extract theses from complex text")
        self.assertGreater(res["protocols_extracted"], 0, "Should extract protocol directive (необходимо обязательно принимать)")
        self.assertGreater(res["edges_extracted"], 0, "Should extract graph edges")

        # Check relation coverage
        rel_types = set(e["relation"] for e in res["edges"])
        self.assertIn("CAUSES", rel_types, "Should detect CAUSES relations")
        self.assertIn("REQUIRES", rel_types, "Should detect REQUIRES relations")
        self.assertIn("CONTRADICTS", rel_types, "Should detect CONTRADICTS relations")

        # Check ACH evaluation results
        ach = res["ach_matrix_summary"]
        self.assertIn("ranked_hypotheses", ach)
        self.assertIn("contradictions_detected", ach)
        self.assertGreater(len(ach["contradictions_detected"]), 0, "Should detect contradictions in ACH matrix")

    # -------------------------------------------------------------
    # Category 4: SQLite Database & Schema Verification
    # -------------------------------------------------------------
    def test_database_schema_and_edge_insertions(self):
        """Verify nodes and edges schema, data types, JSON embeddings, and constraints in SQLite."""
        sample_scene = {
            "scene_id": "scene_db_verify_01",
            "transcript": (
                "Высокие дозы Витамина D3 стимулируют синтез остеокальцина. "
                "Прием Витамина D3 требует обязательного приёма Витамина K2. "
                "Монотерапия Витамином D3 без K2 противоречит безопасному приему и вызывает кальцификацию."
            )
        }
        res = extract_kgb_analytics(sample_scene, db_path=self.temp_db_path)
        persisted_count = res["persisted_counts"]["total_entities"]
        self.assertGreater(persisted_count, 0)

        conn = sqlite3.connect(self.temp_db_path)
        cur = conn.cursor()

        # Check kg_nodes schema & data
        cur.execute("PRAGMA table_info(kg_nodes)")
        node_cols = {col[1]: col[2] for col in cur.fetchall()}
        expected_node_cols = ["id", "name", "domain", "node_type", "description", "tags", "properties", "embedding_json"]
        for col in expected_node_cols:
            self.assertIn(col, node_cols, f"Column '{col}' missing in kg_nodes schema")

        # Query inserted nodes
        cur.execute("SELECT id, name, domain, node_type, description, tags, properties, embedding_json FROM kg_nodes")
        nodes_rows = cur.fetchall()
        self.assertGreater(len(nodes_rows), 0, "kg_nodes must contain records")

        for row in nodes_rows:
            n_id, name, domain, node_type, desc, tags, props_json, emb_json = row
            self.assertTrue(n_id, "node id must not be empty")
            self.assertTrue(name, "node name must not be empty")
            self.assertEqual(domain, "kgb_analytics")
            self.assertIn(node_type, ["ThesisNode", "ProtocolNode"])

            # Verify JSON parsing of properties and embedding_json
            props = json.loads(props_json)
            self.assertIsInstance(props, dict)
            emb = json.loads(emb_json)
            self.assertIsInstance(emb, list)
            self.assertEqual(len(emb), 768, f"Embedding dimension for node {n_id} must be 768, got {len(emb)}")

        # Check kg_edges schema & data
        cur.execute("PRAGMA table_info(kg_edges)")
        edge_cols = {col[1]: col[2] for col in cur.fetchall()}
        expected_edge_cols = ["source_id", "target_id", "relation", "strength", "properties"]
        for col in expected_edge_cols:
            self.assertIn(col, edge_cols, f"Column '{col}' missing in kg_edges schema")

        cur.execute("SELECT source_id, target_id, relation, strength, properties FROM kg_edges")
        edges_rows = cur.fetchall()
        self.assertGreater(len(edges_rows), 0, "kg_edges must contain records")

        edge_relations = set()
        for row in edges_rows:
            src, dst, rel, strength, eprops_json = row
            self.assertTrue(src, "edge source_id must not be empty")
            self.assertTrue(dst, "edge target_id must not be empty")
            self.assertIn(rel, ["CAUSES", "REQUIRES", "CONTRADICTS", "BELONGS_TO"])
            self.assertIsInstance(strength, float)
            self.assertGreaterEqual(strength, 0.0)
            self.assertLessEqual(strength, 1.0)
            eprops = json.loads(eprops_json)
            self.assertIsInstance(eprops, dict)
            edge_relations.add(rel)

        conn.close()

    # -------------------------------------------------------------
    # Category 5: Edge Relation Correctness & Referential Integrity
    # -------------------------------------------------------------
    def test_dangling_edge_referential_integrity(self):
        """Verify whether single-sentence sub-clause edge extraction creates dangling edges (edges referencing non-existent nodes)."""
        single_clause_input = {
            "scene_id": "scene_single_cause",
            "transcript": "Прием Бора приводит к повышению уровня свободного тестостерона."
        }
        res = extract_kgb_analytics(single_clause_input, db_path=self.temp_db_path)
        
        conn = sqlite3.connect(self.temp_db_path)
        cur = conn.cursor()

        cur.execute("""
            SELECT e.source_id, e.target_id, e.relation
            FROM kg_edges e
            WHERE e.source_id NOT IN (SELECT id FROM kg_nodes)
               OR e.target_id NOT IN (SELECT id FROM kg_nodes)
        """)
        dangling = cur.fetchall()
        conn.close()

        # We assert that no edge should refer to a node_id missing from kg_nodes
        self.assertEqual(len(dangling), 0, f"Found {len(dangling)} dangling edges referencing uncreated nodes in kg_nodes: {dangling}")

    def test_causal_dag_acyclicity(self):
        """Verify that CAUSES edge extraction enforces DAG acyclicity (no self-loops or cyclic dependencies)."""
        cyclic_text = (
            "Агент А вызывает повышение показателя Б. "
            "Показатель Б приводит к активации агента В. "
            "Агент В вызывает повышение показателя А."
        )
        res = extract_kgb_analytics({"transcript": cyclic_text}, db_path=self.temp_db_path)
        causes_edges = res["causes_edges"]

        # Check no self loops (source_id == target_id)
        for e in causes_edges:
            self.assertNotEqual(e["source_id"], e["target_id"], f"Causal self-loop detected on node {e['source_id']}")

        # Build adjacency graph and check for cycles via Tarjan / DFS
        adj = {}
        for e in causes_edges:
            src, dst = e["source_id"], e["target_id"]
            if src not in adj:
                adj[src] = []
            adj[src].append(dst)

        def is_cyclic(node, visited, rec_stack):
            visited.add(node)
            rec_stack.add(node)
            for neighbor in adj.get(node, []):
                if neighbor not in visited:
                    if is_cyclic(neighbor, visited, rec_stack):
                        return True
                elif neighbor in rec_stack:
                    return True
            rec_stack.remove(node)
            return False

        visited = set()
        rec_stack = set()
        for node in adj:
            if node not in visited:
                self.assertFalse(is_cyclic(node, visited, rec_stack), "Cycle detected in CAUSES graph extraction!")


if __name__ == "__main__":
    unittest.main()
