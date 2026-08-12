# Backend REST API Design & Technical Analysis: R5 Cognitive & Mastery Tab

**Author**: Explorer 2 (Backend REST API Architect)  
**Milestone**: Milestone 5 (R5: Web Dashboard Cognitive & Mastery Tab)  
**Target File**: `scripts/dashboard.py`  
**Dependencies**: `vazus_core.cognitive_tutor_engine`, `vazus_core.zettelkasten_exporter`  
**Workspace**: `C:\vazus`  
**Date**: 2026-07-24  

---

## 1. Executive Summary

This report provides the full architectural design and technical specification for backend REST API endpoints serving the **Cognitive & Mastery Tab** (Milestone 5 R5) within `scripts/dashboard.py`.

The backend integration bridges the multithreaded Python HTTP server (`scripts/dashboard.py`) with the underlying **Active Learning SM-2 Spaced Repetition Engine** (`vazus_core/cognitive_tutor_engine.py`), SQLite persistence (`C:/vazus/vazus.db`), and the Zettelkasten Obsidian Wiki directory (`C:/vazus/services/memory/semantic/wiki`).

### Core REST API Endpoints Designed:
1. **`GET /api/v1/cognitive/mastery`**: Computes global mastery statistics, card counts, due card queue length, historical retention rate (%), SM-2 Quality rating distribution ($Q \in [0..5]$), and mastery progression tier.
2. **`GET /api/v1/cognitive/trainer`**: Retrieves the next due active recall flashcard question object. Triggers auto-seeding/syncing from Zettelkasten notes or `kg_nodes` if queue is empty.
3. **`POST /api/v1/cognitive/trainer`**: Evaluates student active recall answers via hybrid 768D semantic embedding similarity + keyword recall, calculates SM-2 state updates ($n', EF', I'$), updates card state in SQLite, and logs review telemetry.
4. **`GET /api/v1/cognitive/notes`**: Lists Zettelkasten Markdown notes or reads a single note by path, equipped with strict path boundary security (`is_relative_to(Path("C:/vazus"))`) to prevent path traversal attacks.

---

## 2. Server Architecture & HTTP Request Handling in `scripts/dashboard.py`

### 2.1 Existing Implementation Inspection
- **Server Harness**: `ThreadedHTTPServer(ThreadingMixIn, HTTPServer)` running on `127.0.0.1:8501`.
- **Request Handler**: `DashboardRequestHandler(BaseHTTPRequestHandler)`.
- **Current Routing**:
  - `do_GET()` routes `/`, `/api/v1/knowledge/search`, `/api/v1/knowledge/stream`, `/api/v1/knowledge/thumbnail`, `/api/v1/knowledge/stats`.
  - `send_json_response(data: dict, status: int = 200)` formats JSON responses with UTF-8 encoding, `Content-Length`, and CORS `Access-Control-Allow-Origin: *`.

### 2.2 Architectural Enhancements Required
To support Cognitive & Mastery features:
1. **HTTP Method Support**: Add `do_POST()` to handle `POST /api/v1/cognitive/trainer`.
2. **CORS Pre-flight Handling**: Add `do_OPTIONS()` returning HTTP 200 with `Access-Control-Allow-Methods: GET, POST, OPTIONS` and `Access-Control-Allow-Headers: Content-Type, Authorization`.
3. **Routing Table Expansion**: Map `/api/v1/cognitive/*` paths to dedicated handler methods in `do_GET()` and `do_POST()`.

---

## 3. Comprehensive REST API Specifications & Data Contracts

### 3.1 `GET /api/v1/cognitive/mastery`

- **Purpose**: Returns global active learning metrics, retention rates, and flashcard mastery statistics.
- **HTTP Method**: `GET`
- **Query Parameters**: None.
- **Backend Mechanics**:
  Calls `CognitiveTutorEngine(db_path=self.db_path).get_mastery_stats()`.
- **Response Schema (`200 OK`)**:
  ```json
  {
    "total_cards": 37,
    "due_cards": 5,
    "total_reviews": 18,
    "average_score_percent": 88.5,
    "retention_percent": 88.5,
    "average_q_rating": 4.35,
    "q_distribution": {
      "0": 1,
      "1": 0,
      "2": 2,
      "3": 3,
      "4": 5,
      "5": 7
    },
    "mastery_level": "Proficient",
    "mastery_percent": 65.0
  }
  ```
- **Field Definitions**:
  - `total_cards` (*int*): Total flashcards stored in `tutor_cards` table.
  - `due_cards` (*int*): Flashcards where `next_review_at <= NOW()` or `NULL`.
  - `average_score_percent` / `retention_percent` (*float*): Historical mean active recall accuracy (0.0 to 100.0%).
  - `average_q_rating` (*float*): Mean SM-2 quality rating $Q \in [0..5]$.
  - `q_distribution` (*dict[str, int]*): Review count breakdown by Quality rating Q (0 = Blackout, 5 = Perfect).
  - `mastery_level` (*str*): Skill tier ("Novice", "Apprentice", "Proficient", "Master").
  - `mastery_percent` (*float*): Percentage of cards with $n \ge 3$ and $EF \ge 2.3$.

---

### 3.2 `GET /api/v1/cognitive/trainer`

- **Purpose**: Fetches the next active recall card question for Socratic training.
- **HTTP Method**: `GET`
- **Query Parameters**:
  - `card_id` (*optional, str*): Explicit card ID to fetch.
  - `limit` (*optional, int*, default `1`): Number of due cards to return.
- **Backend Mechanics**:
  1. Instantiates `CognitiveTutorEngine(db_path=self.db_path)`.
  2. If `card_id` provided, fetches target card via `engine.get_card(card_id)`.
  3. Otherwise, calls `due_cards = engine.get_due_cards(limit=1)`.
  4. **Auto-seeding/Syncing**: If `due_cards` is empty:
     - Scans Zettelkasten Markdown notes in `C:/vazus/services/memory/semantic/wiki` via `engine.sync_zettelkasten_notes()`.
     - Queries `kg_nodes` in `vazus.db` for `ThesisNode` or `ProtocolNode` entities to create cards.
  5. Returns selected card object.
- **Response Schema (`200 OK`)**:
  ```json
  {
    "card": {
      "id": "card_a1b2c3d4e5f6",
      "entity_id": "Zettel_AI_Lessons_and_Mistakes",
      "entity_type": "ZettelNote",
      "question_type": "CONCEPT_EXPLANATION",
      "question_text": "Summarize the core claim and analytical significance of Zettel note 'AI Lessons and Mistakes'...",
      "repetition_n": 1,
      "ease_factor": 2.6,
      "interval_days": 1.0,
      "lapses": 0,
      "last_review_at": "2026-07-23T14:00:00Z",
      "next_review_at": "2026-07-24T14:00:00Z"
    },
    "total_due": 5
  }
  ```
- **HTTP Status Codes**:
  - `200 OK`: Card object found and returned.
  - `404 Not Found`: No flashcard cards available in system.

---

### 3.3 `POST /api/v1/cognitive/trainer`

- **Purpose**: Submits user answer for evaluation, calculates SM-2 state update, records review telemetry, and updates database.
- **HTTP Method**: `POST`
- **Request Headers**: `Content-Type: application/json`
- **Request Body Schema**:
  ```json
  {
    "card_id": "card_a1b2c3d4e5f6",
    "user_answer": "Active recall combined with SM-2 spaced repetition prevents memory decay and optimizes intervals.",
    "response_time_sec": 4.8
  }
  ```
- **Backend Mechanics**:
  1. Reads JSON payload from HTTP request body.
  2. Validates presence of `card_id` and `user_answer`.
  3. Calls `engine.process_review(card_id, user_answer, response_time_sec)`.
  4. Execution flow inside `process_review`:
     - Invokes `ResponseEvaluator`: 768D semantic embedding similarity + keyword recall + sequence token match.
     - Maps percentage score $S \in [0, 100]\%$ to SM-2 rating $Q \in [0..5]$ via `map_score_to_q`.
     - Updates SM-2 state $(n', EF', I')$:
       - $EF' = \max(1.3, EF + (0.1 - (5-Q)(0.08 + (5-Q)0.02)))$
       - If $Q \ge 3$: $n' = n + 1$, $I \in \{1, 3, 7, 21, \text{round}(I \cdot EF')\}$
       - If $Q < 3$: $n' = 0$, $I' = 1.0$ day, lapses incremented.
     - Writes updated record to `tutor_cards` and logs review event to `tutor_reviews` table in `vazus.db`.
