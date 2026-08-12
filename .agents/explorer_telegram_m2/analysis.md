# Analysis Report: Telegram Messages & Discussion Threads Indexer (Milestone 2)

**Author**: Explorer Agent (`explorer_telegram_m2`)  
**Target Milestone**: Milestone 2 — Telegram Messages & Discussions SuperGraph Indexer  
**Working Directory**: `C:\vazus\.agents\explorer_telegram_m2`  
**Date**: 2026-07-24  

---

## 1. Executive Summary

This investigation analyzed the Telegram dataset located in `C:\vazus\knowledge\telegram_messages` to design the architecture, schema mapping, thread parsing, media alignment, and module API for `C:\vazus\vazus_core\telegram_indexer.py`.

Key discoveries:
1. **Dataset Overview**: The dataset consists of 5 pairs of `.jsonl` and `.md` files (10 files total), containing **4,906 Telegram messages** across 5 distinct channels/courses.
2. **JSON Schema & Compatibility**: Existing `.jsonl` exports use schema `{"id": int, "date": str, "sender": str, "text": str}`. To handle standard and custom Telegram exports, `telegram_indexer.py` must support both `sender` and `from`/`from_id` fields, as well as `reply_to_msg_id`/`reply_to` and explicit media fields (`media`, `photo`, `video`, `voice`).
3. **Q&A Thread Tree Parsing**: Thread relationships are parsed via explicit `reply_to_msg_id` values when present, supplemented by regex heuristics (`[ID: ...]`, `Re: #...`, `> blockquotes`). Messages are structured into parent-child Q&A trees with calculated `reply_depth` and `root_msg_id`.
4. **Media Cross-Linking**: 420 media files exist in `C:\vazus\knowledge\telegram_courses`, of which 244 contain message IDs in their filenames (e.g. `_msg19.mp4`, `msg_104_record.mp4`, `media_174.oga`). `TelegramMessage` graph nodes link to M1 `MediaScene` nodes and media files via `REFERENCES_MEDIA` graph edges.
5. **768D Vector Embedding Alignment**: Each message's text is formatted into a structured prompt (`"<sender> (<date>) in <channel>: <text>"`) and embedded into a 768-dimensional vector space using `UnifiedEmbeddingManager` (Google Gemini Embedding 2 with 768D fallback).
6. **SQLite SuperGraph Mapping**: Nodes are written to `kg_nodes` with `domain='telegram_discussion'` and `node_type='TelegramMessage'` (plus `TelegramChannel` container nodes). Edges are written to `kg_edges` with relations `REPLIES_TO`, `BELONGS_TO`, and `REFERENCES_MEDIA`.

---

## 2. Dataset & File Structure Inspection

### 2.1 File Catalog (`C:\vazus\knowledge\telegram_messages`)

| File Name | File Type | Message Count | Unique Senders | ID Range | Date Range |
|---|---|---|---|---|---|
| `Общий чат _Покоритель Наташек 6_0_` | `.jsonl` / `.md` | 4,545 | 92 senders | 187656 – 192979 | 2025-11-23 to 2026-05-13 |
| `Курс _Покоритель Наташек 6_0_` | `.jsonl` / `.md` | 124 | 1 sender ("Пользователь") | 6 – 200 | 2025-07-18 to 2026-07-23 |
| `ФУНКЦИОНАЛЬНАЯ МАШИНА _ Канал курса` | `.jsonl` / `.md` | 93 | 1 sender ("Пользователь") | 6 – 169 | 2026-03-21 to 2026-04-30 |
| `Спринт _Забыть бывшую_` | `.jsonl` / `.md` | 73 | 1 sender ("Пользователь") | 5 – 133 | 2022-11-18 to 2026-05-10 |
| `СЕКРЕТНАЯ БАЗА С БОНУСАМИ` | `.jsonl` / `.md` | 71 | 1 sender ("Пользователь") | 12 – 140 | 2025-06-19 to 2026-07-23 |
| **Total** | **10 files** | **4,906 msgs** | **92+ senders** | — | **2022 – 2026** |

### 2.2 Schema Breakdown

#### Primary `.jsonl` Record Format:
```json
{
  "id": 192979,
  "date": "2026-05-13 11:20:12",
  "sender": "Pavel",
  "text": "Вот такие буфера закинула баба в личку нашему самому старому ученику..."
}
```

