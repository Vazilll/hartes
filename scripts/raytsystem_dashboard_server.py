"""
raytsystem_dashboard_server.py — Raytsystem Public OS Visual Control Center Web Server.
Serves the official Raytsystem Control Plane web interface (FastAPI + React/Sigma.js Universe) on http://127.0.0.1:8765.

vazus SuperGraph OS Architecture
"""

import sys
import threading
from pathlib import Path

# Fix Windows console UTF-8 output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Setup project and dependency paths
RAYTSYSTEM_LABS_DIR = Path("C:/vazus/labs/raytsystem").resolve()
RAYTSYSTEM_SRC_DIR = RAYTSYSTEM_LABS_DIR / "src"

for p in [str(RAYTSYSTEM_SRC_DIR), "C:/vazus"]:
    if p not in sys.path:
        sys.path.insert(0, p)

import uvicorn
from raytsystem.webapp import create_app
from raytsystem.codegraph.projection import CodeGraphProjection

PORT = 8765
HOST = "127.0.0.1"


def async_update_graph(root: Path):
    """Updates AST Code Graph in background thread without blocking web server startup."""
    try:
        print(f"[Raytsystem Server] Background indexing AST Code Graph for workspace: {root}...", flush=True)
        proj = CodeGraphProjection(root)
        res = proj.update()
        print(f"[Raytsystem Server] Code graph updated: {res.node_count} nodes, {res.edge_count} edges.", flush=True)
    except Exception as e:
        print(f"[Raytsystem Server] Background code graph index notice: {e}", flush=True)


static_dir = RAYTSYSTEM_SRC_DIR / "raytsystem" / "webapp" / "static"
url = f"http://{HOST}:{PORT}"

# Create FastAPI ASGI Application instance
app = create_app(
    RAYTSYSTEM_LABS_DIR,
    allowed_hosts=frozenset({"*", HOST, f"{HOST}:{PORT}", "localhost"}),
    allowed_origins=frozenset({"*", url, "http://localhost:8765"}),
    static_dir=static_dir,
)


def run_server():
    # Trigger background graph index update
    t = threading.Thread(target=async_update_graph, args=(RAYTSYSTEM_LABS_DIR,), daemon=True)
    t.start()

    print(f"[Raytsystem Server] Launching Visual Control Center & SuperGraph Universe at: {url}", flush=True)
    print(f"[Raytsystem Server] Universe 3D / Graph Surface: {url}/universe", flush=True)

    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        access_log=False,
        log_level="info",
    )


if __name__ == "__main__":
    run_server()