- **Response Schema (`200 OK`)**:
  ```json
  {
    "review_id": "review_9f8e7d6c5b4a",
    "card_id": "card_a1b2c3d4e5f6",
    "score_percent": 92.5,
    "q_rating": 5,
    "feedback_rationale": "Outstanding active recall! Complete semantic accuracy.",
    "feedback": "Outstanding active recall! Complete semantic accuracy.",
    "sm2_update": {
      "repetition_n": 2,
      "ease_factor": 2.7,
      "interval_days": 3.0,
      "lapses": 0,
      "next_review_at": "2026-07-27T16:00:00Z"
    }
  }
  ```
- **HTTP Status Codes**:
  - `200 OK`: Answer successfully evaluated and state saved.
  - `400 Bad Request`: Missing `card_id` or invalid JSON body.
  - `404 Not Found`: Card ID not found in database.

---

### 3.4 `GET /api/v1/cognitive/notes`

- **Purpose**: Lists Zettelkasten Markdown notes or reads a specific note by path with strict path boundary enforcement.
- **HTTP Method**: `GET`
- **Query Parameters**:
  - `path` or `file` (*optional, str*): Path to note file.
  - `dir` (*optional, str*): Base directory (defaults to `C:/vazus/services/memory/semantic/wiki`).
- **Path Boundary Security Specification**:
  ```python
  allowed_base = Path("C:/vazus").resolve()

  if raw_path:
      clean_path = urllib.parse.unquote(raw_path)
      target_path = Path(clean_path).resolve()

      # Path Boundary Check using Python 3.9+ is_relative_to
      try:
          if not target_path.is_relative_to(allowed_base):
              self.send_json_response(
                  {"error": "Access Denied: Path outside allowed workspace boundary"}, 
                  status=403
              )
              return
      except (ValueError, RuntimeError):
          self.send_json_response(
              {"error": "Access Denied: Path outside allowed workspace boundary"}, 
              status=403
          )
          return
  ```

