"""
tests/test_cognitive_tutor_engine.py
Unit test suite for Active Learning SM-2 Spaced Repetition Engine and CLI Runner.
"""

import os
import sys
import unittest
import tempfile
import subprocess
from pathlib import Path

# Add workspace root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from vazus_core.cognitive_tutor_engine import (
    CognitiveTutorEngine,
    calculate_sm2_update,
    generate_active_recall_question,
    generate_all_questions_for_entity,
    evaluate_answer,
    map_score_to_q,
    parse_zettel_markdown,
    extract_keywords
)


class TestSM2Algorithm(unittest.TestCase):
    """Tests SuperMemo SM-2 mathematical correctness and boundary handling."""

    def test_map_score_to_q(self):
        self.assertEqual(map_score_to_q(95.0), 5)
        self.assertEqual(map_score_to_q(90.0), 5)
        self.assertEqual(map_score_to_q(85.0), 4)
        self.assertEqual(map_score_to_q(80.0), 4)
        self.assertEqual(map_score_to_q(70.0), 3)
        self.assertEqual(map_score_to_q(65.0), 3)
        self.assertEqual(map_score_to_q(55.0), 2)
        self.assertEqual(map_score_to_q(50.0), 2)
        self.assertEqual(map_score_to_q(40.0), 1)
        self.assertEqual(map_score_to_q(30.0), 1)
        self.assertEqual(map_score_to_q(20.0), 0)
        self.assertEqual(map_score_to_q(0.0), 0)

    def test_sm2_update_successful_milestones(self):
        # Initial review: n=0, EF=2.5, I=0, Q=5
        n, ef, i = calculate_sm2_update(0, 2.5, 0.0, 5)
        self.assertEqual(n, 1)
        self.assertAlmostEqual(ef, 2.6, places=2)
        self.assertEqual(i, 1.0)

        # 2nd review: n=1, EF=2.6, I=1.0, Q=4
        n, ef, i = calculate_sm2_update(n, ef, i, 4)
        self.assertEqual(n, 2)
        self.assertAlmostEqual(ef, 2.6, places=2)
        self.assertEqual(i, 3.0)

        # 3rd review: n=2, EF=2.6, I=3.0, Q=4
        n, ef, i = calculate_sm2_update(n, ef, i, 4)
        self.assertEqual(n, 3)
        self.assertAlmostEqual(ef, 2.6, places=2)
        self.assertEqual(i, 7.0)

        # 4th review: n=3, EF=2.6, I=7.0, Q=4
        n, ef, i = calculate_sm2_update(n, ef, i, 4)
        self.assertEqual(n, 4)
        self.assertAlmostEqual(ef, 2.6, places=2)
        self.assertEqual(i, 21.0)

        # 5th review (exponential): n=4, EF=2.6, I=21.0, Q=4 -> I = round(21 * 2.6) = 55.0
        n, ef, i = calculate_sm2_update(n, ef, i, 4)
        self.assertEqual(n, 5)
        self.assertAlmostEqual(ef, 2.6, places=2)
        self.assertEqual(i, 55.0)

    def test_sm2_update_lapses(self):
        # Failed review Q=1 resets n=0, interval=1.0 day
        n, ef, i = calculate_sm2_update(5, 2.6, 55.0, 1)
        self.assertEqual(n, 0)
        self.assertEqual(i, 1.0)
        self.assertTrue(ef < 2.6)

    def test_ease_factor_lower_bound(self):
        # Repeated failures Q=0 should clamp EF to minimum 1.3
        cur_ef = 1.4
        for _ in range(10):
            _, cur_ef, _ = calculate_sm2_update(0, cur_ef, 1.0, 0)
        self.assertEqual(cur_ef, 1.3)


class TestSocraticQuestionGenerator(unittest.TestCase):
    """Tests active recall question generation from ThesisNode, ProtocolNode, and Zettel notes."""

    def test_thesis_node_question(self):
        thesis = {
            "id": "thesis_sm2",
            "node_type": "ThesisNode",
            "name": "SuperMemo Algorithm",
            "statement": "SuperMemo SM-2 optimizes spaced repetition intervals to prevent memory decay."
        }
        q = generate_active_recall_question(thesis)
        self.assertEqual(q["entity_id"], "thesis_sm2")
        self.assertIn(q["question_type"], ("FILL_IN_BLANK", "CONCEPT_EXPLANATION"))
        self.assertTrue(len(q["question_text"]) > 0)
        self.assertTrue(len(q["target_answer"]) > 0)

    def test_protocol_node_question(self):
        protocol = {
            "id": "protocol_m4",
            "node_type": "ProtocolNode",
            "name": "Active Recall Testing Protocol",
            "prerequisites": ["Python venv active", "SQLite database writable"],
            "steps": ["Step 1: Present prompt", "Step 2: Collect user answer", "Step 3: Update SM-2 state"],
            "safety_warnings": ["Do not bypass verification checks"]
        }
        q = generate_active_recall_question(protocol)
        self.assertEqual(q["entity_id"], "protocol_m4")
        self.assertIn(q["question_type"], ("PREREQUISITE_CHECK", "SEQUENCE_ORDERING", "SAFETY_WARNING"))
        self.assertTrue(len(q["target_answer"]) > 0)

    def test_zettel_note_question(self):
        zettel = {
            "id": "Zettel_001",
            "node_type": "ZettelNote",
            "title": "Spaced Repetition Memory",
            "core_claim": "Active recall combined with spaced repetition consolidates long term memory.",
            "wikilinks": ["MemoryDecay", "SocraticTutor"]
        }
        q = generate_active_recall_question(zettel)
        self.assertEqual(q["question_type"], "WIKILINK_SYNTHESIS")
        self.assertIn("MemoryDecay", q["question_text"])


