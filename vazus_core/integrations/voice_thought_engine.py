"""
vazus_core.integrations.voice_thought_engine
SOTA Voice-to-Knowledge Pipeline (Thought-to-Memory) for Vazus SuperGraph OS.
Transcribes audio streams using local faster-whisper, extracts structured semantic metadata,
generates Obsidian-compatible Markdown notes with YAML frontmatter, and indexes into 768D vector memory.
"""

import hashlib
import json
import logging
import re
import sys
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception as exc:
        logger.debug("Failed stdout reconfigure: %s", exc)

from vazus_core.engine.config import settings
from vazus_core.memory.db import get_db_connection
from vazus_core.memory.embeddings import get_embedding

DEFAULT_WHISPER_PATH = Path("/home/tarhes/Проекты/vazus/services/memory/knowledge/.whisper_cache/models--mobiuslabsgmbh--faster-whisper-large-v3-turbo/snapshots/0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf")


def _sanitize_filename(title: str) -> str:
    """Sanitizes note title into a valid cross-platform filename."""
    cleaned = re.sub(r'[\\/*?:"<>|]', "", title)
    cleaned = re.sub(r"\s+", "_", cleaned).strip("_. ")
    return cleaned[:64] if cleaned else "voice_thought"


def _extract_tags_from_text(text: str) -> List[str]:
    """Extracts hashtags and domain tags from text."""
    found = re.findall(r"#([a-zA-Zа-яА-Я0-9_]+)", text)
    tags = [t.lower() for t in found]
    if "voice_thought" not in tags:
        tags.insert(0, "voice_thought")
    return list(dict.fromkeys(tags))


def _extract_wikilinks_from_text(text: str) -> List[str]:
    """Extracts [[Wikilinks]] from text."""
    return re.findall(r"\[\[(.*?)\]\]", text)


def _derive_thought_title(cleaned: str, custom_title: Optional[str] = None) -> str:
    """Derives concise note title from custom title, first line, or timestamp."""
    if custom_title:
        return custom_title
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    if lines:
        first_line = lines[0]
        return first_line[:50] + ("..." if len(first_line) > 50 else "")
    return f"Голосовая заметка {time.strftime('%Y-%m-%d %H:%M')}"


def _detect_action_items(cleaned: str) -> List[str]:
    """Detects action items and tasks from speech sentences."""
    action_items = []
    sentences = [s.strip() for s in re.split(r"[.\n;!?]+", cleaned) if s.strip()]
    for sentence in sentences:
        if re.search(r"\b(нужно|надо|сделать|задача|дедлайн|купить|отправить|исправить)\b", sentence, re.IGNORECASE):
            action_items.append(sentence.lstrip("- *•").strip())
    return action_items