#### Mode A: Read Single Note (`path` provided)
- **Response Schema (`200 OK`)**:
  ```json
  {
    "id": "Zettel_AI_Lessons_and_Mistakes",
    "title": "Память об ошибках и правилах",
    "path": "C:/vazus/services/memory/semantic/wiki/AI_Lessons_and_Mistakes.md",
    "content": "# Память об ошибках и правилах\n\n## Core Claim\n...",
    "wikilinks": ["system_test_insights", "auto_test_insights", "Dialog_Context"],
    "action_items": [
      {
        "task": "Verify empirical evidence and source provenance for Zettel_AI_Lessons_and_Mistakes",
        "checked": false
      }
    ],
    "sources": ["SuperGraph Database Index"],
    "tags": ["iad", "zettel"]
  }
  ```

#### Mode B: List Notes (`path` NOT provided)
- **Response Schema (`200 OK`)**:
  ```json
  {
    "notes": [
      {
        "id": "Zettel_AI_Lessons_and_Mistakes",
        "title": "Память об ошибках и правилах",
        "filename": "AI_Lessons_and_Mistakes.md",
        "path": "C:/vazus/services/memory/semantic/wiki/AI_Lessons_and_Mistakes.md",
        "size_bytes": 1420,
        "modified_at": "2026-07-24T12:00:00Z"
      }
    ],
    "count": 37
  }
  ```

- **HTTP Status Codes**:
  - `200 OK`: Successful response.
  - `403 Forbidden`: Path traversal attempt detected (`is_relative_to` returned False).
  - `404 Not Found`: Specified note file does not exist.

---

## 4. Code Implementation Blueprint for `scripts/dashboard.py`

Below is the complete, drop-in Python implementation code to add to `scripts/dashboard.py`:

