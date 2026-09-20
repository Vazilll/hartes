"""
vazus_core/telegram_indexer.py
SuperGraph Indexer for Telegram Messages & Discussion Threads (Milestone 2).
Parses Telegram exports (.jsonl and .md), resolves Q&A discussion thread trees,
maps media references to M1 MediaScene nodes, generates 768D Gemini vector embeddings,
and persists kg_nodes and kg_edges into SuperGraph SQLite databases.
"""

import logging
import os
import sys
import glob
import json
import re
import sqlite3
from typing import List, Dict, Any, Optional, Tuple

import threading

logger = logging.getLogger("telegram_indexer")

DEFAULT_COURSES_DIR = os.environ.get("VAZUS_COURSES_DIR", r"C:\Users\Vaz\Videos\Courses")

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
            except json.JSONDecodeError as json_err:
                logger.debug("Failed to decode jsonl line: %s", json_err)
                continue

            msg_id = data.get("id")
            if msg_id is None:
                continue

            try:
                msg_id = int(msg_id)
            except (ValueError, TypeError) as parse_err:
                logger.debug("Failed to parse msg_id %s: %s", msg_id, parse_err)
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


def _query_db_media_scenes(
    db_file: str, scene_by_file: Dict[str, List[str]], media_by_msg_id: Dict[int, List[Tuple[str, str]]]
) -> None:
    if not os.path.exists(db_file):
        return
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
        logger.debug("MediaScene index query note for %s: %s", db_file, e)


def _scan_courses_media_files(
    courses_dir: str, scene_by_file: Dict[str, List[str]], media_by_msg_id: Dict[int, List[Tuple[str, str]]]
) -> None:
    if not os.path.exists(courses_dir):
        return
    media_exts = ('.mp4', '.m4a', '.mp3', '.oga', '.ogg', '.wav', '.mov', '.jpg', '.jpeg', '.png')
    for root, _, files in os.walk(courses_dir):
        for f in files:
            if f.lower().endswith(media_exts):
                m = re.search(r'(?:_msg|msg_|media_|video_msg|msg)(\d+)', f, re.IGNORECASE)
                if m:
                    msg_id = int(m.group(1))
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


def build_media_index(
    courses_dir: Optional[str] = None,
    target_dbs: Optional[List[str]] = None
) -> Tuple[Dict[str, List[str]], Dict[int, List[Tuple[str, str]]]]:
    """Builds lookup structures for media files and M1 MediaScene nodes."""
    if courses_dir is None:
        courses_dir = DEFAULT_COURSES_DIR
    scene_by_file: Dict[str, List[str]] = {}
    media_by_msg_id: Dict[int, List[Tuple[str, str]]] = {}

    if target_dbs is None:
        target_dbs = ["C:/vazus/services/memory/vazus.db"]

    for db_file in target_dbs:
        _query_db_media_scenes(db_file, scene_by_file, media_by_msg_id)

    _scan_courses_media_files(courses_dir, scene_by_file, media_by_msg_id)
    return scene_by_file, media_by_msg_id


def _load_channel_messages(fpaths: Dict[str, Optional[str]]) -> List[Dict[str, Any]]:
    """Loads raw messages from jsonl (primary) or md (fallback/supplement)."""
    channel_messages_dict: Dict[int, Dict[str, Any]] = {}
    if fpaths["jsonl"]:
        for m in parse_jsonl_file(fpaths["jsonl"]):
            channel_messages_dict[m["msg_id"]] = m
    if fpaths["md"]:
        for m in parse_md_file(fpaths["md"]):
            if m["msg_id"] not in channel_messages_dict:
                channel_messages_dict[m["msg_id"]] = m
            elif not channel_messages_dict[m["msg_id"]]["reply_to_msg_id"] and m["reply_to_msg_id"]:
                channel_messages_dict[m["msg_id"]]["reply_to_msg_id"] = m["reply_to_msg_id"]
    sorted_msg_ids = sorted(channel_messages_dict.keys())
    return [channel_messages_dict[mid] for mid in sorted_msg_ids]


