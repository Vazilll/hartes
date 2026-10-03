"""
services.data_fabric.main
=========================
Vazus Data Fabric Server (FastAPI + FastMCP) running on port 8765.
Unified backend engine powering App Engine VAE 2.0, Academic Dashboard,
and natural language Knowledge Graph tools over MCP.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastmcp import FastMCP

# Ensure root in sys.path
ROOT_DIR = Path(r"C:\vazus")
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.data_fabric.crud_router import router as crud_api_router, get_db_connection
from services.data_fabric.ws_bridge import ws_bridge

# 1. Initialize FastAPI application
app = FastAPI(
    title="vazus Data Fabric",
    description="Unified Data Fabric & FastMCP Gateway for Vazus SuperGraph OS VAE 2.0",
    version="2.0.0",
)

# 2. Configure CORS for local UI and Vite preview (ports 4400, 3000, 5173, etc.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Mount CRUD Router
app.include_router(crud_api_router)

# 4. Initialize FastMCP Tools
mcp = FastMCP("vazus-fabric")


@mcp.tool()
def query_knowledge_graph(query: str, top_k: int = 10) -> List[Dict[str, Any]]:
    """Search the vazus knowledge graph and organic insights via natural language or keyword."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        search_pat = f"%{query.strip()}%"
        cur.execute("""
            SELECT id, name, domain, node_type, description, tags 
            FROM kg_nodes 
            WHERE name LIKE ? OR description LIKE ? OR tags LIKE ?
            LIMIT ?
        """, (search_pat, search_pat, search_pat, top_k))
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@mcp.tool()
def query_academic_debts(status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """Returns academic debt milestones (RTU MIREA) with optional status filter."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        if status_filter:
            cur.execute("""
                SELECT id, subject, milestone_name, milestone_type, status, due_date, stage1_deadline
                FROM mirea_milestones
                WHERE status = ?
                ORDER BY id ASC
            """, (status_filter,))
        else:
            cur.execute("""
                SELECT id, subject, milestone_name, milestone_type, status, due_date, stage1_deadline
                FROM mirea_milestones
                ORDER BY id ASC
            """)
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


@mcp.tool()
def get_academic_schedule(weekday: Optional[str] = None) -> List[Dict[str, Any]]:
    """Queries academic schedule for group ИВБО-22-25."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        if weekday:
            cur.execute("""
                SELECT id, weekday, lesson_time, subject, lesson_type, classroom, teacher
                FROM mirea_schedule
                WHERE weekday LIKE ?
                ORDER BY id ASC
            """, (f"%{weekday}%",))
        else:
            cur.execute("""
                SELECT id, weekday, lesson_time, subject, lesson_type, classroom, teacher
                FROM mirea_schedule
                ORDER BY id ASC
            """)
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


# Mount FastMCP ASGI App onto FastAPI
try:
    app.mount("/mcp", mcp.get_asgi_app())
except Exception:
    pass


# 5. WebSocket HMR Bridge
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_bridge.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Echo or process incoming commands
            await ws_bridge.broadcast("client_ping", {"received": data})
    except WebSocketDisconnect:
        ws_bridge.disconnect(websocket)


# 6. Health Check
@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "vazus-data-fabric",
        "version": "2.0.0",
        "port": 8765,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("services.data_fabric.main:app", host="127.0.0.1", port=8765, reload=True)