#### Supported Extended Telegram Export Fields:
To ensure maximum compatibility with official Telegram Desktop JSON exports and Telethon/Pyrogram scraper dumps, `telegram_indexer.py` must normalize and parse the following fields:
- `id` (int/str): Unique message identifier.
- `date` (str): Timestamp string (`YYYY-MM-DD HH:MM:SS` or ISO 8601).
- `sender` / `from` / `from_id` / `author` (str/dict): Author name or user object. Normalized to `sender_name: str`.
- `text` / `caption` (str): Text content. Normalized to `text_content: str`.
- `reply_to_msg_id` / `reply_to` / `reply_to_message_id` (int/dict): Message ID of parent message being replied to.
- `media` / `photo` / `video` / `voice` / `file` / `document` (dict/str): Attached media object or file path.

---

## 3. Discussion Thread & Q&A Tree Parsing Strategy

### 3.1 Parent-Child Thread Resolution
1. **Explicit Reply ID**: If `reply_to_msg_id` (or `reply_to`) is present in the message JSON:
   - Extract `parent_id = int(data['reply_to_msg_id'])`.
2. **Regex & Quoting Heuristics (Fallback)**:
   - Pattern 1: `\[(?:ID|msg):\s*(\d+)\]` (e.g. `[ID: 192800]`)
   - Pattern 2: `^(?:Re|Ответ на|в ответ на)\s*#?(\d+)` (e.g. `Re: #192800`)
   - Pattern 3: Blockquote analysis (`> ...`). If text starts with `>` quote, attempt fuzzy match against recent preceding messages in the same channel within 50 messages window.

### 3.2 Thread Tree Construction Algorithm
For each channel dataset:
1. Load all messages and sort by `id` ascending (chronological order).
2. Build lookup dictionary `msgs_by_id[msg_id] = msg_node`.
3. Track roots and depths:
   - If message has no valid `parent_id` (or parent not found in channel), set:
     - `is_thread_root = True`
     - `root_msg_id = msg_id`
     - `reply_depth = 0`
   - If message has valid `parent_id`:
     - `parent = msgs_by_id[parent_id]`
     - `is_thread_root = False`
     - `root_msg_id = parent.root_msg_id`
     - `reply_depth = parent.reply_depth + 1`
     - Append `msg_id` to `parent.child_ids`.
4. Graph edge creation:
   - Insert `REPLIES_TO` edge from `child_node_id` -> `parent_node_id`.

---

## 4. Media References & Milestone 1 Alignment Strategy

### 4.1 Media Filename & Message ID Correlation
In `C:\vazus\knowledge\telegram_courses`, media files follow naming conventions encoding message IDs:
- Pattern `_msg<ID>`: `2025-07-22 00-42-20_msg19.mp4` -> Message ID 19
- Pattern `msg_<ID>`: `msg_104_record.mp4` -> Message ID 104
- Pattern `media_<ID>`: `media_174.oga` -> Message ID 174
- Pattern `IMG_..._msg<ID>`: `IMG_4402_msg127.MOV` -> Message ID 127
- Pattern `video_msg<ID>`: `video_msg62.mp4` -> Message ID 62

**Observation**: 244 media files directly match Telegram message IDs in `telegram_courses` subdirectories.

### 4.2 SuperGraph Edge `REFERENCES_MEDIA`
When a message `tg_msg_<channel_slug>_<msg_id>` has matching media files:
1. Find all M1 `MediaScene` nodes in `kg_nodes` where `domain='multimodal_av'` and `source_file` contains the media filename or `msg_<id>`.
2. Insert `REFERENCES_MEDIA` graph edge in `kg_edges`:
   - `source_id`: `tg_msg_<channel_slug>_<msg_id>`
   - `target_id`: `scene_id` (e.g. `scene_34f2e3fa38e2`) or fallback media node `media:<filename>`
   - `relation`: `'REFERENCES_MEDIA'`
   - `strength`: `1.0`
   - `properties`: `{"media_file": filename, "channel": channel_name, "match_rule": "msg_id"}`

---

## 5. 768D Vector Embedding & SuperGraph Schema Mapping

