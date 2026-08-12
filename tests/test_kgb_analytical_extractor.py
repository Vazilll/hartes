"""
tests/test_kgb_analytical_extractor.py
Automated Unit & Integration Test Suite for vazus_core/kgb_analytical_extractor.py
"""

import os
import sys
import unittest
import json
import sqlite3
import tempfile

sys.stdout.reconfigure(encoding='utf-8')

from vazus_core.kgb_analytical_extractor import (
    ThesisNode,
    ProtocolNode,
    KGBAnalyticalExtractor,
    extract_kgb_analytics,
    evaluate_ach_hypotheses,
    persist_kgb_analytics_to_supergraph
)


class TestKGBAnalyticalExtractor(unittest.TestCase):

    def setUp(self):
        """Set up temporary SQLite database for testing isolation."""
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.temp_db_fd)
        self.extractor = KGBAnalyticalExtractor(db_path=self.temp_db_path)

    def tearDown(self):
        """Clean up temporary database file."""
        if os.path.exists(self.temp_db_path):
            try:
                os.remove(self.temp_db_path)
            except Exception:
                pass

    def test_01_extract_kgb_analytics_structure(self):
        """Verify extract_kgb_analytics returns mandatory keys and structure."""
        sample_input = {
            "scene_id": "scene_test01",
            "transcript": "Регулярная суставная разминка перед силовыми тренировками снижает риск микротравм коленей."
        }
        res = extract_kgb_analytics(sample_input, db_path=self.temp_db_path)
        self.assertIsInstance(res, dict)
        required_keys = ["thesis_nodes", "protocol_nodes", "causes_edges", "requires_edges", "contradicts_edges"]
        for key in required_keys:
            self.assertIn(key, res, f"Missing key '{key}' in extraction result")

    def test_02_thesis_node_extraction(self):
        """Verify extraction of ThesisNode claims and ACH initial status."""
        sample_input = {
            "transcript": "Высокие дозы Витамина D3 стимулируют синтез остеокальцина в остеобластах."
        }
        res = extract_kgb_analytics(sample_input, db_path=self.temp_db_path)
        theses = res["thesis_nodes"]
        self.assertGreaterEqual(len(theses), 1, "Should extract at least one ThesisNode")
        t0 = theses[0]
        self.assertEqual(t0["node_type"], "ThesisNode")
        self.assertIn("statement", t0)
        self.assertIn("confidence_score", t0)
        self.assertIn(t0["ach_status"], ["HYPOTHESIS", "ACCEPTED", "REJECTED", "DISPROVED"])

    def test_03_protocol_node_extraction(self):
        """Verify extraction of ProtocolNode step-by-step algorithms."""
        sample_input = {
            "transcript": "Протокол циклирования Бора: принимать 10 мг ежедневно в течение 2 недель, затем делать 1 неделю перерыв для предотвращения десенсибилизации рецепторов."
        }
        res = extract_kgb_analytics(sample_input, db_path=self.temp_db_path)
        protocols = res["protocol_nodes"]
        self.assertGreaterEqual(len(protocols), 1, "Should extract at least one ProtocolNode")
        p0 = protocols[0]
        self.assertEqual(p0["node_type"], "ProtocolNode")
        self.assertIn("steps", p0)
        self.assertIn("frequency_periodicity", p0)

    def test_04_causes_edge_extraction(self):
        """Verify extraction of CAUSES edge causal relationships."""
        sample_input = {
            "transcript": "Отсутствие суставной разминки вызывает микротравмы связок и приводит к воспалению коленного сустава."
        }
        res = extract_kgb_analytics(sample_input, db_path=self.temp_db_path)
        causes = res["causes_edges"]
        self.assertGreaterEqual(len(causes), 1, "Should extract at least one CAUSES edge")
        c0 = causes[0]
        self.assertEqual(c0["relation"], "CAUSES")
        self.assertGreater(c0["strength"], 0.0)

    def test_05_requires_edge_extraction(self):
        """Verify extraction of REQUIRES prerequisite dependencies."""
        sample_input = {
            "transcript": "Приём высоких доз Витамина D3 (10000 МЕ) требует обязательного сопроводительного приёма Витамина K2 и Магния."
        }
        res = extract_kgb_analytics(sample_input, db_path=self.temp_db_path)
        requires = res["requires_edges"]
        self.assertGreaterEqual(len(requires), 1, "Should extract at least one REQUIRES edge")
        r0 = requires[0]
        self.assertEqual(r0["relation"], "REQUIRES")
        self.assertGreaterEqual(r0["strength"], 0.8)

    def test_06_contradicts_edge_and_ach_matrix(self):
        """Verify detection of CONTRADICTS edges and ACH hypothesis rejection."""
        sample_input = {
            "transcript": "Утверждение А: Приём Витамина D3 в монотерапии абсолютно безопасен. Утверждение Б: Монотерапия Витамином D3 без K2 приводит к опасной кальцификации артерий и противоречит безопасному приёму."
        }
        res = extract_kgb_analytics(sample_input, db_path=self.temp_db_path)
        contradicts = res["contradicts_edges"]
        self.assertGreaterEqual(len(contradicts), 1, "Should detect CONTRADICTS relation between opposing statements")
        c0 = contradicts[0]
        self.assertEqual(c0["relation"], "CONTRADICTS")

        theses = res["thesis_nodes"]
        statuses = [t["ach_status"] for t in theses]
        self.assertTrue(any(s in ["REJECTED", "DISPROVED"] for s in statuses), "ACH engine should mark contradicted claim as REJECTED or DISPROVED")

    def test_07_supergraph_persistence(self):
        """Verify persistence into SQLite kg_nodes and kg_edges tables."""
        sample_input = {
            "scene_id": "scene_persistence_test",
            "transcript": "Приём Бора 10 мг снижает ГСПГ на 20% и повышает свободный тестостерон. Данный протокол требует циклирования 2 недели через 1 неделю."
        }
        res = extract_kgb_analytics(sample_input, db_path=self.temp_db_path)
        inserted_count = persist_kgb_analytics_to_supergraph(res, db_path=self.temp_db_path)
        self.assertGreater(inserted_count, 0, "Should persist nodes and edges into SQLite database")

        conn = sqlite3.connect(self.temp_db_path)
        cur = conn.cursor()

        nodes_rows = cur.execute("SELECT id, name, domain, node_type, embedding_json FROM kg_nodes").fetchall()
        self.assertGreaterEqual(len(nodes_rows), 1, "kg_nodes table should contain inserted entities")

        # Verify 768D embedding json format
        emb = json.loads(nodes_rows[0][4])
        self.assertEqual(len(emb), 768, "Embedding vector must be 768D")

        edges_rows = cur.execute("SELECT source_id, target_id, relation, strength FROM kg_edges").fetchall()
        self.assertGreaterEqual(len(edges_rows), 1, "kg_edges table should contain inserted relationships")

        conn.close()

    def test_08_evaluate_ach_hypotheses_helper(self):
        """Verify export helper evaluate_ach_hypotheses function directly."""
        hypotheses = [
            {"id": "H1", "label": "Магний улучшает качество сна"},
            {"id": "H2", "label": "Магний не оказывает эффекта на сон"}
        ]
        evidence = [
            {"id": "E1", "statement": "Клинические исследования показывают, что Магний снижает кортизол и улучшает качество сна.", "confidence": 0.9}
        ]
        ach_res = evaluate_ach_hypotheses(hypotheses, evidence)
        self.assertIn("inconsistency_scores", ach_res)
        self.assertIn("ranked_hypotheses", ach_res)
        self.assertIn("matrix", ach_res)
        self.assertEqual(ach_res["ranked_hypotheses"][0]["hypothesis_id"], "H1")

    def test_09_ach_hypothesis_ranking_top_ranked_score_above_threshold(self):
        """Verify that top-ranked hypothesis (min_score) is ACCEPTED even when score > 0.5."""
        hypotheses = [
            {"id": "H1", "label": "Прием цинка стимулирует иммунитет"},
            {"id": "H2", "label": "Прием цинка не стимулирует иммунитет"}
        ]
        evidence = [
            {"id": "E1", "statement": "Исследование заявляет что прием цинка стимулирует иммунитет", "confidence": 0.9},
            {"id": "E2", "statement": "Второй источник заявляет что прием цинка не стимулирует иммунитет", "confidence": 0.6}
        ]
        ach_res = evaluate_ach_hypotheses(hypotheses, evidence)
        ranked = ach_res["ranked_hypotheses"]
        self.assertEqual(len(ranked), 2)
        top = next(h for h in ranked if h["hypothesis_id"] == "H1")
        bottom = next(h for h in ranked if h["hypothesis_id"] == "H2")
        self.assertEqual(top["inconsistency_score"], 0.6)
        self.assertEqual(bottom["inconsistency_score"], 0.9)
        self.assertEqual(top["ach_status"], "ACCEPTED")
        self.assertEqual(bottom["ach_status"], "DISPROVED")


    def test_10_contradiction_resolution_tied_scores(self):
        """Verify that mutually contradictory claims connected by CONTRADICTS edges do not remain both ACCEPTED."""
        sample_input = {
            "transcript": "Утверждение 1: Приём омега-3 жирных кислот абсолютно безопасен в любых дозах. Утверждение 2: Приём высоких доз омега-3 противоречит безопасному приёму и вызывает разжижение крови и опасные кровотечения."
        }
        res = extract_kgb_analytics(sample_input, db_path=self.temp_db_path)
        theses = res["thesis_nodes"]
        claim_theses = [t for t in theses if not (isinstance(t, dict) and (t.get("properties", {}).get("container") or t.get("id", "").startswith("scene_")))]
        statuses = [t["ach_status"] for t in claim_theses]
        self.assertGreaterEqual(len(statuses), 2)
        self.assertNotEqual((statuses[0], statuses[1]), ("ACCEPTED", "ACCEPTED"), "Mutually contradictory claims must not both remain ACCEPTED")
        self.assertTrue(any(s in ["REJECTED", "DISPROVED"] for s in statuses), "Contradicted claim must be transitioned to REJECTED or DISPROVED")


if __name__ == "__main__":
    unittest.main()

