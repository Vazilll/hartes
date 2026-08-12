#!/usr/bin/env python3
"""
vazus.scripts.knowledge_chat — Interactive CLI Chat Interface for Multimodal Knowledge Engine.

Queries C:/vazus/vazus.db using 768D vector similarity search via UnifiedEmbeddingManager.
Outputs structured information for MediaScene and TelegramMessage nodes.
"""

import sys
import os
import argparse
import json
from pathlib import Path

# Force UTF-8 stdout/stderr encoding for Windows console compatibility
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

# Ensure vazus project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from vazus_core.embeddings import UnifiedEmbeddingManager
except ImportError:
    from embeddings import UnifiedEmbeddingManager


def format_timestamp(seconds: float) -> str:
    """Formats seconds into mm:ss string."""
    sec = int(seconds)
    mins = sec // 60
    secs = sec % 60
    return f"{mins:02d}:{secs:02d}"


def process_search_results(raw_results: list) -> list:
    """Formats raw vector search results into structured result objects."""
    formatted = []
    for idx, r in enumerate(raw_results, 1):
        node_type = r.get("node_type", "Unknown")
        props = r.get("properties", {}) or {}
        similarity = r.get("similarity", 0.0)

        item = {
            "rank": idx,
            "id": r.get("id"),
            "node_type": node_type,
            "domain": r.get("domain"),
            "name": r.get("name"),
            "similarity": similarity,
        }

        if node_type == "MediaScene":
            st = float(props.get("start_sec", 0.0))
            en = float(props.get("end_sec", 0.0))
            time_range_str = f"{format_timestamp(st)} - {format_timestamp(en)}"
            player_fragment = f"#t={st:.1f},{en:.1f}"
            source_file = props.get("source_file", "")
            thumbnail_path = props.get("thumbnail_path", "")
            transcript = props.get("transcript") or r.get("description", "")

            item.update({
                "title": r.get("name"),
                "time_range": time_range_str,
                "start_sec": st,
                "end_sec": en,
                "duration": props.get("duration", round(en - st, 2)),
                "player_url_fragment": player_fragment,
                "stream_url": f"/api/v1/knowledge/stream?path={source_file}{player_fragment}",
                "source_file": source_file,
                "thumbnail_path": thumbnail_path,
                "transcript": transcript,
                "media_type": props.get("media_type", "video"),
            })
        elif node_type == "TelegramMessage":
            msg_id = props.get("msg_id", r.get("id"))
            channel_name = props.get("channel_name", "")
            text_snippet = props.get("text") or r.get("description", "")
            timestamp = props.get("date", "")
            linked_media = props.get("referenced_media_files", [])

            item.update({
                "msg_id": msg_id,
                "channel_name": channel_name,
                "text_snippet": text_snippet,
                "timestamp": timestamp,
                "referenced_media": linked_media,
                "file_source": props.get("file_source", ""),
            })
        else:
            item.update({
                "description": r.get("description", ""),
                "properties": props
            })

        formatted.append(item)
    return formatted


def print_cli_results(results: list, query: str):
    """Prints results in human-readable CLI format."""
    print(f"\n==================================================")
    print(f" vazus SuperGraph OS — Multimodal Knowledge Chat")
    print(f" Query: '{query}' ({len(results)} matches found)")
    print(f"==================================================\n")

    if not results:
        print("No results found.")
        return

    for item in results:
        sim_pct = f"{item['similarity'] * 100:.1f}%"
        print(f"[{item['rank']}] [{item['node_type']}] {item['name']} (Match: {sim_pct})")
        print(f"    ID: {item['id']}")

        if item['node_type'] == "MediaScene":
            print(f"    Timestamp Range : {item['time_range']} ({item['start_sec']}s -> {item['end_sec']}s)")
            print(f"    Player Fragment : {item['player_url_fragment']}")
            print(f"    Source File     : {item['source_file']}")
            print(f"    Thumbnail Path  : {item['thumbnail_path']}")
            print(f"    Transcript      : {item['transcript'][:200]}...")
        elif item['node_type'] == "TelegramMessage":
            print(f"    Message ID      : {item['msg_id']}")
            print(f"    Channel Name    : {item['channel_name']}")
            print(f"    Timestamp       : {item['timestamp']}")
            if item.get("referenced_media"):
                print(f"    Linked Media    : {', '.join(item['referenced_media'])}")
            print(f"    Text Snippet    : {item['text_snippet'][:200]}...")
        else:
            print(f"    Description     : {item.get('description', '')[:200]}...")
        print("-" * 50)


def main():
    parser = argparse.ArgumentParser(
        description="vazus Multimodal Knowledge CLI Chat"
    )
    parser.add_argument(
        "--query", "-q",
        type=str,
        required=True,
        help="Search query text for 768D vector similarity search"
    )
    parser.add_argument(
        "--top-k", "-k",
        type=int,
        default=5,
        help="Maximum number of results to return (default: 5)"
    )
    parser.add_argument(
        "--db",
        type=str,
        default="C:/vazus/vazus.db",
        help="Path to vazus SQLite database (default: C:/vazus/vazus.db)"
    )
    parser.add_argument(
        "--domain", "-d",
        type=str,
        default="",
        help="Filter by domain or node_type (e.g. MediaScene, TelegramMessage, multimodal_av)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON array of search results"
    )

    args = parser.parse_args()

    embedder = UnifiedEmbeddingManager()
    raw_results = embedder.search_unified_vector_space(
        query=args.query,
        db_path=Path(args.db),
        top_k=args.top_k,
        domain_filter=args.domain if args.domain else None
    )

    formatted_results = process_search_results(raw_results)

    if args.json:
        print(json.dumps(formatted_results, indent=2, ensure_ascii=False))
    else:
        print_cli_results(formatted_results, args.query)

    sys.exit(0)


if __name__ == "__main__":
    main()
