#!/usr/bin/env python3
"""
vazus.scripts.knowledge_mcp — FastMCP Tool Server for Multimodal Knowledge Engine.

Exposes FastMCP tools for LLM subagents:
- search_multimodal_knowledge
- get_media_scene_details
- stream_video_segment_info
"""

import sys
import json
import sqlite3
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from fastmcp import FastMCP
except ImportError:
    from mcp.server.fastmcp import FastMCP

try:
    from vazus_core.memory.embeddings import UnifiedEmbeddingManager
except ImportError:
    UnifiedEmbeddingManager = None

DEFAULT_DB_PATH = Path("C:/vazus/services/memory/vazus.db")

mcp = FastMCP("vazus-multimodal-knowledge")


@mcp.tool(description=(
    "Searches the vazus Multimodal Knowledge Engine using 768D vector similarity search. "
    "Returns relevant MediaScene and TelegramMessage nodes matching the query."
))
def search_multimodal_knowledge(query: str, top_k: int = 5, domain: str = "") -> str:
    """Searches multimodal knowledge nodes using vector similarity."""
    embedder = UnifiedEmbeddingManager()
    raw_results = embedder.search_unified_vector_space(
        query=query,
        db_path=DEFAULT_DB_PATH,
        top_k=top_k,
        domain_filter=domain if domain else None
    )

    formatted = []
    for r in raw_results:
        props = r.get("properties", {}) or {}
        node_type = r.get("node_type", "Unknown")
        item = {
            "id": r.get("id"),
            "name": r.get("name"),
            "node_type": node_type,
            "domain": r.get("domain"),
            "similarity": r.get("similarity", 0.0),
        }
        if node_type == "MediaScene":
            st = float(props.get("start_sec", 0.0))
            en = float(props.get("end_sec", 0.0))
            item.update({
                "source_file": props.get("source_file", ""),
                "start_sec": st,
                "end_sec": en,
                "duration": props.get("duration", round(en - st, 2)),
                "player_fragment": f"#t={st:.1f},{en:.1f}",
                "thumbnail_path": props.get("thumbnail_path", ""),
                "transcript": props.get("transcript") or r.get("description", ""),
                "next_scene_id": props.get("next_scene_id"),
                "prev_scene_id": props.get("prev_scene_id"),
            })
        elif node_type == "TelegramMessage":
            item.update({
                "msg_id": props.get("msg_id"),
                "channel_name": props.get("channel_name", ""),
                "date": props.get("date", ""),
                "text": props.get("text") or r.get("description", ""),
                "referenced_media": props.get("referenced_media_files", []),
            })
        else:
            item.update({"properties": props})
        formatted.append(item)

    return json.dumps(formatted, indent=2, ensure_ascii=False)


@mcp.tool(description=(
    "Retrieves full metadata details, transcript, and sequential scene references for a specific MediaScene node by scene_id."
))
def get_media_scene_details(scene_id: str) -> str:
    """Gets complete metadata for a MediaScene by scene_id."""
    if not DEFAULT_DB_PATH.exists():
        return json.dumps({"error": f"Database not found at {DEFAULT_DB_PATH}"})

    target_id = scene_id if scene_id.startswith("scene_") else f"scene_{scene_id}"

    conn = sqlite3.connect(DEFAULT_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        c = conn.cursor()
        row = c.execute(
            "SELECT id, name, domain, node_type, description, tags, properties FROM kg_nodes WHERE id = ? OR id = ?",
            (scene_id, target_id)
        ).fetchone()

        if not row:
            return json.dumps({"error": f"MediaScene '{scene_id}' not found in knowledge base."})

        props = json.loads(row["properties"]) if row["properties"] else {}

        # Query graph edges for NEXT_SCENE / PREV_SCENE / BELONGS_TO relations
        edges = c.execute(
            "SELECT target_id, relation FROM kg_edges WHERE source_id = ?",
            (row["id"],)
        ).fetchall()

        graph_relations = [{"target_id": e["target_id"], "relation": e["relation"]} for e in edges]

        details = {
            "id": row["id"],
            "name": row["name"],
            "domain": row["domain"],
            "node_type": row["node_type"],
            "scene_id": props.get("scene_id", row["id"]),
            "source_file": props.get("source_file", ""),
            "start_sec": props.get("start_sec", 0.0),
            "end_sec": props.get("end_sec", 0.0),
            "duration": props.get("duration", 0.0),
            "transcript": props.get("transcript") or row["description"],
            "thumbnail_path": props.get("thumbnail_path", ""),
            "media_type": props.get("media_type", "video"),
            "prev_scene_id": props.get("prev_scene_id"),
            "next_scene_id": props.get("next_scene_id"),
            "graph_relations": graph_relations,
        }
        return json.dumps(details, indent=2, ensure_ascii=False)
    finally:
        conn.close()


@mcp.tool(description=(
    "Retrieves HTTP video streaming playback parameter info for a scene_id, "
    "including 206 Range stream URL, URL fragments (#t=start,end), and thumbnail endpoints."
))
def stream_video_segment_info(scene_id: str) -> str:
    """Returns streaming parameters for playing a scene segment in HTML5 player."""
    scene_json = get_media_scene_details(scene_id)
    scene_data = json.loads(scene_json)
    if "error" in scene_data:
        return scene_json

    source_file = scene_data.get("source_file", "")
    st = scene_data.get("start_sec", 0.0)
    en = scene_data.get("end_sec", 0.0)

    stream_info = {
        "scene_id": scene_data.get("scene_id"),
        "source_file": source_file,
        "start_sec": st,
        "end_sec": en,
        "duration": scene_data.get("duration"),
        "player_fragment": f"#t={st:.1f},{en:.1f}",
        "stream_url": f"/api/v1/knowledge/stream?path={source_file}#t={st:.1f},{en:.1f}",
        "thumbnail_url": f"/api/v1/knowledge/thumbnail?path={scene_data.get('thumbnail_path', '')}",
        "transcript_preview": scene_data.get("transcript", "")[:150],
    }

    return json.dumps(stream_info, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()
