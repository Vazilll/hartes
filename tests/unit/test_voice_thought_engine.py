"""
tests/test_voice_thought_engine.py
Targeted Unit and E2E Tests for VoiceThoughtEngine.
"""

import tempfile
import sqlite3
from pathlib import Path
import pytest

from vazus_core.integrations.voice_thought_engine import (
    VoiceThoughtEngine,
    _sanitize_filename,
    _extract_tags_from_text,
    _extract_wikilinks_from_text,
)


@pytest.fixture
def temp_workspace():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        db_path = str(tmp_path / "test_vazus.db")
        wiki_dir = str(tmp_path / "wiki")

        conn = sqlite3.connect(db_path)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS memory_facts_v2 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fact_text TEXT,
            category TEXT,
            status TEXT,
            confidence REAL,
            provenance TEXT,
            source_agent TEXT,
            content_hash TEXT,
            embedding_json TEXT,
            valid_from REAL,
            valid_until REAL,
            superseded_by TEXT,
            created_at REAL,
            updated_at REAL
        )
        """)
        conn.commit()
        conn.close()
        yield {"db_path": db_path, "wiki_dir": wiki_dir}


def test_sanitize_filename():
    assert _sanitize_filename('Hello: World / Test? "Great"') == "Hello_World_Test_Great"
    assert _sanitize_filename("") == "voice_thought"


def test_extract_tags_and_wikilinks():
    text = "Сегодня нужно изучить #math #smt и связать с [[Z3 Solver]] и [[Calculus]]"
    tags = _extract_tags_from_text(text)
    assert "voice_thought" in tags
    assert "math" in tags
    assert "smt" in tags

    links = _extract_wikilinks_from_text(text)
    assert "Z3 Solver" in links
    assert "Calculus" in links


def test_voice_thought_engine_structured_extraction(temp_workspace):
    engine = VoiceThoughtEngine(
        db_path=temp_workspace["db_path"],
        wiki_dir=temp_workspace["wiki_dir"]
    )
    raw = "Нужно подготовить экзамен по матанализу к следующей неделе. Также надо сдать курсовой проект по архитектуре ЭВМ #study"
    thought = engine.extract_structured_thought(raw)

    assert "матанализу" in thought["title"]
    assert len(thought["action_items"]) == 2
    assert "study" in thought["tags"]

    note_path, node_id = engine.save_thought_to_vault(thought)
    assert Path(note_path).exists()
    assert node_id.startswith("voice:")

    # Check persistence in SQLite
    conn = sqlite3.connect(temp_workspace["db_path"])
    row = conn.execute("SELECT id, fact_text FROM memory_facts_v2 ORDER BY created_at DESC LIMIT 1").fetchone()
    conn.close()
    assert row is not None
