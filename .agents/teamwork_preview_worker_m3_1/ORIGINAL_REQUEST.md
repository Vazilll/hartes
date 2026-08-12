## 2026-07-24T11:58:41Z
You are Worker (teamwork_preview_worker) for Milestone 3: Interactive Dual Interface.
Your working directory is C:\vazus\.agents\teamwork_preview_worker_m3_1.

OBJECTIVE:
Implement the complete Dual Interactive Interface for the Multimodal Knowledge Engine in `vazus`:
1. `scripts/knowledge_chat.py`: Interactive CLI Chat interface.
2. `scripts/knowledge_mcp.py`: FastMCP Tool server interface for LLM subagents.
3. `scripts/dashboard.py`: Python Web Server backend serving REST API, HTTP Range media streaming, and static files.
4. `scripts/dashboard.html`: Interactive HTML5 Video Player & Graph Browser SPA.

REQUIREMENTS & SPECIFICATIONS:

1. `scripts/knowledge_chat.py`:
   - Argument parsing using `argparse`: `--query` / `-q` (str, required), `--top-k` / `-k` (int, default=5), `--db` (str, default="C:/vazus/vazus.db"), `--domain` / `-d` (str, default=""), `--json` (flag).
   - Uses `UnifiedEmbeddingManager` from `vazus_core.embeddings` to query `C:/vazus/vazus.db` using 768D vector similarity search.
   - For `MediaScene` nodes, output: title/name, timestamp range (`start_sec` to `end_sec` formatted as mm:ss or seconds), player URL fragment (`#t=start_sec,end_sec`), physical `source_file` path, `thumbnail_path`, and transcribed snippet.
   - For `TelegramMessage` nodes, output: message ID, channel name, text snippet, timestamp, and linked media references (`REFERENCES_MEDIA`).
   - Must return exit code 0 and pass command execution: `C:\vazus\.venv\Scripts\python.exe scripts/knowledge_chat.py --query "тест"`.

2. `scripts/knowledge_mcp.py`:
   - Built using `fastmcp` (or standard MCP tool definitions).
   - Exposes tools: `search_multimodal_knowledge(query, top_k, domain)`, `get_media_scene_details(scene_id)`, and `stream_video_segment_info(scene_id)`.
   - Connects to `C:/vazus/vazus.db` and uses `UnifiedEmbeddingManager`.

3. `scripts/dashboard.py`:
   - Fast, resilient Python Web Server (using Python standard library `http.server` / `socketserver` or `FastAPI`/`Starlette`/`aiohttp` if available in `.venv`).
   - Must support CLI args: `--host` (default "127.0.0.1"), `--port` (default 8501), `--db` (default "C:/vazus/vazus.db").
   - Endpoints:
     - `GET /`: Serves `scripts/dashboard.html`.
     - `GET /api/v1/knowledge/search?query=...&top_k=...&domain=...`: Performs vector search via `UnifiedEmbeddingManager` on `vazus.db`, returning JSON results.
     - `GET /api/v1/knowledge/stream?path=...`: Streams media file with `Accept-Ranges: bytes` and `206 Partial Content` header support for HTML5 video player timestamp seeking.
     - `GET /api/v1/knowledge/thumbnail?path=...`: Serves JPEG thumbnail images from `C:\vazus\knowledge\.thumbnails\`.
     - `GET /api/v1/knowledge/stats`: Returns database counts (`kg_nodes`, `kg_edges`, `MediaScene`, `TelegramMessage`, embedded count).

4. `scripts/dashboard.html`:
   - Clean, modern HTML5/CSS/JavaScript single-page app (SPA).
   - Features:
     - Header: "vazus SuperGraph OS — Multimodal Knowledge Hub".
     - Left Panel: Debounced live search input, domain filter tabs (`All`, `MediaScene`, `TelegramMessage`), and results list with thumbnail preview cards, similarity badges, timestamps (`00:00 - 02:02`), and click-to-play buttons.
     - Right Panel: HTML5 `<video id="video-player" controls autoplay>` element. When a card is clicked, updates video source to `/api/v1/knowledge/stream?path=...#t=start_sec,end_sec` and sets `currentTime = start_sec`.
     - Active Scene Transcript Box: Displays full transcript text and next/previous scene buttons (`NEXT_SCENE` graph navigation).

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

BUILD & TEST VERIFICATION REQUIREMENTS:
1. Verify syntax and imports for `scripts/knowledge_chat.py`, `scripts/knowledge_mcp.py`, `scripts/dashboard.py`.
2. Run acceptance test:
   `C:\vazus\.venv\Scripts\python.exe scripts/knowledge_chat.py --query "тест"`
   Confirm valid output with citations, timestamps, thumbnail paths, and exit code 0.
3. Test `scripts/dashboard.py` server startup & endpoints:
   Test REST search `/api/v1/knowledge/search?query=тест` and stats `/api/v1/knowledge/stats`.
4. Document all commands run and exact outputs in your `handoff.md`.

Send a completion message back to parent when done.
