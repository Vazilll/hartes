"""
tests/test_dashboard_cognitive_tab.py
Unit and Integration test suite for Web Dashboard Cognitive & Mastery Tab.

Verifies:
1. Server startup and HTML UI markup.
2. REST API Endpoints:
   - GET /api/v1/cognitive/stats
   - GET /api/v1/cognitive/next-question
   - POST /api/v1/cognitive/evaluate-answer
   - GET /api/v1/wiki/note
   - POST /api/v1/wiki/checkbox
3. Strict Path Boundary Security Enforcement (HTTP 403 Forbidden for path traversal).
"""

import os
import sys
import gc
import json
import time
import unittest
import tempfile
import threading
import urllib.request
import urllib.error
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from vazus_core.integrations.dashboard_server import ThreadedHTTPServer, DashboardRequestHandler
from vazus_core.integrations.cognitive_tutor_engine import CognitiveTutorEngine


class TestDashboardCognitiveTab(unittest.TestCase):
    """Test suite for Dashboard Cognitive & Mastery REST API and security."""

    @classmethod
    def setUpClass(cls):
        cls.tmp_dir = tempfile.TemporaryDirectory()
        cls.db_path = str(Path(cls.tmp_dir.name) / "test_vazus.db")
        
        # Initialize engine and seed default card
        cls.engine = CognitiveTutorEngine(db_path=cls.db_path)
        cls.sample_card_id = cls.engine.save_card({
            "id": "card_test_m5_999",
            "entity_id": "Zettel_thesis_review_test_99",
            "entity_type": "ThesisNode",
            "question_type": "CONCEPT_EXPLANATION",
            "question_text": "What is the primary mechanism of neuroplasticity in hippocampus?",
            "target_answer": "BDNF expression increase via aerobic exercise and nootropics.",
            "repetition_n": 0,
            "ease_factor": 2.5,
            "interval_days": 0.0
        })

        # Start background HTTP server
        DashboardRequestHandler.db_path = cls.db_path
        cls.host = "127.0.0.1"
        cls.server = ThreadedHTTPServer((cls.host, 0), DashboardRequestHandler)
        cls.port = cls.server.server_address[1]
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        time.sleep(0.3)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        gc.collect()
        time.sleep(0.1)
        try:
            cls.tmp_dir.cleanup()
        except Exception:
            pass

    def _get(self, path: str):
        url = f"http://{self.host}:{self.port}{path}"
        req = urllib.request.Request(url, headers={"User-Agent": "TestClient"})
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, dict(resp.headers), resp.read()
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), e.read()

    def _post(self, path: str, data: dict):
        url = f"http://{self.host}:{self.port}{path}"
        body = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": "TestClient"
            },
            method="POST"
        )
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, dict(resp.headers), resp.read()
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), e.read()

    def test_01_html_dashboard_markup(self):
        code, headers, body = self._get("/")
        self.assertEqual(code, 200)
        html_str = body.decode("utf-8")
        self.assertIn("vazus SuperGraph OS", html_str)
        self.assertIn("main-tab-bar", html_str)
        self.assertIn("switchMainTab", html_str)
        self.assertIn("view-cognitive", html_str)
        self.assertIn("mastery-progress-bar", html_str)
        self.assertIn("user-answer-input", html_str)
        self.assertIn("score-gauge-val", html_str)
        self.assertIn("quality-grade-selector", html_str)
        self.assertIn("note-render-area", html_str)
        self.assertIn("wikilink-badge", html_str)

    def test_02_cognitive_stats_endpoint(self):
        code, headers, body = self._get("/api/v1/cognitive/stats")
        self.assertEqual(code, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data.get("status"), "ok")
        self.assertIn("total_cards", data)
        self.assertIn("due_cards", data)
        self.assertIn("mastered_cards", data)
        self.assertIn("learning_cards", data)
        self.assertIn("average_score_percent", data)
        self.assertIn("retention_pct", data)
        self.assertIn("mastery_score_pct", data)
        self.assertIn("mastery_level", data)

    def test_03_cognitive_next_question_endpoint(self):
        code, headers, body = self._get("/api/v1/cognitive/next-question")
        self.assertEqual(code, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data.get("status"), "ok")
        self.assertIn("card", data)
        card = data["card"]
        self.assertIsNotNone(card)
        self.assertIn("question_text", card)
        self.assertIn("target_answer", card)

    def test_04_cognitive_evaluate_answer_endpoint(self):
        payload = {
            "card_id": self.sample_card_id,
            "user_answer": "BDNF expression increases via aerobic exercise and nootropics.",
            "quality_grade": 4
        }
        code, headers, body = self._post("/api/v1/cognitive/evaluate-answer", payload)
        self.assertEqual(code, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data.get("status"), "ok")
        self.assertEqual(data.get("card_id"), self.sample_card_id)
        self.assertIn("score_pct", data)
        self.assertGreaterEqual(data["score_pct"], 70.0)
        self.assertEqual(data.get("q_rating"), 4)
        self.assertIn("feedback_rationale", data)
        self.assertIn("new_ease_factor", data)
        self.assertIn("new_interval_days", data)

    def test_05_wiki_note_endpoint(self):
        code, headers, body = self._get("/api/v1/wiki/note?id=Zettel_thesis_review_test_99")
        self.assertEqual(code, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data.get("status"), "ok")
        self.assertIn("title", data)
        self.assertIn("content", data)
        self.assertIn("wikilinks", data)

    def test_06_wiki_checkbox_toggle_endpoint(self):
        payload = {
            "id": "Zettel_thesis_review_test_99",
            "checkbox_index": 0,
            "checked": True
        }
        code, headers, body = self._post("/api/v1/wiki/checkbox", payload)
        self.assertEqual(code, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data.get("status"), "ok")
        self.assertIn("updated", data)
        self.assertEqual(data.get("checkbox_index"), 0)
        self.assertEqual(data.get("checked"), True)

    def test_07_strict_path_boundary_security_wiki_note(self):
        traversal_paths = [
            "../../../../Windows/System32/drivers/etc/hosts",
            "../secret.txt",
            "..\\..\\Windows\\System32\\cmd.exe",
            "C:/Windows/System32/drivers/etc/hosts"
        ]
        for path_str in traversal_paths:
            code, headers, body = self._get(f"/api/v1/wiki/note?id={urllib.parse.quote(path_str)}")
            self.assertEqual(code, 403, f"Expected 403 Forbidden for path traversal '{path_str}', got {code}")

    def test_08_strict_path_boundary_security_wiki_checkbox(self):
        payload = {
            "id": "../secret.txt",
            "checkbox_index": 0,
            "checked": True
        }
        code, headers, body = self._post("/api/v1/wiki/checkbox", payload)
        self.assertEqual(code, 403, f"Expected 403 Forbidden for path traversal in checkbox, got {code}")

    def test_09_strict_path_boundary_security_stream_and_thumb(self):
        traversal = "../../../../Windows/System32/drivers/etc/hosts"
        code1, _, _ = self._get(f"/api/v1/knowledge/stream?path={urllib.parse.quote(traversal)}")
        self.assertEqual(code1, 403, f"Expected 403 Forbidden for stream traversal, got {code1}")

        code2, _, _ = self._get(f"/api/v1/knowledge/thumbnail?path={urllib.parse.quote(traversal)}")
        self.assertEqual(code2, 403, f"Expected 403 Forbidden for thumbnail traversal, got {code2}")


if __name__ == "__main__":
    unittest.main()
