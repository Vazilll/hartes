#!/usr/bin/env python3
"""
vazus.scripts.dashboard — Fast, Resilient Python Web Server for Multimodal Knowledge & Cognitive Mastery Dashboard.

Serves SPA frontend and REST APIs:
- GET / : dashboard.html
- GET /api/v1/knowledge/search?query=...&top_k=...&domain=...
- GET /api/v1/knowledge/stream?path=... (206 Partial Content Range streaming)
- GET /api/v1/knowledge/thumbnail?path=...
- GET /api/v1/knowledge/stats
- GET /api/v1/cognitive/stats
- GET /api/v1/cognitive/next-question
- POST /api/v1/cognitive/evaluate-answer
- GET /api/v1/wiki/note?id=...
- POST /api/v1/wiki/checkbox
"""

import argparse
import datetime
import json
import logging
import mimetypes
import re
import sqlite3
import sys
import urllib.parse
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from socketserver import ThreadingMixIn
from typing import Optional, Any

logger = logging.getLogger(__name__)

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from vazus_core.embeddings import UnifiedEmbeddingManager
except ImportError:
    UnifiedEmbeddingManager = None

from vazus_core.paths import DEFAULT_DB_PATH as CANONICAL_DB_PATH, VAZUS_ROOT, PROJECTS_DIR

DEFAULT_DB_PATH = str(CANONICAL_DB_PATH)
_CANDIDATE_HTML_PATHS = [
    PROJECTS_DIR / "dashboard.html",
    VAZUS_ROOT / "apps" / "dashboard.html",
    PROJECT_ROOT / "projects" / "dashboard.html",
    PROJECT_ROOT / "apps" / "dashboard.html",
]
DEFAULT_HTML_PATH = next((p for p in _CANDIDATE_HTML_PATHS if p.exists()), _CANDIDATE_HTML_PATHS[0])

