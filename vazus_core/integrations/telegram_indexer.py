"""
vazus_core/telegram_indexer.py
SuperGraph Indexer for Telegram Messages & Discussion Threads (Milestone 2).
Parses Telegram exports (.jsonl and .md), resolves Q&A discussion thread trees,
maps media references to M1 MediaScene nodes, generates 768D Gemini vector embeddings,
and persists kg_nodes and kg_edges into SuperGraph SQLite databases.
"""

import os
import sys
import glob
import json
import re
import sqlite3
from typing import List, Dict, Any, Optional, Set, Tuple
from pathlib import Path


import threading

_EMBEDDING_MANAGER_CACHE = None
_EMBEDDING_LOCK = threading.Lock()


def get_embedding_manager():
    """Thread-safe lazy loader for UnifiedEmbeddingManager instance."""
    global _EMBEDDING_MANAGER_CACHE
    if _EMBEDDING_MANAGER_CACHE is None:
        with _EMBEDDING_LOCK:
            if _EMBEDDING_MANAGER_CACHE is None:
                from vazus_core.memory.embeddings import UnifiedEmbeddingManager
                _EMBEDDING_MANAGER_CACHE = UnifiedEmbeddingManager()
    return _EMBEDDING_MANAGER_CACHE


def make_channel_slug(channel_name: str) -> str:
    """Generates clean ASCII slug from channel/course name."""
    translit_map = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo', 'ж': 'zh',
        'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o',
        'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts',
        'ч': 'ch', 'ш': 'sh', 'щ': 'shch', 'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu',
        'я': 'ya'
    }
    s = channel_name.lower()
    res = []
    for char in s:
        if char in translit_map:
            res.append(translit_map[char])
        elif char.isalnum():
            res.append(char)
        else:
            res.append('_')
    slug = re.sub(r'_+', '_', ''.join(res)).strip('_')
    return slug or "channel"


