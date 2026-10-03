"""
tests/test_telegram_voice_jarvis.py
Targeted Unit and E2E Tests for TelegramVoiceJarvis.
"""

import tempfile
import sqlite3
from pathlib import Path
import pytest

from vazus_core.integrations.telegram_voice_jarvis import TelegramVoiceJarvis


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
        conn.execute("""
        INSERT INTO memory_facts_v2 (fact_text, category, status, confidence, provenance, source_agent, content_hash, embedding_json, valid_from, created_at, updated_at)
        VALUES ('SMT Z3 formal invariant proof', 'verification', 'VERIFIED_FACT', 0.99, 'math', 'test', 'h1', '[]', 100.0, 100.0, 100.0)
        """)
        conn.commit()
        conn.close()
        yield {"db_path": db_path, "wiki_dir": wiki_dir}


def test_telegram_voice_jarvis_commands(temp_workspace):
    jarvis = TelegramVoiceJarvis(
        db_path=temp_workspace["db_path"],
        wiki_dir=temp_workspace["wiki_dir"]
    )

    help_resp = jarvis.handle_text_command("/help")
    assert "Vazus Jarvis" in help_resp

    today_resp = jarvis.handle_text_command("/today")
    assert "Утренний брифинг" in today_resp

    status_resp = jarvis.handle_text_command("/status")
    assert "Vazus SuperGraph OS" in status_resp

    note_resp = jarvis.handle_text_command("/note Записать новую идею по алгоритмам")
    assert "Заметка сохранена" in note_resp

    search_resp = jarvis.handle_text_command("/search SMT")
    assert "Найдено по запросу" in search_resp

    canvas_resp = jarvis.handle_text_command("/canvas")
    assert "Obsidian Canvas создан" in canvas_resp