### 5.1 Text Prompt Formatting for Embedding
To maximize semantic search precision in `vazus.db`, raw message text is pre-formatted before vector embedding generation:
```python
formatted_prompt = f"[{channel_name}] Message #{msg_id} by {sender} ({date}):\n{text_content}"
embedding_768d = embedder.get_embedding(formatted_prompt)
```

### 5.2 SQLite Table `kg_nodes` Schema Mapping
- `id` (TEXT PRIMARY KEY): `tg_msg_<channel_slug>_<msg_id>` (e.g. `tg_msg_obshtii_chat_192979`)
- `name` (TEXT): `Message #<msg_id> by <sender> (<date>)`
- `domain` (TEXT): `'telegram_discussion'`
- `node_type` (TEXT): `'TelegramMessage'`
- `description` (TEXT): Text content snippet (truncated to 500 chars for summary readability)
- `tags` (TEXT): `"telegram,discussion,<channel_slug>"`
- `properties` (TEXT JSON):
  ```json
  {
    "msg_id": 192979,
    "channel_name": "Общий чат _Покоритель Наташек 6_0_",
    "channel_slug": "obshtii_chat_pokoritel_natashek_6_0",
    "sender": "Pavel",
    "date": "2026-05-13 11:20:12",
    "text": "...",
    "reply_to_msg_id": 192975,
    "root_msg_id": 192905,
    "reply_depth": 1,
    "has_media": false,
    "referenced_media_files": [],
    "file_source": "C:/vazus/knowledge/telegram_messages/Общий чат _Покоритель Наташек 6_0_.jsonl"
  }
  ```
- `embedding_json` (TEXT JSON): `"[0.012, -0.045, ... 768 float values]"`

### 5.3 Container Nodes (`TelegramChannel`)
Each `.jsonl` file creates a channel container node:
- `id`: `tg_channel_<channel_slug>`
- `name`: `<channel_name>`
- `domain`: `'telegram_discussion'`
- `node_type`: `'TelegramChannel'`
- `description`: `Telegram channel / course discussion: <channel_name>`
- `tags`: `"telegram,channel"`
- `properties`: `{"channel_name": "...", "total_messages": N}`
- `embedding_json`: 768D vector embedding of channel name.

### 5.4 SQLite Table `kg_edges` Schema Mapping

| Relation | Source Node (`source_id`) | Target Node (`target_id`) | Relation Type | Properties JSON |
|---|---|---|---|---|
| `REPLIES_TO` | `tg_msg_<channel_slug>_<child_id>` | `tg_msg_<channel_slug>_<parent_id>` | `REPLIES_TO` | `{"reply_to_msg_id": parent_id}` |
| `BELONGS_TO` | `tg_msg_<channel_slug>_<msg_id>` | `tg_channel_<channel_slug>` | `BELONGS_TO` | `{"channel_name": channel_name}` |
| `REFERENCES_MEDIA` | `tg_msg_<channel_slug>_<msg_id>` | `scene_<hash>` / `media:<filename>` | `REFERENCES_MEDIA` | `{"media_file": filename}` |

---

## 6. `vazus_core/telegram_indexer.py` Module API Specification

### Function Signature:
```python
def index_telegram_messages(
    messages_dir: str = "C:/vazus/knowledge/telegram_messages",
    db_path: str = "C:/vazus/services/memory/vazus.db"
) -> Dict[str, int]:
    """
    Parses all .jsonl (and .md) files in messages_dir, links Q&A discussion threads via reply_to_msg_id,
    maps media references to M1 MediaScene nodes, generates 768D Gemini vector embeddings,
    and inserts kg_nodes and kg_edges into SQLite databases (services/memory/vazus.db & vazus.db).

    Returns summary dictionary with counts of processed files, indexed messages, channels,
    linked replies, media edges, and updated databases.
    """
```

### Return Structure:
```python
{
    "total_files_processed": 5,
    "total_messages_indexed": 4906,
    "total_channels_indexed": 5,
    "total_replies_linked": 0,
    "total_media_edges_linked": 244,
    "databases_updated": 2
}
```

---

## 7. Next Steps for Implementer

1. Create `C:\vazus\vazus_core\telegram_indexer.py` implementing `index_telegram_messages(...)` and CLI entry point `scripts/index_telegram.py`.
2. Verify indexing on `C:\vazus\services\memory\vazus.db` and `C:\vazus\vazus.db`.
3. Confirm vector similarity search works across indexed Telegram messages.