def parse_jsonl_file(fpath: str) -> List[Dict[str, Any]]:
    """Parses a Telegram .jsonl export file into a list of normalized message dicts."""
    messages = []
    with open(fpath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            msg_id = data.get("id")
            if msg_id is None:
                continue

            try:
                msg_id = int(msg_id)
            except (ValueError, TypeError):
                continue

            sender = data.get("sender") or data.get("from") or data.get("author") or "Пользователь"
            if isinstance(sender, dict):
                sender = sender.get("name") or sender.get("first_name") or "Пользователь"
            sender = str(sender).strip() or "Пользователь"

            date = str(data.get("date", "")).strip()
            text = str(data.get("text") or data.get("caption") or "").strip()

            reply_id = data.get("reply_to_msg_id") or data.get("reply_to") or data.get("reply_to_message_id")
            if isinstance(reply_id, dict):
                reply_id = reply_id.get("reply_to_msg_id") or reply_id.get("message_id")
            if reply_id is not None:
                try:
                    reply_id = int(reply_id)
                except (ValueError, TypeError):
                    reply_id = None

            media = data.get("media") or data.get("photo") or data.get("video") or data.get("voice") or data.get("file") or data.get("document")

            messages.append({
                "msg_id": msg_id,
                "sender": sender,
                "date": date,
                "text": text,
                "reply_to_msg_id": reply_id,
                "raw_media": media,
                "file_source": fpath.replace('\\', '/')
            })

    return messages


def parse_md_file(fpath: str) -> List[Dict[str, Any]]:
    """Parses a Telegram .md export file into a list of normalized message dicts as fallback/supplement."""
    messages = []
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()

    # Split by message header delimiter "### 👤 "
    raw_blocks = re.split(r'\n(?=### 👤 )', content)
    for block in raw_blocks:
        block = block.strip()
        if not block.startswith("### 👤 "):
            continue

        # Header format: ### 👤 <Sender> (`<Date>`) [ID: <MsgID>]
        header_match = re.search(r'### 👤 (.*?) \(`(.*?)`\) \[ID:\s*(\d+)\]', block)
        if not header_match:
            continue

        sender = header_match.group(1).strip()
        date = header_match.group(2).strip()
        msg_id = int(header_match.group(3))

        # Body is everything after header line
        lines = block.split('\n')
        body_text = '\n'.join(lines[1:]).strip()
        # Remove separator line --- if present
        if body_text.endswith("---"):
            body_text = body_text[:-3].strip()

        # Check reply_to patterns in body text
        reply_id = None
        m_reply = re.search(r'\(в ответ на #?(\d+)\)', body_text, re.IGNORECASE)
        if m_reply:
            reply_id = int(m_reply.group(1))

        messages.append({
            "msg_id": msg_id,
            "sender": sender,
            "date": date,
            "text": body_text,
            "reply_to_msg_id": reply_id,
            "raw_media": None,
            "file_source": fpath.replace('\\', '/')
        })

    return messages


def build_media_index(
    courses_dir: str = "C:/vazus/knowledge/telegram_courses",
    target_dbs: Optional[List[str]] = None
) -> Tuple[Dict[str, List[str]], Dict[int, List[Tuple[str, str]]]]:
    """
    Builds lookup structures for media files and M1 MediaScene nodes.
    Returns:
      - scene_by_file: filename_lower -> list of scene_ids
      - media_by_msg_id: msg_id -> list of (target_id, filename)
    """
    scene_by_file: Dict[str, List[str]] = {}
    media_by_msg_id: Dict[int, List[Tuple[str, str]]] = {}

    if target_dbs is None:
        target_dbs = ["C:/vazus/services/memory/vazus.db", "C:/vazus/services/memory/vazus.db"]

    # Query existing MediaScene nodes from database
    for db_file in target_dbs:
        if not os.path.exists(db_file):
            continue
        try:
            conn = sqlite3.connect(db_file)
            cur = conn.cursor()
            tables = [t[0] for t in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
            if 'kg_nodes' in tables:
                rows = cur.execute("SELECT id, properties FROM kg_nodes WHERE domain='multimodal_av'").fetchall()
                for nid, props_str in rows:
                    p = json.loads(props_str) if props_str else {}
                    sf = p.get("source_file", "")
                    fn = os.path.basename(sf)
                    if fn:
                        fn_lower = fn.lower()
                        if nid not in scene_by_file.setdefault(fn_lower, []):
                            scene_by_file[fn_lower].append(nid)

                    m = re.search(r'(?:_msg|msg_|media_|video_msg|msg)(\d+)', fn, re.IGNORECASE)
                    if m:
                        msg_id = int(m.group(1))
                        item = (nid, fn)
                        if item not in media_by_msg_id.setdefault(msg_id, []):
                            media_by_msg_id[msg_id].append(item)
            conn.close()
        except Exception as e:
            sys.stderr.write(f"[TelegramIndexer] MediaScene index query note for {db_file}: {e}\n")

    # Scan physical media files in telegram_courses
    if os.path.exists(courses_dir):
        for root, _, files in os.walk(courses_dir):
            for f in files:
                if f.lower().endswith(('.mp4', '.m4a', '.mp3', '.oga', '.ogg', '.wav', '.mov', '.jpg', '.jpeg', '.png')):
                    m = re.search(r'(?:_msg|msg_|media_|video_msg|msg)(\d+)', f, re.IGNORECASE)
                    if m:
                        msg_id = int(m.group(1))
                        # Determine if scene_id exists for f, else fallback to media:<f>
                        f_lower = f.lower()
                        if f_lower in scene_by_file:
                            for sid in scene_by_file[f_lower]:
                                item = (sid, f)
                                if item not in media_by_msg_id.setdefault(msg_id, []):
                                    media_by_msg_id[msg_id].append(item)
                        else:
                            item = (f"media:{f}", f)
                            if item not in media_by_msg_id.setdefault(msg_id, []):
                                media_by_msg_id[msg_id].append(item)

    return scene_by_file, media_by_msg_id


def index_telegram_messages(
    messages_dir: str = "C:/vazus/knowledge/telegram_messages",
    db_path: str = "C:/vazus/services/memory/vazus.db"
) -> Dict[str, int]:
    """
    Parses all .jsonl and .md files in messages_dir, links Q&A discussion threads via reply_to_msg_id,
    maps media references to M1 MediaScene nodes, generates 768D Gemini vector embeddings,
    and inserts kg_nodes and kg_edges into SQLite SuperGraph databases.

    Returns summary dictionary with counts of processed files, indexed messages, channels,
    linked replies, media edges, and updated databases.
    """
    messages_dir = os.path.abspath(messages_dir).replace('\\', '/')
    db_path = os.path.abspath(db_path).replace('\\', '/')

    target_dbs = list(dict.fromkeys([
        db_path,
        "C:/vazus/services/memory/vazus.db",
        "C:/vazus/services/memory/vazus.db"
    ]))

    embedder = get_embedding_manager()

    # Pre-build media lookup index
    courses_dir = "C:/vazus/knowledge/telegram_courses"
    scene_by_file, media_by_msg_id = build_media_index(courses_dir, target_dbs)

    # 1. Discover all .jsonl and .md files in messages_dir
    jsonl_files = glob.glob(os.path.join(messages_dir, "*.jsonl"))
    md_files = glob.glob(os.path.join(messages_dir, "*.md"))
    all_files = jsonl_files + md_files

    # Group files by channel name (stem)
    channels_map: Dict[str, Dict[str, Optional[str]]] = {}
    for fpath in all_files:
        stem = os.path.splitext(os.path.basename(fpath))[0]
        ext = os.path.splitext(fpath)[1].lower()
        if stem not in channels_map:
            channels_map[stem] = {"jsonl": None, "md": None}
        if ext == ".jsonl":
            channels_map[stem]["jsonl"] = fpath
        elif ext == ".md":
            channels_map[stem]["md"] = fpath

    total_files_processed = len(all_files)
    total_channels_indexed = len(channels_map)
    total_messages_indexed = 0
    total_replies_linked = 0
    total_media_edges_linked = 0

    all_nodes_to_insert: List[Tuple[str, str, str, str, str, str, str, str]] = []
    all_edges_to_insert: List[Tuple[str, str, str, float, str]] = []

    # Process each channel dataset
    for channel_name, fpaths in channels_map.items():
        channel_slug = make_channel_slug(channel_name)
        channel_node_id = f"tg_channel_{channel_slug}"

        # Load raw messages from jsonl (primary) or md (fallback/supplement)
        channel_messages_dict: Dict[int, Dict[str, Any]] = {}

        if fpaths["jsonl"]:
            jsonl_msgs = parse_jsonl_file(fpaths["jsonl"])
            for m in jsonl_msgs:
                channel_messages_dict[m["msg_id"]] = m

        if fpaths["md"]:
            md_msgs = parse_md_file(fpaths["md"])
            for m in md_msgs:
                if m["msg_id"] not in channel_messages_dict:
                    channel_messages_dict[m["msg_id"]] = m
                else:
                    # Enrich reply_to_msg_id from md if missing in jsonl
                    if not channel_messages_dict[m["msg_id"]]["reply_to_msg_id"] and m["reply_to_msg_id"]:
                        channel_messages_dict[m["msg_id"]]["reply_to_msg_id"] = m["reply_to_msg_id"]

        # Sort messages chronologically ascending by msg_id
        sorted_msg_ids = sorted(channel_messages_dict.keys())
        channel_msgs = [channel_messages_dict[mid] for mid in sorted_msg_ids]

        # Build Q&A Thread Trees
        msgs_by_id: Dict[int, Dict[str, Any]] = {}

        for item in channel_msgs:
            msg_id = item["msg_id"]
            text = item["text"]
            parent_id = item["reply_to_msg_id"]

            # Fallback regex pattern checks if parent_id not set
            if parent_id is None and text:
                m1 = re.search(r'\[(?:ID|msg):\s*(\d+)\]', text, re.IGNORECASE)
                if m1:
                    parent_id = int(m1.group(1))
                else:
                    m2 = re.search(r'^(?:Re|Ответ на|в ответ на)\s*#?(\d+)', text, re.IGNORECASE)
                    if m2:
                        parent_id = int(m2.group(1))

            # Quoting fallback if text starts with >
            if parent_id is None and text.startswith(">"):
                quote_line = text.split("\n")[0].lstrip("> ").strip().lower()
                if len(quote_line) > 10:
                    for prev_id in reversed(sorted_msg_ids):
                        if prev_id >= msg_id:
                            continue
                        prev_item = msgs_by_id.get(prev_id)
                        if prev_item and quote_line[:30] in prev_item["text"].lower():
                            parent_id = prev_id
                            break

            item["parent_id"] = parent_id
            item["root_msg_id"] = msg_id
            item["reply_depth"] = 0
            item["is_thread_root"] = True

            if parent_id is not None and parent_id in msgs_by_id:
                parent_node = msgs_by_id[parent_id]
                item["is_thread_root"] = False
                item["root_msg_id"] = parent_node["root_msg_id"]
                item["reply_depth"] = parent_node["reply_depth"] + 1

                # Create REPLIES_TO Edge
                child_node_id = f"tg_msg_{channel_slug}_{msg_id}"
                parent_node_id = f"tg_msg_{channel_slug}_{parent_id}"
                edge_props = json.dumps({"reply_to_msg_id": parent_id}, ensure_ascii=False)
                all_edges_to_insert.append((child_node_id, parent_node_id, "REPLIES_TO", 1.0, edge_props))
                total_replies_linked += 1

            msgs_by_id[msg_id] = item

        # Create Channel Container Node
        channel_desc = f"Telegram channel / course discussion: {channel_name}"
        channel_props = json.dumps({
            "channel_name": channel_name,
            "channel_slug": channel_slug,
            "total_messages": len(channel_msgs)
        }, ensure_ascii=False)
        channel_emb = embedder.get_embedding(channel_name)
        channel_tags = f"telegram,channel,{channel_slug}"

        all_nodes_to_insert.append((
            channel_node_id,
            channel_name,
            "telegram_discussion",
            "TelegramChannel",
            channel_desc,
            channel_tags,
            channel_props,
            json.dumps(channel_emb)
        ))

        # Process Message Nodes and Media Edges
        for item in channel_msgs:
            msg_id = item["msg_id"]
            sender = item["sender"]
            date = item["date"]
            text = item["text"]
            msg_node_id = f"tg_msg_{channel_slug}_{msg_id}"

            # Check media references
            referenced_media_targets: List[Tuple[str, str]] = []
            if msg_id in media_by_msg_id:
                for target_id, fn in media_by_msg_id[msg_id]:
                    referenced_media_targets.append((target_id, fn))

            # Also check raw_media if present
            raw_media = item.get("raw_media")
            if isinstance(raw_media, str) and raw_media:
                fn = os.path.basename(raw_media)
                fn_lower = fn.lower()
                if fn_lower in scene_by_file:
                    for sid in scene_by_file[fn_lower]:
                        referenced_media_targets.append((sid, fn))
                else:
                    referenced_media_targets.append((f"media:{fn}", fn))

            # Deduplicate referenced media targets
            unique_media_targets = list(dict.fromkeys(referenced_media_targets))
            referenced_media_files = [fn for _, fn in unique_media_targets]

            # Create REFERENCES_MEDIA edges
            for target_id, fn in unique_media_targets:
                media_edge_props = json.dumps({
                    "media_file": fn,
                    "channel": channel_name,
                    "match_rule": "msg_id"
                }, ensure_ascii=False)
                all_edges_to_insert.append((msg_node_id, target_id, "REFERENCES_MEDIA", 1.0, media_edge_props))
                total_media_edges_linked += 1

            # Create BELONGS_TO edge
            belongs_props = json.dumps({"channel_name": channel_name}, ensure_ascii=False)
            all_edges_to_insert.append((msg_node_id, channel_node_id, "BELONGS_TO", 1.0, belongs_props))

            # Build Message Node
            node_name = f"Message #{msg_id} by {sender} ({date})"
            description_snippet = text[:500]
            tags = f"telegram,discussion,{channel_slug}"

            node_props = json.dumps({
                "msg_id": msg_id,
                "channel_name": channel_name,
                "channel_slug": channel_slug,
                "sender": sender,
                "date": date,
                "text": text,
                "reply_to_msg_id": item["parent_id"],
                "root_msg_id": item["root_msg_id"],
                "reply_depth": item["reply_depth"],
                "has_media": bool(referenced_media_files),
                "referenced_media_files": referenced_media_files,
                "file_source": item["file_source"]
            }, ensure_ascii=False)

            formatted_prompt = f"[{channel_name}] Message #{msg_id} by {sender} ({date}):\n{text}"
            msg_emb = embedder.get_embedding(formatted_prompt)

            all_nodes_to_insert.append((
                msg_node_id,
                node_name,
                "telegram_discussion",
                "TelegramMessage",
                description_snippet,
                tags,
                node_props,
                json.dumps(msg_emb)
            ))

            total_messages_indexed += 1

    # Persist kg_nodes and kg_edges into SQLite databases
    updated_dbs = []
    for db_target in target_dbs:
        db_dir = os.path.dirname(db_target)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        conn = sqlite3.connect(db_target)
        cur = conn.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS kg_nodes (
            id TEXT PRIMARY KEY,
            name TEXT,
            domain TEXT,
            node_type TEXT,
            description TEXT,
            tags TEXT,
            properties TEXT,
            embedding_json TEXT
        );
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS kg_edges (
            source_id TEXT,
            target_id TEXT,
            relation TEXT,
            strength REAL,
            properties TEXT,
            PRIMARY KEY (source_id, target_id, relation)
        );
        """)

        # Execute batch inserts
        cur.executemany("""
        INSERT OR REPLACE INTO kg_nodes (
            id, name, domain, node_type, description, tags, properties, embedding_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, all_nodes_to_insert)

        cur.executemany("""
        INSERT OR REPLACE INTO kg_edges (
            source_id, target_id, relation, strength, properties
        ) VALUES (?, ?, ?, ?, ?)
        """, all_edges_to_insert)

        conn.commit()
        conn.close()
        updated_dbs.append(db_target)

    return {
        "total_files_processed": total_files_processed,
        "total_messages_indexed": total_messages_indexed,
        "total_channels_indexed": total_channels_indexed,
        "total_replies_linked": total_replies_linked,
        "total_media_edges_linked": total_media_edges_linked,
        "databases_updated": len(updated_dbs)
    }


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8')
    print("Testing Telegram SuperGraph Indexer...")
    res = index_telegram_messages()
    print("Indexing Complete!")
    print(json.dumps(res, indent=2, ensure_ascii=False))
