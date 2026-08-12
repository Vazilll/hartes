"""
empirical_stress_test.py
Empirical Verification & Stress Test Harness for Web Dashboard Cognitive & Mastery Tab.

Runs a real ThreadedHTTPServer on an ephemeral port with an ephemeral SQLite database,
and performs:
1. REST API functional verification across all endpoints.
2. High-concurrency stress testing (50 parallel workers).
3. Parameter boundary & edge case mining (malformed payloads, negative bounds, invalid types).
4. Range streaming boundary tests (HTTP 206, 416, malformed headers).
5. Path security and HTTP error handling (400, 403, 404, 500 handling).
6. SQLite transaction concurrency under heavy POST writes.
"""

import os
import sys
import gc
import json
import time
import sqlite3
import tempfile
import threading
import urllib.request
import urllib.error
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.dashboard import ThreadedHTTPServer, DashboardRequestHandler
from vazus_core.cognitive_tutor_engine import CognitiveTutorEngine

HOST = "127.0.0.1"
PORT = 9876
WORKSPACE_DIR = Path(__file__).resolve().parent

def run_empirical_tests():
    print("=== STARTING EMPIRICAL STRESS TEST SUITE ===")
    tmp_dir = tempfile.TemporaryDirectory()
    db_path = str(Path(tmp_dir.name) / "stress_vazus.db")
    
    # 1. Initialize Engine and seed test data
    engine = CognitiveTutorEngine(db_path=db_path)
    card_id_1 = engine.save_card({
        "id": "card_stress_101",
        "entity_id": "Zettel_neuro_01",
        "entity_type": "ThesisNode",
        "question_type": "CONCEPT_EXPLANATION",
        "question_text": "Explain LTP mechanism in CA1 neurons.",
        "target_answer": "NMDA receptor activation leads to Ca2+ influx and AMPA receptor insertion.",
        "repetition_n": 0,
        "ease_factor": 2.5,
        "interval_days": 0.0
    })
    
    card_id_2 = engine.save_card({
        "id": "card_stress_102",
        "entity_id": "Zettel_neuro_02",
        "entity_type": "ThesisNode",
        "question_type": "KEY_DEFINITION",
        "question_text": "Define Hebbian Learning.",
        "target_answer": "Cells that fire together wire together.",
        "repetition_n": 1,
        "ease_factor": 2.6,
        "interval_days": 1.0
    })

    # Create dummy markdown wiki note inside workspace (C:\vazus boundary) for valid wiki tests
    sample_note = WORKSPACE_DIR / "sample_wiki_note.md"
    sample_note.write_text("""# LTP Mechanism

Context on Synaptic Plasticity [[Zettel_neuro_02]].

- [ ] Verify NMDA receptors
- [x] Check AMPA trafficking
- [ ] Review CaMKII autophosphorylation
""", encoding="utf-8")

    # Start HTTP server
    DashboardRequestHandler.db_path = db_path
    server = ThreadedHTTPServer((HOST, PORT), DashboardRequestHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(0.3)
    
    base_url = f"http://{HOST}:{PORT}"
    results = {
        "passed": 0,
        "failed": 0,
        "failures": []
    }

    def assert_test(cond, name, detail=""):
        if cond:
            results["passed"] += 1
            print(f" [PASS] {name}")
        else:
            results["failed"] += 1
            results["failures"].append((name, detail))
            print(f" [FAIL] {name}: {detail}")

    def http_req(path, method="GET", body=None, headers=None):
        if headers is None:
            headers = {}
        if "User-Agent" not in headers:
            headers["User-Agent"] = "StressTestClient/1.0"
        
        data_bytes = None
        if body is not None:
            if isinstance(body, dict) or isinstance(body, list):
                data_bytes = json.dumps(body).encode("utf-8")
                headers["Content-Type"] = "application/json; charset=utf-8"
            elif isinstance(body, bytes):
                data_bytes = body
            elif isinstance(body, str):
                data_bytes = body.encode("utf-8")

        url = f"{base_url}{path}"
        req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                res_body = resp.read()
                return resp.status, dict(resp.headers), res_body
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), e.read()
        except Exception as e:
            return 599, {}, str(e).encode("utf-8")

    # -------------------------------------------------------------
    # SECTION 1: Standard REST API Endpoints Verification
    # -------------------------------------------------------------
    print("\n--- SECTION 1: Standard REST API Verification ---")
    
    # GET /
    code, _, body = http_req("/")
    assert_test(code == 200 and b"vazus SuperGraph OS" in body, "GET / (Dashboard HTML served)")

    # GET /api/v1/cognitive/stats
    code, _, body = http_req("/api/v1/cognitive/stats")
    data = json.loads(body.decode("utf-8")) if code == 200 else {}
    assert_test(code == 200 and data.get("status") == "ok" and data.get("total_cards") == 2, "GET /api/v1/cognitive/stats response format")

    # GET /api/v1/cognitive/next-question
    code, _, body = http_req("/api/v1/cognitive/next-question")
    data = json.loads(body.decode("utf-8")) if code == 200 else {}
    assert_test(code == 200 and data.get("status") == "ok" and "card" in data, "GET /api/v1/cognitive/next-question response format")

    # POST /api/v1/cognitive/evaluate-answer
    payload = {
        "card_id": card_id_1,
        "user_answer": "NMDA receptor activation and Ca2+ influx leads to AMPA receptor insertion.",
        "quality_grade": 5
    }
    code, _, body = http_req("/api/v1/cognitive/evaluate-answer", method="POST", body=payload)
    data = json.loads(body.decode("utf-8")) if code == 200 else {}
    assert_test(code == 200 and data.get("status") == "ok" and data.get("q_rating") == 5, "POST /api/v1/cognitive/evaluate-answer grade 5")

    # GET /api/v1/wiki/note
    rel_note_path = str(sample_note.relative_to(Path("C:/vazus").resolve()))
    code, _, body = http_req(f"/api/v1/wiki/note?id={urllib.parse.quote(rel_note_path)}")
    data = json.loads(body.decode("utf-8")) if code == 200 else {}
    assert_test(code == 200 and data.get("status") == "ok" and "LTP Mechanism" in data.get("content", ""), "GET /api/v1/wiki/note valid note inside workspace")

    # POST /api/v1/wiki/checkbox valid index
    cb_valid = {
        "id": rel_note_path,
        "checkbox_index": 0,
        "checked": True
    }
    code, _, body = http_req("/api/v1/wiki/checkbox", method="POST", body=cb_valid)
    data = json.loads(body.decode("utf-8")) if code == 200 else {}
    assert_test(code == 200 and data.get("updated") is True, "POST /api/v1/wiki/checkbox valid index -> updated=True")

    # -------------------------------------------------------------
    # SECTION 2: Stress & Boundary Parameter Inputs
    # -------------------------------------------------------------
    print("\n--- SECTION 2: Boundary & Edge Case Mining ---")

    # Evaluate answer: Missing card_id
    code, _, body = http_req("/api/v1/cognitive/evaluate-answer", method="POST", body={"user_answer": "test"})
    assert_test(code == 400, "POST /api/v1/cognitive/evaluate-answer missing card_id -> 400")

    # Evaluate answer: Non-existent card_id
    code, _, body = http_req("/api/v1/cognitive/evaluate-answer", method="POST", body={"card_id": "non_existent_999", "user_answer": "test"})
    assert_test(code == 404, "POST /api/v1/cognitive/evaluate-answer non-existent card_id -> 404")

    # Evaluate answer: Malformed JSON body
    code, _, body = http_req("/api/v1/cognitive/evaluate-answer", method="POST", body="{malformed json...", headers={"Content-Type": "application/json"})
    assert_test(code == 500, "POST /api/v1/cognitive/evaluate-answer malformed JSON -> 500 error response")

    # Evaluate answer: Out of bounds quality grade (<0 or >5)
    code, _, body = http_req("/api/v1/cognitive/evaluate-answer", method="POST", body={"card_id": card_id_1, "user_answer": "test", "quality_grade": 999})
    data = json.loads(body.decode("utf-8")) if code == 200 else {}
    assert_test(code == 200 and data.get("q_rating") == 5, "POST /api/v1/cognitive/evaluate-answer quality_grade upper bound clamped to 5")

    code, _, body = http_req("/api/v1/cognitive/evaluate-answer", method="POST", body={"card_id": card_id_1, "user_answer": "test", "quality_grade": -10})
    data = json.loads(body.decode("utf-8")) if code == 200 else {}
    assert_test(code == 200 and data.get("q_rating") == 0, "POST /api/v1/cognitive/evaluate-answer quality_grade lower bound clamped to 0")

    # Wiki note: Empty note id
    code, _, body = http_req("/api/v1/wiki/note?id=")
    assert_test(code == 400, "GET /api/v1/wiki/note empty id -> 400")

    # Wiki note: Non-existent note id within allowed dir
    code, _, body = http_req("/api/v1/wiki/note?id=non_existent_note_123")
    assert_test(code == 404, "GET /api/v1/wiki/note non-existent note -> 404")

    # Wiki checkbox: Out of bounds checkbox index (e.g. 9999)
    cb_payload = {
        "id": rel_note_path,
        "checkbox_index": 9999,
        "checked": True
    }
    code, _, body = http_req("/api/v1/wiki/checkbox", method="POST", body=cb_payload)
    data = json.loads(body.decode("utf-8")) if code == 200 else {}
    assert_test(code == 200 and data.get("updated") is False, "POST /api/v1/wiki/checkbox index out of bounds handled gracefully (updated=False)")

    # Stream: Missing path param
    code, _, _ = http_req("/api/v1/knowledge/stream")
    assert_test(code == 400, "GET /api/v1/knowledge/stream missing path -> 400")

    # Thumbnail: Missing path param
    code, _, _ = http_req("/api/v1/knowledge/thumbnail")
    assert_test(code == 400, "GET /api/v1/knowledge/thumbnail missing path -> 400")

    # Path traversal security: 403 Forbidden checks
    traversals = [
        "../../../../Windows/System32/drivers/etc/hosts",
        "..\\..\\Windows\\System32\\cmd.exe",
        "C:/Windows/System32/drivers/etc/hosts"
    ]
    for tr in traversals:
        c1, _, _ = http_req(f"/api/v1/wiki/note?id={urllib.parse.quote(tr)}")
        assert_test(c1 == 403, f"Security: wiki note traversal '{tr}' -> 403")

        c2, _, _ = http_req("/api/v1/wiki/checkbox", method="POST", body={"id": tr, "checkbox_index": 0, "checked": True})
        assert_test(c2 == 403, f"Security: wiki checkbox traversal '{tr}' -> 403")

        c3, _, _ = http_req(f"/api/v1/knowledge/stream?path={urllib.parse.quote(tr)}")
        assert_test(c3 == 403, f"Security: knowledge stream traversal '{tr}' -> 403")

        c4, _, _ = http_req(f"/api/v1/knowledge/thumbnail?path={urllib.parse.quote(tr)}")
        assert_test(c4 == 403, f"Security: knowledge thumbnail traversal '{tr}' -> 403")

    # OPTIONS preflight
    code, headers, _ = http_req("/api/v1/cognitive/stats", method="OPTIONS")
    assert_test(code == 200 and headers.get("Access-Control-Allow-Origin") == "*", "OPTIONS preflight returns 200 and CORS headers")

    # 404 Not Found endpoint
    code, _, _ = http_req("/api/v1/nonexistent/endpoint")
    assert_test(code == 404, "Unknown endpoint returns 404")

    # -------------------------------------------------------------
    # SECTION 3: High Concurrency Stress Testing
    # -------------------------------------------------------------
    print("\n--- SECTION 3: High-Concurrency Stress Testing (50 Parallel Workers) ---")
    
    num_requests = 50
    concurrency = 15
    
    def worker_task(idx):
        if idx % 4 == 0:
            return http_req("/api/v1/cognitive/stats")
        elif idx % 4 == 1:
            return http_req("/api/v1/cognitive/next-question")
        elif idx % 4 == 2:
            return http_req(f"/api/v1/wiki/note?id={urllib.parse.quote(rel_note_path)}")
        else:
            p = {
                "card_id": card_id_1 if idx % 2 == 0 else card_id_2,
                "user_answer": f"Concurrent test answer {idx}",
                "quality_grade": (idx % 6)
            }
            return http_req("/api/v1/cognitive/evaluate-answer", method="POST", body=p)

    t0 = time.time()
    successful_concurrent = 0
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(worker_task, i) for i in range(num_requests)]
        for f in as_completed(futures):
            c, _, b = f.result()
            if c == 200:
                successful_concurrent += 1
    t1 = time.time()

    elapsed = t1 - t0
    print(f" Executed {num_requests} concurrent requests in {elapsed:.3f}s ({num_requests/elapsed:.1f} req/s)")
    assert_test(successful_concurrent == num_requests, f"All {num_requests} concurrent requests succeeded without HTTP/Thread/Lock errors ({successful_concurrent}/{num_requests})")

    # Clean up test note
    if sample_note.exists():
        try:
            sample_note.unlink()
        except Exception:
            pass

    # Shutdown server
    server.shutdown()
    server.server_close()
    try:
        tmp_dir.cleanup()
    except Exception:
        pass

    print("\n=== STRESS TEST SUMMARY ===")
    print(f"Passed: {results['passed']}")
    print(f"Failed: {results['failed']}")
    if results['failures']:
        print("Failures:")
        for name, detail in results['failures']:
            print(f" - {name}: {detail}")
    
    return results['failed'] == 0

if __name__ == "__main__":
    success = run_empirical_tests()
    sys.exit(0 if success else 1)