```python
# Import CognitiveTutorEngine and Zettel helper
try:
    from vazus_core.cognitive_tutor_engine import (
        CognitiveTutorEngine,
        parse_zettel_markdown
    )
except ImportError:
    CognitiveTutorEngine = None
    parse_zettel_markdown = None


class DashboardRequestHandler(BaseHTTPRequestHandler):
    db_path: str = DEFAULT_DB_PATH

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query_params = urllib.parse.parse_qs(parsed_url.query)

        try:
            if path in ("/", "/dashboard.html", "/index.html"):
                self.handle_serve_html()
            elif path == "/api/v1/knowledge/search":
                self.handle_search(query_params)
            elif path == "/api/v1/knowledge/stream":
                self.handle_stream(query_params)
            elif path == "/api/v1/knowledge/thumbnail":
                self.handle_thumbnail(query_params)
            elif path == "/api/v1/knowledge/stats":
                self.handle_stats()
            # Milestone 5 Cognitive & Mastery Routes
            elif path == "/api/v1/cognitive/mastery":
                self.handle_cognitive_mastery()
            elif path == "/api/v1/cognitive/trainer":
                self.handle_cognitive_trainer_get(query_params)
            elif path == "/api/v1/cognitive/notes":
                self.handle_cognitive_notes(query_params)
            else:
                self.send_error(404, "Endpoint Not Found")
        except Exception as e:
            sys.stderr.write(f"[Dashboard] Request Error: {e}\n")
            self.send_json_response({"error": f"Internal Server Error: {str(e)}"}, status=500)

    def do_POST(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        try:
            if path == "/api/v1/cognitive/trainer":
                self.handle_cognitive_trainer_post()
            else:
                self.send_error(404, "Endpoint Not Found")
        except Exception as e:
            sys.stderr.write(f"[Dashboard] Request Error: {e}\n")
            self.send_json_response({"error": f"Internal Server Error: {str(e)}"}, status=500)

    # -------------------------------------------------------------------------
    # Milestone 5 Handler Implementation Methods
    # -------------------------------------------------------------------------

    def handle_cognitive_mastery(self):
        if CognitiveTutorEngine is None:
            self.send_json_response({"error": "CognitiveTutorEngine unavailable"}, status=500)
            return

        engine = CognitiveTutorEngine(db_path=self.db_path)
        stats = engine.get_mastery_stats()
        stats["retention_percent"] = stats.get("average_score_percent", 0.0)
        self.send_json_response(stats)

    def handle_cognitive_trainer_get(self, query_params):
        if CognitiveTutorEngine is None:
            self.send_json_response({"error": "CognitiveTutorEngine unavailable"}, status=500)
            return

        engine = CognitiveTutorEngine(db_path=self.db_path)
        card_id = query_params.get("card_id", [""])[0].strip()

        if card_id:
            card = engine.get_card(card_id)
            if not card:
                self.send_json_response({"error": f"Card '{card_id}' not found"}, status=404)
                return
            self.send_json_response({"card": card, "total_due": 1})
            return

        due_cards = engine.get_due_cards(limit=1)
        if not due_cards:
            # Auto-seed cards if empty
            engine.sync_zettelkasten_notes()
            due_cards = engine.get_due_cards(limit=1)

        if not due_cards:
            cards = engine.get_all_cards(limit=1)
            if cards:
                due_cards = cards

        if not due_cards:
            self.send_json_response({"error": "No flashcards available"}, status=404)
            return

        stats = engine.get_mastery_stats()
        self.send_json_response({
            "card": due_cards[0],
            "total_due": stats.get("due_cards", len(due_cards))
        })

    def handle_cognitive_trainer_post(self):
        if CognitiveTutorEngine is None:
            self.send_json_response({"error": "CognitiveTutorEngine unavailable"}, status=500)
            return

        content_len = int(self.headers.get("Content-Length", 0))
        if content_len == 0:
            self.send_json_response({"error": "Empty request body"}, status=400)
            return

        body_bytes = self.rfile.read(content_len)
        try:
            payload = json.loads(body_bytes.decode("utf-8"))
        except Exception:
            self.send_json_response({"error": "Invalid JSON format"}, status=400)
            return

        card_id = payload.get("card_id", "").strip()
        user_answer = payload.get("user_answer", "").strip()
        response_time = float(payload.get("response_time_sec", 0.0))

        if not card_id:
            self.send_json_response({"error": "Missing 'card_id' parameter"}, status=400)
            return

        engine = CognitiveTutorEngine(db_path=self.db_path)
        try:
            review_res = engine.process_review(card_id, user_answer, response_time_sec=response_time)
            self.send_json_response(review_res, status=200)
        except ValueError as ve:
            self.send_json_response({"error": str(ve)}, status=404)

    def handle_cognitive_notes(self, query_params):
        raw_path = query_params.get("path", query_params.get("file", [""]))[0].strip()
        wiki_dir_str = query_params.get("dir", [r"C:\vazus\services\memory\semantic\wiki"])[0].strip()

        allowed_base = Path("C:/vazus").resolve()

        if raw_path:
            clean_path = urllib.parse.unquote(raw_path)
            note_path = Path(clean_path).resolve()

            # Security boundary verification
            try:
                if not note_path.is_relative_to(allowed_base):
                    self.send_json_response({"error": "Access Denied: Path outside allowed workspace boundary"}, status=403)
                    return
            except (ValueError, RuntimeError):
                self.send_json_response({"error": "Access Denied: Path outside allowed workspace boundary"}, status=403)
                return

            if not note_path.exists() or not note_path.is_file():
                self.send_json_response({"error": f"Note file not found: {raw_path}"}, status=404)
                return

            if parse_zettel_markdown:
                note_dict = parse_zettel_markdown(note_path)
            else:
                content = note_path.read_text(encoding="utf-8", errors="ignore")
                note_dict = {
                    "id": f"Zettel_{note_path.stem}",
                    "title": note_path.stem,
                    "content": content,
                    "wikilinks": re.findall(r'\[\[(.*?)\]\]', content)
                }

            # Extract action checklist items (- [ ] / - [x])
            content_text = note_dict.get("content", "")
            action_items = []
            for match in re.finditer(r'^\s*-\s*\[([ xX])\]\s*(.+)$', content_text, re.MULTILINE):
                checked = match.group(1).lower() == 'x'
                task_text = match.group(2).strip()
                action_items.append({"task": task_text, "checked": checked})

            note_dict["action_items"] = action_items
            note_dict["path"] = str(note_path)
            self.send_json_response(note_dict)
        else:
            wiki_dir = Path(wiki_dir_str)
            if not wiki_dir.exists():
                fallback_dir = Path("C:/vazus/memory/semantic/wiki")
                if fallback_dir.exists():
                    wiki_dir = fallback_dir

            notes_list = []
            if wiki_dir.exists():
                for md in wiki_dir.glob("*.md"):
                    try:
                        resolved_md = md.resolve()
                        if not resolved_md.is_relative_to(allowed_base):
                            continue
                        
                        stat = resolved_md.stat()
                        # Extract title from H1 or stem
                        title = resolved_md.stem
                        try:
                            first_lines = resolved_md.read_text(encoding="utf-8", errors="ignore")[:300]
                            h1_m = re.search(r'^#\s+(.+)$', first_lines, re.MULTILINE)
                            if h1_m:
                                title = h1_m.group(1).strip()
                        except Exception:
                            pass

                        notes_list.append({
                            "id": f"Zettel_{resolved_md.stem}",
                            "title": title,
                            "filename": resolved_md.name,
                            "path": str(resolved_md),
                            "size_bytes": stat.st_size,
                            "modified_at": datetime.datetime.fromtimestamp(stat.st_mtime, datetime.timezone.utc).isoformat()
                        })
                    except Exception:
                        continue

            self.send_json_response({
                "notes": notes_list,
                "count": len(notes_list)
            })
```