def _resolve_thread_trees(
    channel_msgs: List[Dict[str, Any]],
    channel_slug: str,
    *,
    all_edges_to_insert: List[Tuple[str, str, str, float, str]]
) -> int:
    """Builds Q&A thread trees and inserts REPLIES_TO edges."""
    msgs_by_id: Dict[int, Dict[str, Any]] = {}
    sorted_msg_ids = [m["msg_id"] for m in channel_msgs]
    replies_linked = 0

    for item in channel_msgs:
        msg_id, text, parent_id = item["msg_id"], item["text"], item["reply_to_msg_id"]
        if parent_id is None and text:
            m1 = re.search(r'\[(?:ID|msg):\s*(\d+)\]', text, re.IGNORECASE)
            if m1:
                parent_id = int(m1.group(1))
            else:
                m2 = re.search(r'^(?:Re|Ответ на|в ответ на)\s*#?(\d+)', text, re.IGNORECASE)
                if m2:
                    parent_id = int(m2.group(1))

        if parent_id is None and text.startswith(">"):
            quote_line = text.split("\n")[0].lstrip("> ").strip().lower()
            if len(quote_line) > 10:
                for prev_id in reversed(sorted_msg_ids):
                    if prev_id < msg_id and prev_id in msgs_by_id:
                        if quote_line[:30] in msgs_by_id[prev_id]["text"].lower():
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

            child_node_id = f"tg_msg_{channel_slug}_{msg_id}"
            parent_node_id = f"tg_msg_{channel_slug}_{parent_id}"
            edge_props = json.dumps({"reply_to_msg_id": parent_id}, ensure_ascii=False)
            all_edges_to_insert.append((child_node_id, parent_node_id, "REPLIES_TO", 1.0, edge_props))
            replies_linked += 1

        msgs_by_id[msg_id] = item
    return replies_linked


def _build_media_targets_for_msg(
    item: Dict[str, Any],
    msg_id: int,
    *,
    media_by_msg_id: Dict[int, List[Tuple[str, str]]],
    scene_by_file: Dict[str, List[str]]
) -> List[Tuple[str, str]]:
    """Gathers referenced media targets for a single message."""
    referenced_media_targets: List[Tuple[str, str]] = []
    if msg_id in media_by_msg_id:
        for target_id, fn in media_by_msg_id[msg_id]:
            referenced_media_targets.append((target_id, fn))

    raw_media = item.get("raw_media")
    if isinstance(raw_media, str) and raw_media:
        fn = os.path.basename(raw_media)
        fn_lower = fn.lower()
        if fn_lower in scene_by_file:
            for sid in scene_by_file[fn_lower]:
                referenced_media_targets.append((sid, fn))
        else:
            referenced_media_targets.append((f"media:{fn}", fn))

    return list(dict.fromkeys(referenced_media_targets))


def _process_single_message(
    item: Dict[str, Any],
    channel_name: str,
    channel_slug: str,
    channel_node_id: str,
    *,
    media_by_msg_id: Dict[int, List[Tuple[str, str]]],
    scene_by_file: Dict[str, List[str]],
    embedder: Any,
    all_nodes_to_insert: list,
    all_edges_to_insert: list
) -> int:
    """Processes a single Telegram message into node and edge records."""
    msg_id, sender, date, text = item["msg_id"], item["sender"], item["date"], item["text"]
    msg_node_id = f"tg_msg_{channel_slug}_{msg_id}"

    unique_media_targets = _build_media_targets_for_msg(
        item, msg_id, media_by_msg_id=media_by_msg_id, scene_by_file=scene_by_file
    )
    referenced_media_files = [fn for _, fn in unique_media_targets]

    for target_id, fn in unique_media_targets:
        media_edge_props = json.dumps({"media_file": fn, "channel": channel_name, "match_rule": "msg_id"}, ensure_ascii=False)
        all_edges_to_insert.append((msg_node_id, target_id, "REFERENCES_MEDIA", 1.0, media_edge_props))

    belongs_props = json.dumps({"channel_name": channel_name}, ensure_ascii=False)
    all_edges_to_insert.append((msg_node_id, channel_node_id, "BELONGS_TO", 1.0, belongs_props))

    node_props = json.dumps({
        "msg_id": msg_id, "channel_name": channel_name, "channel_slug": channel_slug,
        "sender": sender, "date": date, "text": text,
        "reply_to_msg_id": item["parent_id"], "root_msg_id": item["root_msg_id"],
        "reply_depth": item["reply_depth"], "has_media": bool(referenced_media_files),
        "referenced_media_files": referenced_media_files, "file_source": item["file_source"]
    }, ensure_ascii=False)

    formatted_prompt = f"[{channel_name}] Message #{msg_id} by {sender} ({date}):\n{text}"
    msg_emb = embedder.get_embedding(formatted_prompt)

    all_nodes_to_insert.append((
        msg_node_id, f"Message #{msg_id} by {sender} ({date})",
        "telegram_discussion", "TelegramMessage",
        text[:500], f"telegram,discussion,{channel_slug}",
        node_props, json.dumps(msg_emb)
    ))
    return len(unique_media_targets)


