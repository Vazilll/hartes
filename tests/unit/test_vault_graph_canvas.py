"""
tests/test_vault_graph_canvas.py
Targeted Unit and E2E Tests for VaultGraphCanvasGenerator.
"""

import tempfile
import sqlite3
import json
from pathlib import Path
import pytest

from vazus_core.integrations.vault_graph_canvas import VaultGraphCanvasGenerator


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
        VALUES ('SMT Z3 formal invariant', 'verification', 'VERIFIED_FACT', 0.99, 'math', 'test', 'h1', '[]', 100.0, 100.0, 100.0)
        """)
        conn.commit()
        conn.close()
        yield {"db_path": db_path, "wiki_dir": wiki_dir}


def test_vault_graph_canvas_generation(temp_workspace):
    canvas_gen = VaultGraphCanvasGenerator(db_path=temp_workspace["db_path"])
    
    schedule_data = {
        "group_name": "ИВБО-22-25",
        "schedule": [
            {"weekday": "Понедельник", "lesson_time": "09:00 - 10:30", "subject": "Высшая математика", "teacher": "проф. Смирнов", "classroom": "А-418"}
        ],
        "milestones": [
            {"subject": "Высшая математика", "milestone_name": "Экзамен", "due_date": "2026-08-25", "status": "PENDING"}
        ]
    }
    academic_canvas = canvas_gen.generate_academic_canvas(schedule_data)
    assert len(academic_canvas["nodes"]) >= 3
    assert len(academic_canvas["edges"]) >= 2

    # Test export
    out_file = str(Path(temp_workspace["wiki_dir"]) / "test.canvas")
    exported = canvas_gen.export_canvas_to_file(academic_canvas, out_file)
    assert Path(exported).exists()
    with open(exported, "r", encoding="utf-8") as f:
        data = json.load(f)
        assert "nodes" in data


def test_memory_canvas_generation(temp_workspace):
    canvas_gen = VaultGraphCanvasGenerator(db_path=temp_workspace["db_path"])
    mem_canvas = canvas_gen.generate_memory_facts_canvas(limit=5)
    assert len(mem_canvas["nodes"]) >= 1
