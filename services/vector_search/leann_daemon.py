#!/usr/bin/env python3
"""
leann_daemon.py — Persistent semantic search daemon on port 5010.
Uses leann_search_direct (sentence-transformers + numpy) — no ZMQ, no LEANN daemon.
Loads model ONCE on startup, then answers queries in <1s.

API:
  GET  http://127.0.0.1:5010/health  → {"ok": true, "model": "loaded", "corpus": N}
  POST http://127.0.0.1:5010/search  → {"query": "...", "top_k": 5}
  →   {"results": [{"text": "...", "score": 0.9, "source": "leann:pyenv"}]}
"""
import json
import sys
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

# Add scripts dir to path
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

PORT = 5010

# Model selection via env var (default: all-MiniLM, upgrade to nomic when available)
# Set LEANN_MODEL=nomic-ai/nomic-embed-text-v1.5 and LEANN_TRUST_REMOTE=1 to upgrade
_model_name = os.environ.get("LEANN_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
print(f"[leann-daemon] Using model: {_model_name}", file=sys.stderr, flush=True)

# Force offline mode — model already in HF cache
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

print(f"[leann-daemon] Loading model and corpus...", file=sys.stderr, flush=True)

from leann_search_direct import search as _search, _load

_load()  # Pre-load model + corpus embeddings

print(f"[leann-daemon] Ready. Serving on http://127.0.0.1:{PORT}", file=sys.stderr, flush=True)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # suppress request logs

    def do_GET(self):
        if self.path == "/health":
            from leann_search_direct import _corpus_texts
            body = json.dumps({"ok": True, "model": "loaded", "corpus": len(_corpus_texts)}).encode()
            self._respond(200, body)
        else:
            self._respond(404, b'{"error":"not found"}')

    def do_POST(self):
        if self.path != "/search":
            self._respond(404, b'{"error":"not found"}')
            return
        length = int(self.headers.get("Content-Length", 0))
        data   = json.loads(self.rfile.read(length).decode())
        query  = data.get("query", "")
        top_k  = int(data.get("top_k", 5))

        try:
            results = _search(query, top_k=top_k)
            self._respond(200, json.dumps({"results": results}).encode())
        except Exception as e:
            self._respond(500, json.dumps({"error": str(e)}).encode())

    def _respond(self, code: int, body: bytes):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    httpd = HTTPServer(("127.0.0.1", PORT), Handler)
    print(f"[leann-daemon] HTTP server started on port {PORT}", file=sys.stderr, flush=True)
    httpd.serve_forever()