---

## 5. Security & Robustness Verification

1. **Path Traversal Protection**:
   Strictly verified using Python `Path.is_relative_to(Path("C:/vazus").resolve())`. Attempts to supply `C:/vazus/../Windows/System32/cmd.exe` or encoded `..%2f..%2f` resolve to canonical absolute paths and immediately trigger HTTP 403 Forbidden.
2. **CORS & Pre-flight Support**:
   Full CORS headers (`Access-Control-Allow-Origin: *`, `Access-Control-Allow-Methods: GET, POST, OPTIONS`, `Access-Control-Allow-Headers: Content-Type, Authorization`) ensure seamless frontend SPA requests.
3. **Database Concurrency & Resilience**:
   `CognitiveTutorEngine` utilizes WAL mode and thread-safe SQLite connections. Views `kg_flashcards` and `kg_review_logs` ensure backward compatibility.

---

## 6. Verification & Test Plan

1. **Python Unit Tests**: Execute `pytest tests/test_cognitive_tutor_engine.py` to confirm SM-2 mathematical correctness and persistence.
2. **HTTP Server Integration**: Start `scripts/dashboard.py` and run curl/requests commands against:
   - `GET /api/v1/cognitive/mastery`
   - `GET /api/v1/cognitive/trainer`
   - `POST /api/v1/cognitive/trainer`
   - `GET /api/v1/cognitive/notes`
   - `GET /api/v1/cognitive/notes?path=C:/vazus/services/memory/semantic/wiki/AI_Lessons_and_Mistakes.md`
   - `GET /api/v1/cognitive/notes?path=C:/Windows/System32/cmd.exe` (Verify HTTP 403 response).
