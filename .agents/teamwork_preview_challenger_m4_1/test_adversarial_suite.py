"""
Adversarial Stress Test Suite for Cognitive Tutor Engine (R4)
Executed by Challenger 1 in working directory.
"""

import os
import sys
import unittest
import tempfile
import sqlite3
import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, r"C:\vazus")

from vazus_core.cognitive_tutor_engine import (
    calculate_sm2_update,
    map_score_to_q,
    extract_keywords,
    generate_active_recall_question,
    generate_all_questions_for_entity,
    ResponseEvaluator,
    evaluate_answer,
    parse_zettel_markdown,
    CognitiveTutorEngine
)


class TestCognitiveTutorAdversarial(unittest.TestCase):

    def test_sm2_edge_cases(self):
        # 1. Extreme Q ratings below 0 and above 5
        n, ef, i = calculate_sm2_update(1, 2.5, 1.0, -10)
        self.assertEqual(n, 0)
        self.assertEqual(i, 1.0)
        self.assertGreaterEqual(ef, 1.3)

        n, ef, i = calculate_sm2_update(1, 2.5, 1.0, 100)
        self.assertEqual(n, 2)
        self.assertGreaterEqual(ef, 1.3)

        # 2. Negative inputs for reps, ef, interval
        n, ef, i = calculate_sm2_update(-5, -2.0, -10.0, 4)
        self.assertEqual(n, 1)
        self.assertEqual(ef, 1.3)  # Clamped to 1.3
        self.assertEqual(i, 1.0)

        # 3. High repetitions transition: n > 4 uses cur_i * new_ef
        n, ef, i = calculate_sm2_update(4, 2.5, 21.0, 5)
        self.assertEqual(n, 5)
        # EF for Q=5: 2.5 + (0.1 - 0) = 2.6
        # interval: round(21.0 * 2.6) = 55.0
        self.assertEqual(i, 55.0)

    def test_question_generator_empty_and_malformed(self):
        # 1. Non-dict entity
        q = generate_active_recall_question("Just a plain string statement")
        self.assertIn("question_text", q)
        self.assertIn("target_answer", q)

        # 2. Protocol node with non-list steps and empty prereqs
        proto = {
            "node_type": "ProtocolNode",
            "name": "Bad Protocol",
            "steps": "Step 1; Step 2; Step 3",
            "prerequisites": None,
            "safety_warnings": []
        }
        q_proto = generate_active_recall_question(proto)
        self.assertEqual(q_proto["question_type"], "SEQUENCE_ORDERING")
        self.assertIn("Step 1 -> Step 2 -> Step 3", q_proto["target_answer"])

        # 3. Thesis node with short/no statement
        thesis = {"node_type": "ThesisNode", "statement": ""}
        q_thesis = generate_active_recall_question(thesis)
        self.assertEqual(q_thesis["question_type"], "CONCEPT_EXPLANATION")

    def test_response_evaluator_adversarial(self):
        evaluator = ResponseEvaluator()

        # 1. None / empty user response
        res = evaluator.evaluate_response(None, "Expected answer")
        self.assertEqual(res["score_percent"], 0.0)
        self.assertEqual(res["q_rating"], 0)

        # 2. Whitespace user response
        res = evaluator.evaluate_response("   \n\t  ", "Expected answer")
        self.assertEqual(res["score_percent"], 0.0)

        # 3. Exact match
        res = evaluator.evaluate_response("Expected answer", "Expected answer")
        self.assertEqual(res["score_percent"], 100.0)
        self.assertEqual(res["q_rating"], 5)

        # 4. Cyrillic and unicode input
        res = evaluator.evaluate_response("Алгоритм распределенного консенсуса", "Алгоритм распределенного консенсуса")
        self.assertEqual(res["score_percent"], 100.0)

    def test_sqlite_engine_temp(self):
        import gc
        with tempfile.TemporaryDirectory() as tmpdir:
            db_file = os.path.join(tmpdir, "nested", "dir", "test_tutor.db")
            engine = CognitiveTutorEngine(db_path=db_file)

            # Check directory auto-creation
            self.assertTrue(os.path.exists(db_file))

            # Test card saving and retrieval
            card_data = {
                "entity_id": "ent_123",
                "entity_type": "ThesisNode",
                "question_type": "CONCEPT_EXPLANATION",
                "question_text": "What is SuperGraph?",
                "target_answer": "Unified two-layer graph architecture."
            }
            cid = engine.save_card(card_data)
            card = engine.get_card(cid)
            self.assertIsNotNone(card)
            self.assertEqual(card["entity_id"], "ent_123")

            # Check view aliases kg_flashcards and kg_review_logs
            with sqlite3.connect(db_file) as conn:
                row = conn.execute("SELECT COUNT(*) FROM kg_flashcards").fetchone()
                self.assertEqual(row[0], 1)

            # Test processing review
            rev = engine.process_review(cid, "Unified two-layer graph architecture.")
            self.assertEqual(rev["q_rating"], 5)

            with sqlite3.connect(db_file) as conn:
                row = conn.execute("SELECT COUNT(*) FROM kg_review_logs").fetchone()
                self.assertEqual(row[0], 1)

            gc.collect()



if __name__ == "__main__":
    unittest.main()