class TestResponseEvaluator(unittest.TestCase):
    """Tests 768D hybrid response evaluation engine."""

    def test_evaluate_perfect_answer(self):
        question = {
            "target_answer": "SuperMemo SM-2 optimizes spaced repetition intervals.",
            "repetition_n": 0,
            "ease_factor": 2.5,
            "interval_days": 0.0
        }
        user_ans = "SuperMemo SM-2 optimizes spaced repetition intervals."
        res = evaluate_answer(question, user_ans)
        self.assertGreaterEqual(res["score_percent"], 90.0)
        self.assertEqual(res["q_rating"], 5)
        self.assertIn("sm2_update", res)
        self.assertEqual(res["sm2_update"]["repetition_n"], 1)

    def test_evaluate_imperfect_answer(self):
        question = {
            "target_answer": "SuperMemo SM-2 optimizes spaced repetition intervals.",
            "repetition_n": 1,
            "ease_factor": 2.6,
            "interval_days": 1.0
        }
        user_ans = "SuperMemo algorithm adjusts repetition intervals for memory."
        res = evaluate_answer(question, user_ans)
        self.assertTrue(30.0 <= res["score_percent"] <= 100.0)
        self.assertTrue(1 <= res["q_rating"] <= 5)

    def test_evaluate_wrong_answer(self):
        question = {
            "target_answer": "SuperMemo SM-2 optimizes spaced repetition intervals.",
            "repetition_n": 2,
            "ease_factor": 2.6,
            "interval_days": 3.0
        }
        user_ans = "Unrelated banana apples soup"
        res = evaluate_answer(question, user_ans)
        self.assertLess(res["score_percent"], 50.0)
        self.assertLessEqual(res["q_rating"], 2)
        self.assertEqual(res["sm2_update"]["repetition_n"], 0)


class TestCognitiveTutorEnginePersistence(unittest.TestCase):
    """Tests SQLite persistence for tutor_cards, tutor_reviews, and stats."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp_db.close()
        self.db_path = self.tmp_db.name
        self.engine = CognitiveTutorEngine(db_path=self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except OSError:
                pass

    def test_card_creation_and_due_query(self):
        thesis = {
            "id": "thesis_db_test",
            "node_type": "ThesisNode",
            "name": "Database Persistence",
            "statement": "SQLite stores tutor cards and review logs for long-term tracking."
        }
        card_ids = self.engine.create_cards_from_entity(thesis)
        self.assertTrue(len(card_ids) > 0)

        due = self.engine.get_due_cards()
        self.assertTrue(len(due) > 0)
        self.assertEqual(due[0]["id"], card_ids[0])

    def test_process_review_and_stats(self):
        thesis = {
            "id": "thesis_review_test",
            "node_type": "ThesisNode",
            "name": "Review Processing",
            "statement": "Review processing updates SM-2 state in SQLite."
        }
        card_ids = self.engine.create_cards_from_entity(thesis)
        cid = card_ids[0]
        card_obj = self.engine.get_card(cid)
        target_ans = card_obj["target_answer"]
        review_res = self.engine.process_review(cid, target_ans, response_time_sec=3.0)
        self.assertEqual(review_res["q_rating"], 5)
        self.assertEqual(review_res["sm2_update"]["repetition_n"], 1)

        updated_card = self.engine.get_card(cid)
        self.assertEqual(updated_card["repetition_n"], 1)
        self.assertAlmostEqual(updated_card["ease_factor"], 2.6, places=2)

        stats = self.engine.get_mastery_stats()
        self.assertEqual(stats["total_cards"], len(card_ids))
        self.assertEqual(stats["total_reviews"], 1)
        self.assertGreater(stats["average_score_percent"], 80.0)


class TestCLIRunner(unittest.TestCase):
    """Tests personal_tutor.py CLI runner with --test flag."""

    def test_cli_test_flag(self):
        cli_script = PROJECT_ROOT / "scripts" / "personal_tutor.py"
        res = subprocess.run([sys.executable, str(cli_script), "--test"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"CLI --test failed with stderr: {res.stderr}\nstdout: {res.stdout}")
        self.assertIn("[SELF-TEST PASSED]", res.stdout)


if __name__ == "__main__":
    unittest.main()