def _persist_kg_batch(
    target_dbs: List[str],
    all_nodes_to_insert: list,
    all_edges_to_insert: list
) -> int:
    """Executes batch inserts into target SuperGraph SQLite databases."""
    from vazus_core.analysis.kg_schema import ensure_kg_schema
    updated_count = 0
    for db_target in target_dbs:
        db_dir = os.path.dirname(db_target)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        with sqlite3.connect(db_target) as conn:
            cur = conn.cursor()
            ensure_kg_schema(cur)
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
        updated_count += 1
    return updated_count


def index_telegram_messages(
    messages_dir: str = "C:/vazus/knowledge/telegram_messages",
    db_path: str = "C:/vazus/services/memory/vazus.db"
) -> Dict[str, int]:
    """Parses .jsonl/.md files, links Q&A discussion threads, and persists kg_nodes/kg_edges."""
    messages_dir = os.path.abspath(messages_dir).replace('\\', '/')
    db_path = os.path.abspath(db_path).replace('\\', '/')
    target_dbs = list(dict.fromkeys([db_path, "C:/vazus/services/memory/vazus.db"]))

    embedder = get_embedding_manager()
    courses_dir = DEFAULT_COURSES_DIR
    scene_by_file, media_by_msg_id = build_media_index(courses_dir, target_dbs)

    all_files = glob.glob(os.path.join(messages_dir, "*.jsonl")) + glob.glob(os.path.join(messages_dir, "*.md"))
    channels_map: Dict[str, Dict[str, Optional[str]]] = {}
    for fpath in all_files:
        stem = os.path.splitext(os.path.basename(fpath))[0]
        ext = os.path.splitext(fpath)[1].lower()
        if stem not in channels_map:
            channels_map[stem] = {"jsonl": None, "md": None}
        channels_map[stem]["jsonl" if ext == ".jsonl" else "md"] = fpath

    all_nodes_to_insert: List[Tuple[str, str, str, str, str, str, str, str]] = []
    all_edges_to_insert: List[Tuple[str, str, str, float, str]] = []
    tot_msgs, tot_replies, tot_media_edges = 0, 0, 0

    for channel_name, fpaths in channels_map.items():
        channel_slug = make_channel_slug(channel_name)
        channel_node_id = f"tg_channel_{channel_slug}"
        channel_msgs = _load_channel_messages(fpaths)

        tot_replies += _resolve_thread_trees(channel_msgs, channel_slug, all_edges_to_insert=all_edges_to_insert)

        channel_desc = f"Telegram channel / course discussion: {channel_name}"
        channel_props = json.dumps({"channel_name": channel_name, "channel_slug": channel_slug, "total_messages": len(channel_msgs)}, ensure_ascii=False)
        channel_emb = embedder.get_embedding(channel_name)

        all_nodes_to_insert.append((
            channel_node_id, channel_name, "telegram_discussion", "TelegramChannel",
            channel_desc, f"telegram,channel,{channel_slug}", channel_props, json.dumps(channel_emb)
        ))

        for item in channel_msgs:
            med_count = _process_single_message(
                item, channel_name, channel_slug, channel_node_id,
                media_by_msg_id=media_by_msg_id, scene_by_file=scene_by_file,
                embedder=embedder, all_nodes_to_insert=all_nodes_to_insert,
                all_edges_to_insert=all_edges_to_insert
            )
            tot_media_edges += med_count
            tot_msgs += 1

    updated_count = _persist_kg_batch(target_dbs, all_nodes_to_insert, all_edges_to_insert)
    return {
        "total_files_processed": len(all_files),
        "total_messages_indexed": tot_msgs,
        "total_channels_indexed": len(channels_map),
        "total_replies_linked": tot_replies,
        "total_media_edges_linked": tot_media_edges,
        "databases_updated": updated_count
    }


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8')
    print("Testing Telegram SuperGraph Indexer...")
    res = index_telegram_messages()
    print("Indexing Complete!")
    print(json.dumps(res, indent=2, ensure_ascii=False))
