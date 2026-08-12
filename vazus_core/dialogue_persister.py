"""
vazus.vazus_core.dialogue_persister — Subagent Dialogue & Memory Trace Persistence Engine.
Persists subagent conversation traces, memory steps into SQLite vazus.db,
and exports formatted Obsidian wiki notes to C:\\vazus\\services\\memory\\semantic\\wiki.

vazus SuperGraph OS Architecture
"""

import json
from contextlib import contextmanager
import os
import re
import sqlite3
import sys
import time
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from vazus_core.embeddings import UnifiedEmbeddingManager
except ImportError:
    UnifiedEmbeddingManager = None

PRIMARY_WIKI_DIR = Path("C:/vazus/services/memory/semantic/wiki")
SECONDARY_WIKI_DIR = Path("C:/vazus/memory/semantic/wiki")
DEFAULT_DB_PATH = Path("C:/vazus/services/memory/vazus.db")


class SubagentDialoguePersister:
    """Persists subagent dialogues and memory traces into vazus.db and Obsidian wiki notes."""

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
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
        except Exception:
            pass
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
        """Ensures subagent_dialogues and subagent_memory_traces tables exist in vazus.db files."""
        candidate_paths = [
            self.db_path,
            Path("C:/vazus/services/memory/vazus.db"),
            Path("C:/vazus/memory/vazus.db"),
            Path("C:/vazus/vazus.db"),
        ]
        for p in candidate_paths:
            try:
                with self._connection(p):
                    pass
            except Exception:
                pass

    def record_dialogue(
        self,
        session_id: str,
        parent_id: str,
        agent_name: str,
        prompt: str,
        response: str,
        dialogue_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Records a subagent conversation dialogue into SQLite vazus.db."""
        dlg_id = dialogue_id or f"dlg_{agent_name}_{int(time.time()*1000)}_{uuid.uuid4().hex[:6]}"
        
        # Calculate 768D vector embedding if embedder available
        vector_bytes = None
        vector_dim = 0
        if self.embedder:
            try:
                combined_text = f"Agent: {agent_name}\nPrompt: {prompt[:1000]}\nResponse: {response[:1000]}"
                vector_768d = self.embedder.get_embedding(combined_text)
                vector_dim = len(vector_768d)
                vector_bytes = json.dumps(vector_768d).encode("utf-8")
            except Exception as e:
                sys.stderr.write(f"[DialoguePersister] Embedding warning: {e}\n")

        candidate_paths = [
            self.db_path,
            Path("C:/vazus/services/memory/vazus.db"),
            Path("C:/vazus/memory/vazus.db"),
            Path("C:/vazus/vazus.db"),
        ]
        for p in candidate_paths:
            try:
                with self._connection(p) as conn:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO subagent_dialogues 
                        (dialogue_id, session_id, parent_id, agent_name, prompt, response, vector_768d)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (dlg_id, session_id, parent_id, agent_name, prompt, response, vector_bytes)
                    )
            except Exception:
                pass

        return {
            "dialogue_id": dlg_id,
            "session_id": session_id,
            "parent_id": parent_id,
            "agent_name": agent_name,
            "vector_dim": vector_dim,
            "status": "STORED"
        }

    def record_memory_trace(
        self,
        agent_name: str,
        trace_kind: str,
        summary: str,
        content: str,
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
                title=note_title,
                content=content,
                agent_name=agent_name,
                summary=summary,
                trace_kind=trace_kind
            )

        candidate_paths = [
            self.db_path,
            Path("C:/vazus/services/memory/vazus.db"),
            Path("C:/vazus/memory/vazus.db"),
            Path("C:/vazus/vazus.db"),
        ]
        for p in candidate_paths:
            try:
                with self._connection(p) as conn:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO subagent_memory_traces
                        (trace_id, dialogue_id, agent_name, trace_kind, summary, content, obsidian_note_path)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (trace_id, dialogue_id or "", agent_name, trace_kind, summary, content, obsidian_path)
                    )
            except Exception:
                pass

        return {
            "trace_id": trace_id,
            "dialogue_id": dialogue_id,
            "agent_name": agent_name,
            "trace_kind": trace_kind,
            "obsidian_note_path": obsidian_path,
            "status": "STORED"
        }

    def export_to_obsidian_wiki(
        self,
        title: str,
        content: str,
        agent_name: str = "subagent",
        summary: str = "",
        trace_kind: str = "MEMORY_TRACE",
        linked_notes: Optional[List[str]] = None
    ) -> str:
        """Exports subagent memory trace into formatted Obsidian Markdown wiki notes."""
        clean_title = re.sub(r'[^\w\-_]', '_', title).strip('_')
        if not clean_title:
            clean_title = f"subagent_trace_{int(time.time())}"

        filename = f"{clean_title}.md"
        primary_file = PRIMARY_WIKI_DIR / filename
        secondary_file = SECONDARY_WIKI_DIR / filename

        links_str = ""
        if linked_notes:
            links_str = "\n".join([f"- [[{note}]]" for note in linked_notes])
        else:
            links_str = f"- [[{agent_name}_Memory_Hub]]\n- [[SuperGraph_OS_Architecture]]"

        timestamp_iso = time.strftime("%Y-%m-%d %H:%M:%S")

        markdown_body = f"""---
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

        written_path = ""
        for dir_path in [PRIMARY_WIKI_DIR, SECONDARY_WIKI_DIR]:
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
                note_file = dir_path / filename
                note_file.write_text(markdown_body, encoding="utf-8")
                if not written_path:
                    written_path = str(note_file)
            except Exception as e:
                sys.stderr.write(f"[DialoguePersister] Failed to write wiki note to {dir_path}: {e}\n")

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
