"""
vazus.vazus_core.dialogue_persister — Subagent Dialogue & Memory Trace Persistence Engine.
Persists subagent conversation traces, memory steps into SQLite vazus.db,
and exports formatted Obsidian wiki notes to /home/tarhes/Проекты/vazus/services/memory/semantic/wiki.

vazus SuperGraph OS Architecture
"""

import json
import logging
from contextlib import contextmanager
import re
import sqlite3
import sys
import time
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger("vazus_core.dialogue_persister")

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from vazus_core.memory.embeddings import UnifiedEmbeddingManager
except ImportError:
    UnifiedEmbeddingManager = None

import os

PRIMARY_WIKI_DIR = Path("/home/tarhes/Проекты/vazus/services/memory/semantic/wiki")
SECONDARY_WIKI_DIR = PRIMARY_WIKI_DIR
DEFAULT_DB_PATH = Path(os.getenv("VAZUS_DB_PATH", "/home/tarhes/Проекты/vazus/services/memory/vazus.db"))


class SubagentDialoguePersister:
    """Persists subagent dialogues and memory traces into vazus.db and Obsidian wiki notes."""

    def __init__(self, db_path: Optional[str | Path] = None):
        target = db_path if db_path is not None else os.getenv("VAZUS_DB_PATH", "/home/tarhes/Проекты/vazus/services/memory/vazus.db")
        self.db_path = Path(target)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.embedder = UnifiedEmbeddingManager() if UnifiedEmbeddingManager else None
        self._ensure_tables()

    @contextmanager
    def _connection(self, db_file: Optional[Path] = None):
        target_path = Path(db_file) if db_file else self.db_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(target_path, timeout=30.0)
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=30000;")
        except Exception as e:
            logger.debug("configure pragma non-fatal: %s", e)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS subagent_dialogues (
                dialogue_id TEXT PRIMARY KEY,
                session_id TEXT,
                parent_id TEXT,
                agent_name TEXT,
                prompt TEXT,
                response TEXT,
                vector_768d BLOB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS subagent_memory_traces (
                trace_id TEXT PRIMARY KEY,
                dialogue_id TEXT,
                agent_name TEXT,
                trace_kind TEXT,
                summary TEXT,
                content TEXT,
                obsidian_note_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _ensure_tables(self):
        """Ensures subagent_dialogues and subagent_memory_traces tables exist in target vazus.db file."""
        try:
            with self._connection(self.db_path):
                pass
        except Exception as e:
            logger.debug("ensure_tables on %s non-fatal: %s", self.db_path, e)

    def record_dialogue(
        self,
        session_id: str,
        parent_id: str,
        agent_name: str,
        prompt: str,
        response: str,
        *,
        dialogue_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Records a subagent conversation dialogue into SQLite vazus.db."""
        dlg_id = dialogue_id or f"dlg_{agent_name}_{int(time.time()*1000)}_{uuid.uuid4().hex[:6]}"
        vector_bytes, vector_dim = None, 0
        if self.embedder:
            try:
                combined_text = f"Agent: {agent_name}\nPrompt: {prompt[:1000]}\nResponse: {response[:1000]}"
                vector_768d = self.embedder.get_embedding(combined_text)
                vector_dim = len(vector_768d)
                vector_bytes = json.dumps(vector_768d).encode("utf-8")
            except Exception as e:
                logger.debug("calculate dialogue embedding non-fatal: %s", e)

        try:
            with self._connection(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO subagent_dialogues 
                    (dialogue_id, session_id, parent_id, agent_name, prompt, response, vector_768d)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (dlg_id, session_id, parent_id, agent_name, prompt, response, vector_bytes)
                )
        except Exception as e:
            logger.debug("record_dialogue insert on %s non-fatal: %s", self.db_path, e)

        return {
            "dialogue_id": dlg_id, "session_id": session_id,
            "parent_id": parent_id, "agent_name": agent_name,
            "vector_dim": vector_dim, "status": "STORED"
        }

    def record_memory_trace(
        self,
        agent_name: str,
        trace_kind: str,
        summary: str,
        content: str,
        *,
        dialogue_id: Optional[str] = None,
        export_obsidian: bool = True,
        title: Optional[str] = None
    ) -> Dict[str, Any]:
        """Records a subagent memory trace and optionally exports an Obsidian wiki note."""
        trace_id = f"trace_{agent_name}_{int(time.time()*1000)}_{uuid.uuid4().hex[:6]}"
        obsidian_path = ""
        if export_obsidian:
            note_title = title or f"{agent_name}_{trace_kind}_{int(time.time())}"
            obsidian_path = self.export_to_obsidian_wiki(
                title=note_title, content=content,
                agent_name=agent_name, summary=summary,
                trace_kind=trace_kind
            )

        try:
            with self._connection(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO subagent_memory_traces
                    (trace_id, dialogue_id, agent_name, trace_kind, summary, content, obsidian_note_path)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (trace_id, dialogue_id or "", agent_name, trace_kind, summary, content, obsidian_path)
                )
        except Exception as e:
            logger.debug("record_memory_trace insert on %s non-fatal: %s", self.db_path, e)

        return {
            "trace_id": trace_id, "dialogue_id": dialogue_id,
            "agent_name": agent_name, "trace_kind": trace_kind,
            "obsidian_note_path": obsidian_path, "status": "STORED"
        }

    def _build_obsidian_markdown(
        self,
        title: str,
        content: str,
        agent_name: str,
        summary: str,
        trace_kind: str,
        *,
        linked_notes: Optional[List[str]] = None
    ) -> str:
        """Constructs markdown frontmatter and body for Obsidian note."""
        links_str = "\n".join([f"- [[{note}]]" for note in linked_notes]) if linked_notes else f"- [[{agent_name}_Memory_Hub]]\n- [[SuperGraph_OS_Architecture]]"
        timestamp_iso = time.strftime("%Y-%m-%d %H:%M:%S")
        return f"""---
title: "{title}"
agent: "{agent_name}"
trace_kind: "{trace_kind}"
created_at: "{timestamp_iso}"
tags:
  - subagent
  - memory_trace
  - vazus_supergraph
  - obsidian_wiki
---

# {title}

> **Agent**: [[{agent_name}]]  
> **Trace Kind**: `{trace_kind}`  
> **Timestamp**: {timestamp_iso}  
> **Summary**: {summary or 'Subagent execution trace'}

---

## Memory Trace Content

{content}

---

## Linked SuperGraph Memory Nodes
{links_str}
"""

    def export_to_obsidian_wiki(
        self,
        title: str,
        content: str,
        *,
        agent_name: str = "subagent",
        summary: str = "",
        trace_kind: str = "MEMORY_TRACE",
        linked_notes: Optional[List[str]] = None
    ) -> str:
        """Exports subagent memory trace into formatted Obsidian Markdown wiki notes."""
        clean_title = re.sub(r'[^\w\-_]', '_', title).strip('_') or f"subagent_trace_{int(time.time())}"
        filename = f"{clean_title}.md"
        markdown_body = self._build_obsidian_markdown(
            title, content, agent_name, summary, trace_kind, linked_notes=linked_notes
        )

        written_path = ""
        for dir_path in [PRIMARY_WIKI_DIR, SECONDARY_WIKI_DIR]:
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
                note_file = dir_path / filename
                note_file.write_text(markdown_body, encoding="utf-8")
                if not written_path:
                    written_path = str(note_file)
            except Exception as e:
                logger.debug("write wiki note to %s non-fatal: %s", dir_path, e)
        return written_path


# Global singleton instance
dialogue_persister = SubagentDialoguePersister()


if __name__ == "__main__":
    dlg_res = dialogue_persister.record_dialogue(
        session_id="test_session_001",
        parent_id="orchestrator",
        agent_name="open_deep_researcher",
        prompt="Analyze SuperGraph memory linking",
        response="SuperGraph memory link complete with 768D vectors."
    )
    print("Dialogue Record:", dlg_res)

    trace_res = dialogue_persister.record_memory_trace(
        agent_name="open_deep_researcher",
        trace_kind="RESEARCH_FINDING",
        summary="SuperGraph memory link complete",
        content="Detailed research on AST and Wiki link unification.",
        dialogue_id=dlg_res["dialogue_id"],
        title="SuperGraph_Memory_Research_Note"
    )
    print("Memory Trace Record:", trace_res)
