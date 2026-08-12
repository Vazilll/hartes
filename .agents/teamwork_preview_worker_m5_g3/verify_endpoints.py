import json
import time
import tempfile
import threading
import urllib.request
import urllib.error
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.dashboard import ThreadedHTTPServer, DashboardRequestHandler
from vazus_core.cognitive_tutor_engine import CognitiveTutorEngine

def run_verification():
    tmp_dir = tempfile.TemporaryDirectory()
    db_path = str(Path(tmp_dir.name) / "test_verify.db")
    
    engine = CognitiveTutorEngine(db_path=db_path)
    card_id = engine.save_card({
        "id": "card_test_verify_001",
        "entity_id": "Zettel_thesis_review_test_99",
        "entity_type": "ThesisNode",
        "question_type": "CONCEPT_EXPLANATION",
        "question_text": "What is the primary mechanism of neuroplasticity in hippocampus?",
        "target_answer": "BDNF expression increase via aerobic exercise and nootropics.",
        "repetition_n": 0,
        "ease_factor": 2.5,
        "interval_days": 0.0
    })

    DashboardRequestHandler.db_path = db_path
    server = ThreadedHTTPServer(("127.0.0.1", 9599), DashboardRequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.3)

    results = {}

    try:
        # 1. GET /api/v1/cognitive/stats
        url = "http://127.0.0.1:9599/api/v1/cognitive/stats"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            results["stats"] = {
                "status": resp.status,
                "content_type": resp.headers.get("Content-Type"),
                "body": json.loads(resp.read().decode("utf-8"))
            }

        # 2. GET /api/v1/cognitive/next-question
        url = "http://127.0.0.1:9599/api/v1/cognitive/next-question"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            results["next_question"] = {
                "status": resp.status,
                "content_type": resp.headers.get("Content-Type"),
                "body": json.loads(resp.read().decode("utf-8"))
            }

        # 3. POST /api/v1/cognitive/evaluate-answer
        url = "http://127.0.0.1:9599/api/v1/cognitive/evaluate-answer"
        payload = json.dumps({
            "card_id": card_id,
            "user_answer": "BDNF expression increases via aerobic exercise and nootropics.",
            "quality_grade": 4
        }).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req) as resp:
            results["evaluate_answer"] = {
                "status": resp.status,
                "content_type": resp.headers.get("Content-Type"),
                "body": json.loads(resp.read().decode("utf-8"))
            }

        # 4. GET /api/v1/wiki/note
        url = "http://127.0.0.1:9599/api/v1/wiki/note?id=Zettel_thesis_review_test_99"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            results["wiki_note"] = {
                "status": resp.status,
                "content_type": resp.headers.get("Content-Type"),
                "body": json.loads(resp.read().decode("utf-8"))
            }

        # 5. POST /api/v1/wiki/checkbox
        url = "http://127.0.0.1:9599/api/v1/wiki/checkbox"
        payload = json.dumps({
            "id": "Zettel_thesis_review_test_99",
            "checkbox_index": 0,
            "checked": True
        }).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req) as resp:
            results["wiki_checkbox"] = {
                "status": resp.status,
                "content_type": resp.headers.get("Content-Type"),
                "body": json.loads(resp.read().decode("utf-8"))
            }

        print(json.dumps(results, indent=2))

    finally:
        server.shutdown()
        server.server_close()
        try:
            tmp_dir.cleanup()
        except Exception:
            pass

if __name__ == "__main__":
    run_verification()