# Threading HTTPServer for concurrent requests
class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class DashboardRequestHandler(BaseHTTPRequestHandler):
    db_path: str = DEFAULT_DB_PATH

    def log_message(self, format, *args):
        # Clean logging format
        sys.stderr.write(f"[Dashboard] {self.address_string()} - {format % args}\n")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query_params = urllib.parse.parse_qs(parsed_url.query)

        try:
            if path in ("/", "/dashboard.html", "/index.html"):
                self.handle_serve_html()
            elif path == "/favicon.ico":
                self.send_response(204)
                self.end_headers()
                return
            elif path in ("/api/health", "/healthz", "/health"):
                self.send_json_response({"status": "ok", "service": "vazus-supergraph-os", "timestamp": datetime.datetime.now().isoformat()})
            elif path == "/api/v1/system/overview":
                self.handle_system_overview()
            elif path == "/api/v1/knowledge/insights":
                self.handle_knowledge_insights(query_params)
            elif path == "/api/v1/academic/debts":
                self.handle_academic_debts()
            elif path == "/api/v1/tools/catalog":
                self.handle_tools_catalog(query_params)
            elif path == "/api/v1/wiki/tree":
                self.handle_wiki_tree()
            elif path == "/api/v1/wiki/content":
                self.handle_wiki_content(query_params)
            elif path == "/api/v1/finance/summary":
                self.handle_finance_summary()
            elif path == "/api/v1/health/summary":
                self.handle_health_summary()
            elif path == "/api/v1/ai/status":
                self.handle_ai_status()
            elif path == "/api/v1/knowledge/search":
                self.handle_search(query_params)
            elif path == "/api/v1/knowledge/stream":
                self.handle_stream(query_params)
            elif path == "/api/v1/knowledge/thumbnail":
                self.handle_thumbnail(query_params)
            elif path == "/api/v1/knowledge/stats":
                self.handle_stats()
            elif path == "/api/v1/cognitive/stats":
                self.handle_cognitive_stats()
            elif path == "/api/v1/cognitive/next-question":
                self.handle_cognitive_next_question(query_params)
            elif path == "/api/v1/wiki/note":
                self.handle_wiki_note(query_params)
            elif path == "/api/v1/notebooklm/study-guides":
                self.handle_notebooklm_study_guides()
            elif path == "/api/v1/notebooklm/podcasts":
                self.handle_notebooklm_podcasts()
            else:
                self.send_error(404, "Endpoint Not Found")
        except Exception as e:
            sys.stderr.write(f"[Dashboard] GET Request Error: {e}\n")
            self.send_error(500, f"Internal Server Error: {str(e)}")

    def do_POST(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        try:
            if path == "/api/v1/security/verify":
                self.handle_security_verify()
            elif path == "/api/v1/cognitive/evaluate-answer":
                self.handle_cognitive_evaluate_answer()
            elif path == "/api/v1/wiki/checkbox":
                self.handle_wiki_checkbox()
            elif path == "/api/v1/notebooklm/generate-podcast":
                self.handle_notebooklm_generate_podcast()
            elif path == "/api/v1/notebooklm/generate-study-guide":
                self.handle_notebooklm_generate_study_guide()
            else:
                self.send_error(404, "Endpoint Not Found")
        except Exception as e:
            sys.stderr.write(f"[Dashboard] POST Request Error: {e}\n")
            self.send_json_response({"error": str(e)}, status=500)

    def handle_serve_html(self):
        if not DEFAULT_HTML_PATH.exists():
            self.send_error(404, f"HTML UI file not found at {DEFAULT_HTML_PATH}")
            return
        
        with open(DEFAULT_HTML_PATH, "rb") as f:
            content = f.read()

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(content)

    @staticmethod
    def _format_media_scene_item(r: dict, props: dict) -> dict:
        st = float(props.get("start_sec", 0.0))
        en = float(props.get("end_sec", 0.0))
        src_file = props.get("source_file", "")
        return {
            "title": r.get("name"),
            "start_sec": st,
            "end_sec": en,
            "duration": props.get("duration", round(en - st, 2)),
            "player_fragment": f"#t={st:.1f},{en:.1f}",
            "stream_url": f"/api/v1/knowledge/stream?path={urllib.parse.quote(src_file)}#t={st:.1f},{en:.1f}",
            "source_file": src_file,
            "thumbnail_path": props.get("thumbnail_path", ""),
            "thumbnail_url": f"/api/v1/knowledge/thumbnail?path={urllib.parse.quote(props.get('thumbnail_path', ''))}",
            "transcript": props.get("transcript") or r.get("description", ""),
            "media_type": props.get("media_type", "video"),
            "next_scene_id": props.get("next_scene_id"),
            "prev_scene_id": props.get("prev_scene_id"),
        }

    @staticmethod
    def _format_search_item(idx: int, r: dict) -> dict:
        node_type = r.get("node_type", "Unknown")
        props = r.get("properties", {}) or {}
        sim = r.get("similarity", 0.0)

        item = {
            "rank": idx,
            "id": r.get("id"),
            "name": r.get("name"),
            "node_type": node_type,
            "domain": r.get("domain"),
            "similarity": sim,
            "properties": props
        }
        if node_type == "MediaScene":
            item.update(DashboardRequestHandler._format_media_scene_item(r, props))
        elif node_type == "TelegramMessage":
            item.update({
                "msg_id": props.get("msg_id"),
                "channel_name": props.get("channel_name", ""),
                "timestamp": props.get("date", ""),
                "text_snippet": props.get("text") or r.get("description", ""),
                "referenced_media": props.get("referenced_media_files", []),
            })
        return item

    def handle_search(self, query_params):
        query = query_params.get("query", [""])[0].strip()
        top_k_str = query_params.get("top_k", ["5"])[0]
        domain = query_params.get("domain", [""])[0].strip()

        try:
            top_k = int(top_k_str)
        except ValueError:
            top_k = 5

        if not query:
            self.send_json_response({"results": [], "query": "", "count": 0})
            return

        embedder = UnifiedEmbeddingManager()
        raw_results = embedder.search_unified_vector_space(
            query=query,
            db_path=Path(self.db_path),
            top_k=top_k,
            domain_filter=domain if domain else None
        )

        formatted = [self._format_search_item(idx, r) for idx, r in enumerate(raw_results, 1)]
        self.send_json_response({"results": formatted, "query": query, "count": len(formatted)})

    def _resolve_media_stream_path(self, raw_path: str) -> tuple[Optional[Path], bool]:
        file_path = Path(urllib.parse.unquote(raw_path))
        allowed_base = Path("/home/tarhes/Проекты/vazus").resolve()
        try:
            resolved_path = file_path.resolve()
            resolved_path.relative_to(allowed_base)
        except Exception:
            return None, True
        if resolved_path.exists() and resolved_path.is_file():
            return resolved_path, False
        return None, False

    def _stream_range_response(self, resolved_path: Path, file_size: int, mime_type: str, range_header: str) -> None:
        byte_range = range_header.replace("bytes=", "").strip()
        parts = byte_range.split("-")
        start = int(parts[0]) if parts[0] else 0
        end = int(parts[1]) if parts[1] else file_size - 1

        if start >= file_size or end >= file_size or start > end:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{file_size}")
            self.end_headers()
            return

        chunk_size = end - start + 1
        self.send_response(206)
        self.send_header("Content-Type", mime_type)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
        self.send_header("Content-Length", str(chunk_size))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        with open(resolved_path, "rb") as f:
            f.seek(start)
            bytes_to_send = chunk_size
            buffer_size = 64 * 1024
            while bytes_to_send > 0:
                read_len = min(bytes_to_send, buffer_size)
                data = f.read(read_len)
                if not data:
                    break
                self.wfile.write(data)
                bytes_to_send -= len(data)

    def handle_stream(self, query_params):
        raw_path = query_params.get("path", [""])[0]
        if not raw_path:
            self.send_error(400, "Missing path parameter")
            return

        resolved_path, is_forbidden = self._resolve_media_stream_path(raw_path)
        if is_forbidden:
            self.send_error(403, "Access Denied: Path outside allowed workspace boundary")
            return
        if not resolved_path:
            self.send_error(404, f"Media file not found: {raw_path}")
            return

        file_size = resolved_path.stat().st_size
        mime_type, _ = mimetypes.guess_type(str(resolved_path))
        if not mime_type:
            ext = resolved_path.suffix.lower()
            mime_type = 'video/mp4' if ext in ('.mp4', '.m4v') else ('audio/mpeg' if ext == '.mp3' else 'application/octet-stream')

        range_header = self.headers.get("Range")
        if range_header and range_header.startswith("bytes="):
            self._stream_range_response(resolved_path, file_size, mime_type, range_header)
        else:
            self.send_response(200)
            self.send_header("Content-Type", mime_type)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(file_size))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            with open(resolved_path, "rb") as f:
                buffer_size = 64 * 1024
                while True:
                    data = f.read(buffer_size)
                    if not data:
                        break
                    self.wfile.write(data)

    def handle_thumbnail(self, query_params):
        raw_path = query_params.get("path", [""])[0]
        if not raw_path:
            self.send_error(400, "Missing path parameter")
            return

        clean_path = urllib.parse.unquote(raw_path)
        file_path = Path(clean_path)

        allowed_base = Path("/home/tarhes/Проекты/vazus").resolve()
        try:
            resolved_path = file_path.resolve()
            resolved_path.relative_to(allowed_base)
        except ValueError:
            self.send_error(403, "Access Denied: Path outside allowed workspace boundary")
            return
        except Exception:
            self.send_error(403, "Access Denied: Path outside allowed workspace boundary")
            return

        if not resolved_path.exists():
            default_thumb_dir = Path("/home/tarhes/Проекты/vazus/knowledge/.thumbnails")
            fallback_path = default_thumb_dir / file_path.name
            try:
                resolved_path = fallback_path.resolve()
                resolved_path.relative_to(allowed_base)
            except ValueError:
                self.send_error(403, "Access Denied: Path outside allowed workspace boundary")
                return
            except Exception:
                self.send_error(403, "Access Denied: Path outside allowed workspace boundary")
                return

        if not resolved_path.exists() or not resolved_path.is_file():
            self.send_error(404, f"Thumbnail image not found: {raw_path}")
            return

        with open(resolved_path, "rb") as f:
            content = f.read()

        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "public, max-age=86400")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(content)

    def handle_stats(self):
        db_p = Path(self.db_path)
        if not db_p.exists():
            self.send_json_response({"error": f"Database not found at {db_p}"}, status=404)
            return

        conn = sqlite3.connect(db_p)
        try:
            c = conn.cursor()
            total_nodes = c.execute("SELECT COUNT(*) FROM kg_nodes").fetchone()[0]
            total_edges = c.execute("SELECT COUNT(*) FROM kg_edges").fetchone()[0]

            ms_count = c.execute("SELECT COUNT(*) FROM kg_nodes WHERE node_type='MediaScene'").fetchone()[0]
            tm_count = c.execute("SELECT COUNT(*) FROM kg_nodes WHERE node_type='TelegramMessage'").fetchone()[0]
            emb_count = c.execute("SELECT COUNT(*) FROM kg_nodes WHERE embedding_json IS NOT NULL").fetchone()[0]

            stats = {
                "kg_nodes": total_nodes,
                "kg_edges": total_edges,
                "MediaScene": ms_count,
                "TelegramMessage": tm_count,
                "embedded_count": emb_count
            }
            self.send_json_response(stats)
        finally:
            conn.close()

    def handle_cognitive_stats(self):
        try:
            from vazus_core.integrations.cognitive_tutor_engine import CognitiveTutorEngine
            engine = CognitiveTutorEngine(db_path=self.db_path)
            stats = engine.get_mastery_stats()
            
            conn = sqlite3.connect(self.db_path)
            try:
                conn.row_factory = sqlite3.Row
                total_cards = conn.execute("SELECT COUNT(*) FROM tutor_cards").fetchone()[0]
                
                # Auto-sync notes if database is fresh/empty
                if total_cards == 0:
                    engine.sync_zettelkasten_notes()
                    stats = engine.get_mastery_stats()
                    total_cards = conn.execute("SELECT COUNT(*) FROM tutor_cards").fetchone()[0]

                mastered_cards = conn.execute("SELECT COUNT(*) FROM tutor_cards WHERE repetition_n >= 3 AND ease_factor >= 2.3").fetchone()[0]
                learning_cards = conn.execute("SELECT COUNT(*) FROM tutor_cards WHERE repetition_n < 3").fetchone()[0]
                
                now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
                due_cards = conn.execute("SELECT COUNT(*) FROM tutor_cards WHERE next_review_at IS NULL OR next_review_at <= ?", (now_str,)).fetchone()[0]
                
                ef_row = conn.execute("SELECT AVG(ease_factor) FROM tutor_cards").fetchone()
                avg_ef = round(ef_row[0], 2) if ef_row and ef_row[0] is not None else 2.50
                
                int_row = conn.execute("SELECT AVG(interval_days) FROM tutor_cards").fetchone()
                avg_interval = round(int_row[0], 1) if int_row and int_row[0] is not None else 1.0
            finally:
                conn.close()

            mastery_score_pct = round((mastered_cards / total_cards * 100.0), 1) if total_cards > 0 else 0.0
            
            if stats.get("total_reviews", 0) > 0:
                est_retention_pct = round(stats.get("average_score_percent", 90.0), 1)
            else:
                est_retention_pct = 92.5

            res = {
                "status": "ok",
                "total_cards": total_cards,
                "mastered_cards": mastered_cards,
                "learning_cards": learning_cards,
                "due_cards": due_cards,
                "due_count": due_cards,
                "average_score_percent": stats.get("average_score_percent", 0.0),
                "average_q_rating": stats.get("average_q_rating", 0.0),
                "average_ease_factor": avg_ef,
                "avg_ease_factor": avg_ef,
                "average_interval_days": avg_interval,
                "avg_interval_days": avg_interval,
                "estimated_retention_pct": est_retention_pct,
                "retention_pct": est_retention_pct,
                "mastery_score_pct": mastery_score_pct,
                "mastery_pct": mastery_score_pct,
                "mastery_level": stats.get("mastery_level", "Novice"),
                "total_reviews": stats.get("total_reviews", 0),
                "q_distribution": stats.get("q_distribution", {})
            }
            self.send_json_response(res)
        except Exception as e:
            sys.stderr.write(f"[Dashboard] cognitive/stats error: {e}\n")
            self.send_json_response({"error": str(e)}, status=500)

    def handle_cognitive_next_question(self, query_params):
        try:
            from vazus_core.integrations.cognitive_tutor_engine import CognitiveTutorEngine
            engine = CognitiveTutorEngine(db_path=self.db_path)
            
            all_cards = engine.get_all_cards(limit=1)
            if not all_cards:
                engine.sync_zettelkasten_notes()
                
            due_cards = engine.get_due_cards(limit=1)
            if due_cards:
                card = due_cards[0]
                is_due = True
            else:
                all_cards = engine.get_all_cards(limit=1)
                if all_cards:
                    card = all_cards[0]
                    is_due = False
                else:
                    card = None
                    is_due = False

            if card:
                res = {
                    "status": "ok",
                    "is_due": is_due,
                    "card": card,
                    "card_id": card["id"],
                    "id": card["id"],
                    "entity_id": card["entity_id"],
                    "entity_type": card["entity_type"],
                    "question_type": card["question_type"],
                    "question_text": card["question_text"],
                    "target_answer": card["target_answer"],
                    "repetition_n": card["repetition_n"],
                    "ease_factor": card["ease_factor"],
                    "interval_days": card["interval_days"]
                }
                self.send_json_response(res)
            else:
                self.send_json_response({"status": "empty", "card": None, "message": "No cards available"}, status=200)
        except Exception as e:
            sys.stderr.write(f"[Dashboard] cognitive/next-question error: {e}\n")
            self.send_json_response({"error": str(e)}, status=500)
    def _record_tutor_review(
        self, card_id: str, score: float, q_rating: int, user_answer: str,
        *, feedback: str, now_str: str
    ) -> str:
        review_id = f"review_{uuid.uuid4().hex[:12]}"
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                INSERT INTO tutor_reviews (
                    id, card_id, score_percent, q_rating, user_response,
                    feedback_rationale, response_time_sec, reviewed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (review_id, card_id, score, q_rating, user_answer, feedback, 0.0, now_str))
            conn.commit()
        finally:
            conn.close()
        return review_id

    @staticmethod
    def _update_card_sm2_schedule(card: dict, q_rating: int, engine: Any) -> dict:
        from vazus_core.integrations.cognitive_tutor_engine import calculate_sm2_update
        cur_n, cur_ef = card["repetition_n"], card["ease_factor"]
        cur_interval, cur_lapses = card["interval_days"], card["lapses"]

        new_n, new_ef, new_interval = calculate_sm2_update(cur_n, cur_ef, cur_interval, q_rating)
        new_lapses = cur_lapses + (1 if q_rating < 3 else 0)

        now_dt = datetime.datetime.now(datetime.timezone.utc)
        next_dt = now_dt + datetime.timedelta(days=new_interval)
        now_str, next_str = now_dt.isoformat(), next_dt.isoformat()

        card.update({
            "repetition_n": new_n, "ease_factor": new_ef, "interval_days": new_interval,
            "lapses": new_lapses, "last_review_at": now_str, "next_review_at": next_str
        })
        engine.save_card(card)
        return {
            "repetition_n": new_n, "ease_factor": new_ef, "interval_days": new_interval,
            "lapses": new_lapses, "last_review_at": now_str, "next_review_at": next_str
        }

    def handle_cognitive_evaluate_answer(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body_bytes = self.rfile.read(content_length) if content_length > 0 else b"{}"
            data = json.loads(body_bytes.decode("utf-8"))

            card_id = data.get("card_id")
            user_answer = data.get("user_answer", "")
            quality_grade = data.get("quality_grade")

            if not card_id:
                self.send_json_response({"error": "Missing card_id parameter"}, status=400)
                return

            from vazus_core.integrations.cognitive_tutor_engine import CognitiveTutorEngine, evaluate_answer
            engine = CognitiveTutorEngine(db_path=self.db_path)
            card = engine.get_card(card_id)
            if not card:
                self.send_json_response({"error": f"Card not found: {card_id}"}, status=404)
                return

            eval_res = evaluate_answer(card, user_answer)
            score, q_rating, feedback = eval_res["score_percent"], eval_res["q_rating"], eval_res["feedback_rationale"]

            if quality_grade is not None:
                try:
                    q_rating = max(0, min(5, int(quality_grade)))
                except (ValueError, TypeError) as exc:
                    logger.debug("Failed parsing quality_grade %s: %s", quality_grade, exc)

            sched = self._update_card_sm2_schedule(card, q_rating, engine)
            now_str = sched["last_review_at"]
            review_id = self._record_tutor_review(
                card_id, score, q_rating, user_answer, feedback=feedback, now_str=now_str
            )

            res = {
                "status": "ok",
                "review_id": review_id,
                "card_id": card_id,
                "score_percent": score,
                "score_pct": score,
                "q_rating": q_rating,
                "quality_grade": q_rating,
                "feedback_rationale": feedback,
                "feedback": feedback,
                "target_answer": card.get("target_answer", ""),
                "new_ease_factor": sched["ease_factor"],
                "new_interval_days": sched["interval_days"],
                "sm2_update": sched
            }
            self.send_json_response(res)
        except Exception as e:
            sys.stderr.write(f"[Dashboard] cognitive/evaluate-answer error: {e}\n")
            self.send_json_response({"error": str(e)}, status=500)

    @staticmethod
    def _resolve_wiki_note_file(raw_id: str) -> Optional[Path]:
        wiki_base = Path("/home/tarhes/Проекты/vazus/services/memory/semantic/wiki").resolve()
        clean_id = urllib.parse.unquote(raw_id).strip()
        if not clean_id:
            return None

        # Clean relative note identifier (strip leading slashes / dots)
        safe_rel = clean_id.lstrip("/\\")
        candidate_paths = [
            wiki_base / f"{safe_rel}.md",
            wiki_base / safe_rel,
        ]
        for cand in candidate_paths:
            try:
                res = cand.resolve()
                if res.is_relative_to(wiki_base) and res.exists() and res.is_file():
                    if res.suffix.lower() in (".md", ".markdown"):
                        return res
            except Exception as exc:
                logger.debug("Path resolution failed for %s: %s", cand, exc)
        return None

    def handle_wiki_note(self, query_params):
        try:
            raw_id = query_params.get("id", [""])[0].strip() or query_params.get("path", [""])[0].strip()
            if not raw_id:
                self.send_json_response({"error": "Missing note id or path parameter"}, status=400)
                return

            clean_id = urllib.parse.unquote(raw_id).strip()
            if ".." in clean_id or clean_id.startswith(("/", "\\")) or (len(clean_id) > 1 and clean_id[1] == ":"):
                self.send_json_response({"error": "Path traversal forbidden"}, status=403)
                return

            target_file = self._resolve_wiki_note_file(raw_id)
            if not target_file:
                self.send_json_response({"error": f"Note not found: {raw_id}"}, status=404)
                return

            from vazus_core.integrations.cognitive_tutor_engine import parse_zettel_markdown
            parsed = parse_zettel_markdown(target_file)
            raw_content = target_file.read_text(encoding="utf-8", errors="ignore")

            res = {
                "status": "ok",
                "id": parsed.get("id", target_file.stem),
                "title": parsed.get("title", target_file.stem),
                "content": raw_content,
                "parsed_entity": parsed,
                "wikilinks": parsed.get("wikilinks", []),
                "source_file": str(target_file)
            }
            self.send_json_response(res)
        except Exception as e:
            sys.stderr.write(f"[Dashboard] wiki/note error: {e}\n")
            self.send_json_response({"error": str(e)}, status=500)

    @staticmethod
    def _toggle_checkbox_in_lines(lines: list[str], checkbox_index: int, checked: bool) -> tuple[list[str], bool]:
        current_idx = 0
        modified = False
        for i in range(len(lines)):
            m = re.match(r'^([ \t]*- \[)([ xX])(\].*)$', lines[i])
            if m:
                if current_idx == checkbox_index:
                    new_mark = "x" if checked else " "
                    lines[i] = f"{m.group(1)}{new_mark}{m.group(3)}"
                    modified = True
                    break
                current_idx += 1
        return lines, modified

    def handle_wiki_checkbox(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 10 * 1024 * 1024:  # 10 MB limit
                self.send_error(413, "Payload Too Large: Content-Length exceeds 10MB limit")
                return
            body_bytes = self.rfile.read(content_length) if content_length > 0 else b"{}"
            data = json.loads(body_bytes.decode("utf-8"))

            raw_id = str(data.get("id") or data.get("note_id") or "").strip()
            checkbox_index = int(data.get("checkbox_index", 0))
            checked = bool(data.get("checked", False))

            if not raw_id:
                self.send_json_response({"error": "Missing id parameter"}, status=400)
                return

            clean_id = urllib.parse.unquote(raw_id).strip()
            if ".." in clean_id or clean_id.startswith(("/", "\\")) or (len(clean_id) > 1 and clean_id[1] == ":"):
                self.send_json_response({"error": "Path traversal forbidden"}, status=403)
                return

            target_file = self._resolve_wiki_note_file(raw_id)
            if not target_file:
                self.send_json_response({"error": f"Note file not found: {raw_id}"}, status=404)
                return

            content = target_file.read_text(encoding="utf-8", errors="ignore")
            lines, modified = self._toggle_checkbox_in_lines(content.splitlines(), checkbox_index, checked)

            if modified:
                new_content = "\n".join(lines) + ("\n" if content.endswith("\n") else "")
                target_file.write_text(new_content, encoding="utf-8")

            self.send_json_response({
                "status": "ok",
                "updated": modified,
                "id": raw_id,
                "checkbox_index": checkbox_index,
                "checked": checked
            })
        except Exception as e:
            sys.stderr.write(f"[Dashboard] wiki/checkbox error: {e}\n")
            self.send_json_response({"error": str(e)}, status=500)

    def handle_notebooklm_study_guides(self):
        try:
            guide_dir = Path("/home/tarhes/Проекты/vazus/knowledge/.study_guides")
            guides = []
            if guide_dir.exists():
                for f in guide_dir.glob("*.md"):
                    guides.append({
                        "name": f.name,
                        "path": str(f).replace("\\", "/"),
                        "size": f.stat().st_size,
                        "created": datetime.datetime.fromtimestamp(f.stat().st_ctime).strftime("%Y-%m-%d %H:%M")
                    })
            self.send_json_response({"study_guides": guides})
        except Exception as e:
            self.send_json_response({"error": str(e)}, status=500)

    def handle_notebooklm_podcasts(self):
        try:
            podcast_dir = Path("/home/tarhes/Проекты/vazus/knowledge/.podcasts")
            podcasts = []
            if podcast_dir.exists():
                for f in podcast_dir.glob("*.*"):
                    if f.suffix in (".mp3", ".wav", ".txt", ".json"):
                        podcasts.append({
                            "name": f.name,
                            "path": str(f).replace("\\", "/"),
                            "size": f.stat().st_size,
                            "type": f.suffix[1:]
                        })
            self.send_json_response({"podcasts": podcasts})
        except Exception as e:
            self.send_json_response({"error": str(e)}, status=500)

    def handle_notebooklm_generate_podcast(self):
        try:
            from vazus_core.integrations.notebook_synthesis_engine import NotebookSynthesisEngine
            from vazus_core.integrations.tts_podcast_generator import synthesize_podcast_audio
            engine = NotebookSynthesisEngine()
            script = engine.generate_audio_podcast_script(topic="Сводный обзор базы знаний и МИРЭА")
            audio_path = synthesize_podcast_audio(script["dialogue"])
            self.send_json_response({"status": "ok", "audio_path": audio_path, "script": script})
        except Exception as e:
            self.send_json_response({"error": str(e)}, status=500)

    def handle_system_overview(self):
        try:
            from vazus_core.paths import DEFAULT_DB_PATH, VAZUS_ROOT
            from vazus_core.engine.health_registry import health_registry
            import platform

            db_target = Path(self.db_path) if self.db_path else DEFAULT_DB_PATH
            db_size_mb = round(db_target.stat().st_size / (1024 * 1024), 2) if db_target.exists() else 0.0

            table_counts = {}
            if db_target.exists():
                try:
                    conn = sqlite3.connect(str(db_target), timeout=2.0)
                    cur = conn.cursor()
                    tables_to_check = [
                        "organic_insights", "kg_nodes", "kg_edges", "j_space_tool_metadata",
                        "j_space_tool_activations", "finance_transactions", "nutrition_log",
                        "mirea_milestones", "mem0_facts", "telemetry_function_hits", "improvement_suggestions"
                    ]
                    for tbl in tables_to_check:
                        try:
                            cur.execute(f"SELECT count(*) FROM {tbl}")
                            table_counts[tbl] = cur.fetchone()[0]
                        except Exception:
                            table_counts[tbl] = 0
                    conn.close()
                except Exception:
                    pass

            health_rep = health_registry.get_health_report()

            cpu_pct = 0.0
            ram_pct = 0.0
            ram_used_gb = 0.0
            ram_total_gb = 0.0
            try:
                import psutil
                cpu_pct = psutil.cpu_percent(interval=None)
                ram = psutil.virtual_memory()
                ram_pct = ram.percent
                ram_used_gb = round((ram.used / (1024**3)), 1)
                ram_total_gb = round((ram.total / (1024**3)), 1)
            except Exception:
                pass

            overview = {
                "system": {
                    "platform": platform.platform(),
                    "python_version": platform.python_version(),
                    "vazus_root": str(VAZUS_ROOT),
                    "db_path": str(db_target),
                    "db_size_mb": db_size_mb,
                    "cpu_percent": cpu_pct,
                    "ram_used_gb": ram_used_gb,
                    "ram_total_gb": ram_total_gb,
                    "ram_percent": ram_pct,
                },
                "health": health_rep,
                "metrics": table_counts,
                "timestamp": datetime.datetime.now().isoformat(),
            }
            self.send_json_response(overview)
        except Exception as e:
            self.send_json_response({"error": str(e)}, status=500)

    def handle_knowledge_insights(self, query_params):
        try:
            q = query_params.get("query", [""])[0].strip()
            limit = min(int(query_params.get("limit", [60])[0]), 200)
            conn = sqlite3.connect(self.db_path, timeout=5.0)
            cur = conn.cursor()
            if q:
                cur.execute(
                    "SELECT id, category, insight, timestamp, created_at FROM organic_insights WHERE insight LIKE ? OR category LIKE ? ORDER BY id DESC LIMIT ?",
                    (f"%{q}%", f"%{q}%", limit),
                )
            else:
                cur.execute(
                    "SELECT id, category, insight, timestamp, created_at FROM organic_insights ORDER BY id DESC LIMIT ?",
                    (limit,),
                )
            rows = [
                {
                    "id": r[0],
                    "category": r[1] or "General",
                    "insight": r[2],
                    "tags": r[1] or "Insight",
                    "created_at": str(r[4] or r[3] or "")[:19],
                }
                for r in cur.fetchall()
            ]
            conn.close()
            self.send_json_response({"total": len(rows), "insights": rows})
        except Exception as e:
            self.send_json_response({"error": str(e), "insights": []}, status=500)

    def handle_academic_debts(self):
        try:
            deadline = datetime.date(2026, 10, 15)
            today = datetime.date.today()
            days_remaining = max(0, (deadline - today).days)

            debts = []
            conn = sqlite3.connect(self.db_path, timeout=5.0)
            cur = conn.cursor()
            try:
                cur.execute("SELECT id, title, status, deadline, credits, difficulty, teacher, notes FROM mirea_milestones ORDER BY id ASC")
                for r in cur.fetchall():
                    debts.append({
                        "id": str(r[0]),
                        "title": r[1],
                        "status": r[2] or "IN_PROGRESS",
                        "deadline": r[3] or "15.10.2026",
                        "credits": r[4] or 3,
                        "difficulty": r[5] or "Medium",
                        "teacher": r[6] or "Кафедра КИТПиПИ",
                        "notes": r[7] or "",
                    })
            except Exception:
                pass
            conn.close()

            if not debts:
                canonical_18 = [
                    ("1", "ЭВМ и периферийные устройства", "Кафедра КИТПиПИ", "High", 4, "Лабораторные 1-4, типовой расчет"),
                    ("2", "Информатика", "Кафедра КИТПиПИ", "Medium", 3, "Тесты СДО, практические задания"),
                    ("3", "Алгоритмы и структуры данных", "Кафедра КИТПиПИ", "High", 4, "Деревья, графы, балансировка"),
                    ("4", "Высшая математика (Математический анализ)", "Кафедра ВМ", "High", 5, "Интегралы, ряды, ДУ"),
                    ("5", "Физика", "Кафедра общей физики", "Medium", 4, "Лабораторные работы, коллоквиум"),
                    ("6", "Базы данных", "Кафедра КИТПиПИ", "Medium", 3, "SQL нормализация, реляционные схемы"),
                    ("7", "Объектно-ориентированное программирование", "Кафедра КИТПиПИ", "Medium", 4, "Паттерны проектирования, SOLID"),
                    ("8", "Операционные системы", "Кафедра КИТПиПИ", "High", 4, "Процессы, потоки, планировщик Linux/Win32"),
                    ("9", "Сети и телекоммуникации", "Кафедра КИТПиПИ", "Medium", 3, "TCP/IP, маршрутизация, Wireshark"),
                    ("10", "Дискретная математика", "Кафедра ВМ", "Medium", 3, "Теория графов, логика предикатов"),
                    ("11", "Архитектура вычислительных систем", "Кафедра КИТПиПИ", "High", 4, "Ассемблер, микроархитектура, конвейер"),
                    ("12", "Теория вероятностей и математическая статистика", "Кафедра ВМ", "Medium", 3, "Случайные величины, регрессия"),
                    ("13", "Инженерная и компьютерная графика", "Кафедра ИГ", "Low", 2, "Чертежи AutoCAD / Компас"),
                    ("14", "Экология", "Кафедра экологии", "Low", 2, "Реферат, тестирование"),
                    ("15", "История России", "Кафедра истории", "Low", 2, "Эссе, тест"),
                    ("16", "Иностранный язык (Английский)", "Кафедра ИЯ", "Low", 2, "Технический перевод, лексика IT"),
                    ("17", "Правоведение", "Кафедра права", "Low", 2, "Правовые основы в сфере IT"),
                    ("18", "Физическая культура и спорт", "Кафедра ФК", "Low", 2, "Нормативы / реферат")
                ]
                debts = [
                    {
                        "id": d[0],
                        "title": d[1],
                        "teacher": d[2],
                        "difficulty": d[3],
                        "credits": d[4],
                        "notes": d[5],
                        "status": "ACADEMIC_DEBT",
                        "deadline": "15.10.2026",
                    }
                    for d in canonical_18
                ]

            self.send_json_response({
                "student": {
                    "name": "Жуков Максим Дмитриевич",
                    "group": "ИВБО-22-25",
                    "student_id": "25И0566",
                    "institute": "РТУ МИРЭА, ИИТ, кафедра КИТПиПИ",
                },
                "deadline": "2026-10-15",
                "days_remaining": days_remaining,
                "total_debts": len(debts),
                "debts": debts
            })
        except Exception as e:
            self.send_json_response({"error": str(e)}, status=500)

    def handle_tools_catalog(self, query_params):
        try:
            q = query_params.get("query", [""])[0].strip().lower()
            conn = sqlite3.connect(self.db_path, timeout=5.0)
            cur = conn.cursor()
            cur.execute("SELECT tool_name, module, description, parameters_json, keywords, is_native FROM j_space_tool_metadata")
            tools = []
            for r in cur.fetchall():
                t_name, mod, desc, schema, kw, is_nat = r[0], r[1], r[2], r[3], r[4], r[5]
                if q and (q not in str(t_name).lower() and q not in str(desc).lower() and q not in str(mod).lower()):
                    continue
                tools.append({
                    "id": t_name,
                    "name": t_name,
                    "module": mod or "vazus_core",
                    "description": desc or "J-Space system tool",
                    "schema": schema or "{}",
                    "keywords": kw or "",
                    "is_native": bool(is_nat)
                })
            conn.close()
            self.send_json_response({"total": len(tools), "tools": tools})
        except Exception as e:
            self.send_json_response({"error": str(e), "tools": []}, status=500)

    def handle_wiki_tree(self):
        try:
            from vazus_core.paths import MEMORY_DIR
            files = []
            for p in sorted(MEMORY_DIR.glob("*.md")):
                files.append({
                    "name": p.name,
                    "size": p.stat().st_size,
                    "modified": datetime.datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                })
            self.send_json_response({"files": files})
        except Exception as e:
            self.send_json_response({"error": str(e), "files": []}, status=500)

    def handle_wiki_content(self, query_params):
        try:
            from vazus_core.paths import MEMORY_DIR
            f_name = query_params.get("file", ["USER.md"])[0]
            safe_name = Path(f_name).name
            target = MEMORY_DIR / safe_name
            if not target.exists() or not target.is_file():
                self.send_error(404, "Wiki document not found")
                return
            content = target.read_text(encoding="utf-8", errors="replace")
            self.send_json_response({"file": safe_name, "content": content})
        except Exception as e:
            self.send_json_response({"error": str(e)}, status=500)

    def handle_security_verify(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(length).decode("utf-8")
            data = json.loads(raw_body)
            from vazus_core.verification.substrate_guard import SubstrateGuard, ToolCallRequest
            guard = SubstrateGuard()
            req = ToolCallRequest.from_raw(data.get("tool_name", "write_to_file"), data)
            res = guard.verify_tool_action(req)
            self.send_json_response(res)
        except Exception as e:
            self.send_json_response({"error": str(e), "decision": "deny", "reason": f"Verification error: {e}"}, status=400)

    def handle_finance_summary(self):
        try:
            conn = sqlite3.connect(self.db_path, timeout=5.0)
            cur = conn.cursor()
            cur.execute("SELECT category, sum(amount_rub), count(*) FROM finance_transactions GROUP BY category")
            categories = [{"category": r[0] or "Прочее", "total": round(r[1] or 0, 2), "count": r[2]} for r in cur.fetchall()]
            cur.execute("SELECT id, timestamp, amount_rub, category, merchant, operation_type FROM finance_transactions ORDER BY id DESC LIMIT 20")
            recent = [
                {"id": r[0], "date": str(r[1])[:10] if r[1] else "", "amount": r[2], "category": r[3] or "Прочее", "description": r[4] or r[5] or ""}
                for r in cur.fetchall()
            ]
            conn.close()
            self.send_json_response({"categories": categories, "recent": recent})
        except Exception as e:
            self.send_json_response({"error": str(e), "categories": [], "recent": []}, status=500)

    def handle_health_summary(self):
        try:
            conn = sqlite3.connect(self.db_path, timeout=5.0)
            cur = conn.cursor()
            cur.execute("SELECT substr(timestamp, 1, 10) as d, sum(calories_kcal), sum(protein_g), sum(carbs_g), sum(fat_g) FROM nutrition_log GROUP BY d ORDER BY d DESC LIMIT 14")
            nutrition = [
                {"date": r[0] or "", "calories": round(r[1] or 0), "protein": round(r[2] or 0, 1), "carbs": round(r[3] or 0, 1), "fat": round(r[4] or 0, 1)}
                for r in cur.fetchall()
            ]
            cur.execute("SELECT substr(timestamp, 1, 10), weight_kg, body_fat_pct, muscle_mass_kg FROM mi_scale_weighins ORDER BY id DESC LIMIT 10")
            weighins = [
                {"date": r[0] or "", "weight": r[1], "fat": r[2], "muscle": r[3]}
                for r in cur.fetchall()
            ]
            conn.close()
            self.send_json_response({"nutrition": nutrition, "weighins": weighins})
        except Exception as e:
            self.send_json_response({"error": str(e), "nutrition": [], "weighins": []}, status=500)

    def handle_ai_status(self):
        try:
            import urllib.request
            ollama_online = False
            ollama_models = []
            try:
                req = urllib.request.Request("http://127.0.0.1:11434/api/tags", headers={"User-Agent": "Vazus/5.0"})
                with urllib.request.urlopen(req, timeout=1.0) as resp:
                    if resp.status == 200:
                        ollama_online = True
                        data = json.loads(resp.read().decode("utf-8"))
                        ollama_models = [m.get("name") for m in data.get("models", [])]
            except Exception:
                pass

            from vazus_core.paths import MODELS_DIR
            gemma_installed = (MODELS_DIR / "gemma-4-e2b-it-int4-ov").exists()

            self.send_json_response({
                "openvino": {
                    "gemma_installed": gemma_installed,
                    "model_dir": str(MODELS_DIR / "gemma-4-e2b-it-int4-ov"),
                },
                "ollama": {
                    "online": ollama_online,
                    "host": "http://127.0.0.1:11434",
                    "models": ollama_models
                }
            })
        except Exception as e:
            self.send_json_response({"error": str(e)}, status=500)

    def send_json_response(self, data: dict, status: int = 200):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)


VazusDashboardHTTPHandler = DashboardRequestHandler


def main():
    parser = argparse.ArgumentParser(description="vazus Multimodal Knowledge & Cognitive Mastery Dashboard Server")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8501, help="Port number (default: 8501)")
    parser.add_argument("--db", type=str, default=DEFAULT_DB_PATH, help="Path to SQLite database")

    args = parser.parse_args()

    DashboardRequestHandler.db_path = args.db

    server = ThreadedHTTPServer((args.host, args.port), DashboardRequestHandler)
    print(f"[Dashboard] vazus Multimodal Knowledge & Cognitive Mastery Dashboard running at http://{args.host}:{args.port}/")
    print(f"[Dashboard] Database: {args.db}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[Dashboard] Shutting down server.")
        server.server_close()


if __name__ == "__main__":
    main()