class VoiceThoughtEngine:
    """End-to-end voice transcription and organic memory indexing engine."""

    def __init__(
        self,
        db_path: Optional[str] = None,
        model_path: Optional[str] = None,
        wiki_dir: Optional[str] = None,
    ):
        self.db_path = str(db_path or settings.VAZUS_DB_PATH)
        self.model_path = str(model_path or DEFAULT_WHISPER_PATH)
        self.wiki_dir = Path(wiki_dir or str(settings.WIKI_DIR))
        self.wiki_dir.mkdir(parents=True, exist_ok=True)
        self._model = None

    def _get_model(self):
        """Lazy-loads faster-whisper model with fallback handling."""
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
                if Path(self.model_path).exists():
                    self._model = WhisperModel(self.model_path, device="cpu", compute_type="int8")
                else:
                    self._model = WhisperModel("tiny", device="cpu", compute_type="int8")
            except Exception as e:
                self._model = f"FALLBACK_UNAVAILABLE: {e}"
        return self._model

    def transcribe_audio(self, audio_path: str) -> Dict[str, Any]:
        """Transcribes audio file to plain text with timestamps and language detection."""
        p = Path(audio_path)
        if not p.exists():
            return {"status": "ERROR", "text": "", "error": f"File not found: {audio_path}"}

        model = self._get_model()
        if isinstance(model, str) and model.startswith("FALLBACK_UNAVAILABLE"):
            return {
                "status": "FALLBACK",
                "text": f"Raw audio received: {p.name}",
                "language": "ru",
                "segments": [],
            }

        try:
            segments, info = model.transcribe(str(p), beam_size=5, language="ru")
            seg_list = []
            full_text_chunks = []
            for seg in segments:
                seg_list.append({"start": seg.start, "end": seg.end, "text": seg.text.strip()})
                full_text_chunks.append(seg.text.strip())

            full_text = " ".join(full_text_chunks).strip()
            return {
                "status": "SUCCESS",
                "text": full_text,
                "language": info.language if hasattr(info, "language") else "ru",
                "duration": info.duration if hasattr(info, "duration") else 0.0,
                "segments": seg_list,
            }
        except Exception as err:
            return {"status": "ERROR", "text": "", "error": str(err)}

    def extract_structured_thought(self, raw_text: str, custom_title: Optional[str] = None) -> Dict[str, Any]:
        """Extracts structured metadata, action items, and wikilinks from raw speech text."""
        cleaned = raw_text.strip()
        title = _derive_thought_title(cleaned, custom_title)
        tags = _extract_tags_from_text(cleaned)
        wikilinks = _extract_wikilinks_from_text(cleaned)
        action_items = _detect_action_items(cleaned)

        return {
            "title": title,
            "raw_text": cleaned,
            "summary": cleaned[:200] + ("..." if len(cleaned) > 200 else ""),
            "action_items": action_items,
            "tags": tags,
            "wikilinks": wikilinks,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }

    def format_markdown_note(self, thought: Dict[str, Any]) -> str:
        """Renders an Obsidian-compatible Markdown document with YAML frontmatter."""
        tags_str = ", ".join(thought.get("tags", ["voice_thought"]))
        frontmatter = [
            "---",
            f"title: \"{thought.get('title', 'Untitled')}\"",
            f"date: {thought.get('created_at', time.strftime('%Y-%m-%dT%H:%M:%S'))}",
            f"tags: [{tags_str}]",
            "source: voice_thought_stream",
            "status: inbox",
            "---",
            "",
            f"# {thought.get('title', 'Untitled')}",
            "",
            "## 🎙️ Расшифровка мысли",
            thought.get("raw_text", ""),
            "",
        ]

        actions = thought.get("action_items", [])
        if actions:
            frontmatter.append("## 📌 Задачи и действия")
            for act in actions:
                frontmatter.append(f"- [ ] {act}")
            frontmatter.append("")

        wikilinks = thought.get("wikilinks", [])
        if wikilinks:
            frontmatter.append("## 🔗 Связанные концепты")
            for link in wikilinks:
                frontmatter.append(f"- [[{link}]]")
            frontmatter.append("")

        return "\n".join(frontmatter)

    def save_thought_to_vault(self, thought: Dict[str, Any]) -> Tuple[str, str]:
        """Saves note to wiki directory and indexes into 768D memory facts."""
        title = thought.get("title", "voice_thought")
        sanitized = _sanitize_filename(title)
        filename = f"{time.strftime('%Y%m%d_%H%M%S')}_{sanitized}.md"
        filepath = self.wiki_dir / filename

        content = self.format_markdown_note(thought)
        filepath.write_text(content, encoding="utf-8")

        # Index into SQLite memory_facts_v2
        node_id = f"voice:{hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]}"
        self._index_to_memory_db(node_id, title, content, thought.get("tags", []))

        return str(filepath), node_id

    def _index_to_memory_db(self, node_id: str, title: str, content: str, tags: List[str]):
        """Persists 768D vector fact into SQLite memory database."""
        conn = None
        try:
            conn = get_db_connection(self.db_path)
            cur = conn.cursor()
            cur.execute("""
            CREATE TABLE IF NOT EXISTS memory_facts_v2 (
                node_id TEXT PRIMARY KEY,
                category TEXT,
                statement TEXT,
                confidence REAL,
                source_domain TEXT,
                created_at REAL,
                embedding_json TEXT
            )
            """)

            emb = get_embedding(content[:512])
            emb_json = json.dumps(emb) if emb else "[]"
            tags_str = ",".join(tags)

            cols = [c[1] for c in cur.execute("PRAGMA table_info(memory_facts_v2)").fetchall()]
            if "fact_text" in cols:
                now = time.time()
                content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
                cur.execute("""
                INSERT INTO memory_facts_v2 (fact_text, category, status, confidence, provenance, source_agent, content_hash, embedding_json, valid_from, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (f"{title}: {content[:300]}", "voice_thought", "VERIFIED_FACT", 0.95, tags_str, "voice_thought_engine", content_hash, emb_json, now, now, now))
            else:
                cur.execute("""
                INSERT OR REPLACE INTO memory_facts_v2 (node_id, category, statement, confidence, source_domain, created_at, embedding_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (node_id, "voice_thought", f"{title}: {content[:300]}", 0.95, tags_str, time.time(), emb_json))
            conn.commit()
        except Exception as e:
            sys.stderr.write(f"Memory indexing notice: {e}\n")
        finally:
            if conn:
                try:
                    conn.close()
                except Exception as exc:
                    logger.debug("Failed closing DB in index_thought_to_memory: %s", exc)

    def process_voice_file(self, audio_path: str, custom_title: Optional[str] = None) -> Dict[str, Any]:
        """High-level pipeline: transcribe -> extract -> save -> index."""
        trans_res = self.transcribe_audio(audio_path)
        if trans_res.get("status") == "ERROR":
            return trans_res

        thought = self.extract_structured_thought(trans_res.get("text", ""), custom_title=custom_title)
        note_path, node_id = self.save_thought_to_vault(thought)

        return {
            "status": "SUCCESS",
            "transcription": trans_res.get("text", ""),
            "duration": trans_res.get("duration", 0.0),
            "note_path": note_path,
            "node_id": node_id,
            "title": thought.get("title"),
            "action_items": thought.get("action_items"),
            "tags": thought.get("tags"),
        }
