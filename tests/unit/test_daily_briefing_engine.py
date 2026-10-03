"""
tests/test_daily_briefing_engine.py
Targeted Unit and E2E Tests for DailyBriefingEngine.
"""

import tempfile
import sqlite3
from pathlib import Path
import pytest

from vazus_core.integrations.daily_briefing_engine import DailyBriefingEngine


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


def test_daily_briefing_engine(temp_workspace):
    engine = DailyBriefingEngine(
        db_path=temp_workspace["db_path"],
        wiki_dir=temp_workspace["wiki_dir"]
    )
    briefing = engine.generate_morning_briefing()
    assert briefing["type"] == "morning_briefing"
    assert "today_lessons" in briefing

    card = engine.format_telegram_card(briefing)
    assert "Утренний брифинг" in card

    saved_path = engine.save_briefing_to_wiki(briefing)
    assert Path(saved_path).exists()


def test_daily_briefing_evening_digest(temp_workspace):
    engine = DailyBriefingEngine(
        db_path=temp_workspace["db_path"],
        wiki_dir=temp_workspace["wiki_dir"]
    )
    digest = engine.generate_evening_digest()
    assert digest["type"] == "evening_digest"
    card = engine.format_telegram_card(digest)
    assert "Вечерний дайджест" in card
