"""
adversarial_test.py
Forensic Auditor Stress-Testing Suite for kgb_analytical_extractor.py
"""

import sys
import os
import unittest
import json
import sqlite3
import tempfile

sys.path.insert(0, r"C:\vazus")

from vazus_core.kgb_analytical_extractor import (
    ThesisNode,
    ProtocolNode,
    KGBAnalyticalExtractor,
    extract_kgb_analytics,
    evaluate_ach_hypotheses,
    persist_kgb_analytics_to_supergraph
)

class TestAdversarialExtractor(unittest.TestCase):

    def setUp(self):
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.temp_db_fd)
        self.extractor = KGBAnalyticalExtractor(db_path=self.temp_db_path)

    def tearDown(self):
        if os.path.exists(self.temp_db_path):
            try:
                os.remove(self.temp_db_path)
            except Exception:
                pass

    def test_novel_domain_astrophysics(self):
        """Test extraction on novel domain text (Astrophysics/Quantum Computing)."""
        input_data = {
            "scene_id": "scene_quantum_99",
            "transcript": "Термодинамический шум вызывает декогеренцию кубитов и приводит к ошибкам вычислений. "
                        "Инструкция по охлаждению: необходимо поддерживать температуру 15 минут ежедневно во избежание срыва суперпозиции."
        }
        res = extract_kgb_analytics(input_data, db_path=self.temp_db_path)
        self.assertEqual(res["status"], "SUCCESS")
        self.assertGreaterEqual(len(res["thesis_nodes"]), 1)
        self.assertGreaterEqual(len(res["protocol_nodes"]), 1)
        self.assertGreaterEqual(len(res["causes_edges"]), 1)

        # Verify CAUSES edge content
        c0 = res["causes_edges"][0]
        self.assertEqual(c0["relation"], "CAUSES")

        # Verify Protocol safety warning & periodicity
        p0 = res["protocol_nodes"][0]
        self.assertIn("15 минут", p0["frequency_periodicity"])

    def test_ach_matrix_manual_verification(self):
        """Test ACH evaluation with 4 hypotheses and 3 evidence items."""
        hypotheses = [
            {"id": "H1", "label": "Сервер упал из-за перегрузки ЦПУ"},
            {"id": "H2", "label": "Сервер упал из-за утечки памяти"},
            {"id": "H3", "label": "Сервер упал из-за сбоя сети"},
            {"id": "H4", "label": "Сервер не падал"}
        ]
        evidence = [
            {"id": "E1", "statement": "Мониторинг зафиксировал 100% загрузку ЦПУ перед сбоем.", "confidence": 0.9},
            {"id": "E2", "statement": "Память находилась в норме и не испытывала утечки.", "confidence": 0.95},
            {"id": "E3", "statement": "Сеть работала стабильно без сбоев.", "confidence": 0.8}
        ]
        ach_res = evaluate_ach_hypotheses(hypotheses, evidence)

        # E2 has "не испытывала" and mentions "памяти", contradicting H2 ("утечки памяти").
        # E3 has "без сбоев" and mentions "сеть", contradicting H3 ("сбоя сети").
        # E2 & E3 contradict H4 ("не падал"? E2 has "не", H4 has "не" -> same polarity for "не", but let's check ratings).
        scores = ach_res["inconsistency_scores"]
        ranked = ach_res["ranked_hypotheses"]

        # H1 should have lowest inconsistency score (0.0), so H1 is ACCEPTED
        self.assertEqual(ranked[0]["hypothesis_id"], "H1")
        self.assertEqual(ranked[0]["ach_status"], "ACCEPTED")
        self.assertEqual(scores["H1"], 0.0)

        # H2 should have inconsistency score > 0 (E2 contradicted it with conf 0.95)
        self.assertGreater(scores["H2"], 0.0)

    def test_dag_acyclicity_prevents_cycles(self):
        """Verify that CAUSES edges enforce DAG acyclicity when potential cycles exist."""
        theses = [
            ThesisNode(id="T1", name="Узел 1", statement="Фактор 1 вызывает Фактор 2"),
            ThesisNode(id="T2", name="Узел 2", statement="Фактор 2 вызывает Фактор 3"),
            ThesisNode(id="T3", name="Узел 3", statement="Фактор 3 вызывает Фактор 1")
        ]
        causes, requires, contradicts, belongs = self.extractor.extract_graph_edges(theses, [], scene_id="s_cycle")
        
        # Verify no cycle T1 -> T2 -> T3 -> T1 was formed in causes
        adj = {}
        for edge in causes:
            src, dst = edge["source_id"], edge["target_id"]
            adj.setdefault(src, set()).add(dst)

        def has_cycle(node, visited, rec_stack):
            visited.add(node)
            rec_stack.add(node)
            for neighbor in adj.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor, visited, rec_stack):
                        return True
                elif neighbor in rec_stack:
                    return True
            rec_stack.remove(node)
            return False

        visited = set()
        rec_stack = set()
        cycle_found = False
        for n in list(adj.keys()):
            if n not in visited:
                if has_cycle(n, visited, rec_stack):
                    cycle_found = True
                    break

        self.assertFalse(cycle_found, "CAUSES edges must maintain DAG acyclicity without cycles")

if __name__ == "__main__":
    unittest.main()
