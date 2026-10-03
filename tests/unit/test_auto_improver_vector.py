"""
tests/test_auto_improver_vector.py — Unit Tests for LessonMemoryBank 768D Vector Wiring & Cosine Retrieval
===========================================================================================================
Tests database schema auto-migration, 768D embedding generation on save_lesson, top-k cosine similarity retrieval,
score weighting formula (0.75 * similarity + 0.25 * min(1.0, success_count / 5.0)), and fallback behavior.
"""

import json
import sqlite3
import pytest
import asyncio
from unittest.mock import patch

from vazus_core.auto_improver import LessonMemoryBank
from vazus_core.db import get_db_connection
from vazus_core.embeddings import UnifiedEmbeddingManager


def test_schema_auto_migration(tmp_path, monkeypatch):
    """Verifies that LessonMemoryBank auto-migrates existing tables without embedding_json column."""
    db_file = tmp_path / "test_migration.db"
    monkeypatch.setenv("VAZUS_DB_PATH", str(db_file))

    # Pre-create table without embedding_json
    conn = sqlite3.connect(str(db_file))
    conn.execute("""
        CREATE TABLE reflexion_lessons (
            lesson_id      TEXT PRIMARY KEY,
            task_type      TEXT,
            error_sig      TEXT,
            lesson_text    TEXT,
            fix_hint       TEXT,
            success_count  INTEGER DEFAULT 0,
            created_at     REAL
        )
    """)
    conn.commit()
    conn.close()

    # Instantiate bank — should run auto-migration seamlessly
    bank = LessonMemoryBank()

    # Verify column exists
    conn = sqlite3.connect(str(db_file))
    cursor = conn.execute("PRAGMA table_info(reflexion_lessons)")
    cols = [r[1] for r in cursor.fetchall()]
    conn.close()

    assert "embedding_json" in cols, "embedding_json column was not auto-migrated!"


def test_save_lesson_vector_generation(tmp_path, monkeypatch):
    """Verifies save_lesson computes and persists a 768D embedding in embedding_json."""
    db_file = tmp_path / "test_save.db"
    monkeypatch.setenv("VAZUS_DB_PATH", str(db_file))

    bank = LessonMemoryBank()
    lesson_id = bank.save_lesson(
        task_type="unit_test",
        error_sig="ValueError: invalid literal for int() with base 10",
        lesson_text="Ensure string is sanitized before converting to int.",
        fix_hint="Use try-except or str.isdigit() check."
    )

    assert lesson_id.startswith("lesson_")

    conn = sqlite3.connect(str(db_file))
    row = conn.execute(
        "SELECT lesson_id, task_type, error_sig, lesson_text, fix_hint, embedding_json FROM reflexion_lessons WHERE lesson_id = ?",
        (lesson_id,)
    ).fetchone()
    conn.close()

    assert row is not None
    assert row[1] == "unit_test"
    assert row[5] is not None

    emb = json.loads(row[5])
    assert isinstance(emb, list)
    assert len(emb) == 768
    assert all(isinstance(x, (float, int)) for x in emb)


def test_save_lesson_async(tmp_path, monkeypatch):
    """Verifies save_lesson_async works asynchronously and persists 768D embedding."""
    db_file = tmp_path / "test_save_async.db"
    monkeypatch.setenv("VAZUS_DB_PATH", str(db_file))

    bank = LessonMemoryBank()
    lesson_id = asyncio.run(bank.save_lesson_async(
        task_type="async_test",
        error_sig="ZeroDivisionError: division by zero",
        lesson_text="Always guard denominator against zero.",
        fix_hint="Add if denominator != 0 check."
    ))

    conn = sqlite3.connect(str(db_file))
    row = conn.execute("SELECT embedding_json FROM reflexion_lessons WHERE lesson_id = ?", (lesson_id,)).fetchone()
    conn.close()

    assert row is not None and row[0] is not None
    vec = json.loads(row[0])
    assert len(vec) == 768


def test_top_k_cosine_similarity_retrieval(tmp_path, monkeypatch):
    """Verifies retrieve_relevant uses cosine similarity ranking over candidate embeddings."""
    db_file = tmp_path / "test_retrieval.db"
    monkeypatch.setenv("VAZUS_DB_PATH", str(db_file))

    bank = LessonMemoryBank()

    def mock_get_embedding(text: str) -> list[float]:
        vec = [0.0] * 768
        if "KeyError" in text:
            vec[0] = 1.0
        elif "IndexError" in text:
            vec[1] = 1.0
        elif "ZeroDivisionError" in text:
            vec[2] = 1.0
        else:
            vec[3] = 1.0
        return vec

    with patch.object(UnifiedEmbeddingManager, "get_embedding", side_effect=mock_get_embedding):
        # Save 3 distinct lessons
        id_key = bank.save_lesson(
            task_type="code_fix",
            error_sig="KeyError: 'username' missing in dict",
            lesson_text="Use dict.get('username') instead of dict['username'].",
            fix_hint="Use dict.get('username', default_val)"
        )

        id_index = bank.save_lesson(
            task_type="code_fix",
            error_sig="IndexError: list index out of range in array lookup",
            lesson_text="Check len(lst) before accessing index.",
            fix_hint="Guard with if idx < len(lst)"
        )

        id_zero = bank.save_lesson(
            task_type="code_fix",
            error_sig="ZeroDivisionError: float division by zero",
            lesson_text="Validate non-zero divisor before division.",
            fix_hint="Check if divisor == 0"
        )

        # Query with a semantic variant of IndexError
        results = bank.retrieve_relevant(
            error_sig="IndexError: list access out of bounds",
            task_type="code_fix",
            top_k=3
        )

        assert len(results) >= 1
        # Top match should be the IndexError lesson
        top_match = results[0]
        assert top_match["id"] == id_index
        assert "IndexError" in top_match["error_sig"]


def test_retrieval_similarity_ranking(tmp_path, monkeypatch):
    """Verifies that retrieve_relevant computes and ranks by cosine similarity."""
    db_file = tmp_path / "test_weighting.db"
    monkeypatch.setenv("VAZUS_DB_PATH", str(db_file))

    bank = LessonMemoryBank()

    def mock_get_embedding(text: str) -> list[float]:
        vec = [0.0] * 768
        vec[0] = 1.0
        return vec

    with patch.object(UnifiedEmbeddingManager, "get_embedding", side_effect=mock_get_embedding):
        id1 = bank.save_lesson(
            task_type="test",
            error_sig="TypeError: unsupported operand type for +",
            lesson_text="Cast string to int before addition variant 1.",
            fix_hint="int(x) + int(y)"
        )

        id2 = bank.save_lesson(
            task_type="test",
            error_sig="TypeError: unsupported operand type for +",
            lesson_text="Cast string to int before addition variant 2.",
            fix_hint="int(x) + int(y)"
        )

        results = bank.retrieve_relevant(
            error_sig="TypeError: unsupported operand type for +",
            task_type="test",
            top_k=2
        )

        assert len(results) == 2
        assert "similarity" in results[0]
        assert results[0]["similarity"] == pytest.approx(1.0, abs=1e-3)


def test_fallback_to_sql_like(tmp_path, monkeypatch):
    """Verifies that retrieve_relevant falls back cleanly when vector embeddings are absent."""
    db_file = tmp_path / "test_fallback.db"
    monkeypatch.setenv("VAZUS_DB_PATH", str(db_file))

    # Manually insert row without embedding_json
    conn = sqlite3.connect(str(db_file))
    conn.execute("""
        CREATE TABLE reflexion_lessons (
            lesson_id      TEXT PRIMARY KEY,
            task_type      TEXT,
            error_sig      TEXT,
            lesson_text    TEXT,
            fix_hint       TEXT,
            success_count  INTEGER DEFAULT 0,
            created_at     REAL,
            embedding_json TEXT
        )
    """)
    conn.execute(
        "INSERT INTO reflexion_lessons VALUES (?, ?, ?, ?, ?, 0, 100.0, NULL)",
        ("legacy_1", "fallback_test", "AttributeError: 'NoneType' object has no attribute 'name'", "Check if object is None.", "Add if obj is not None check")
    )
    conn.commit()
    conn.close()

    bank = LessonMemoryBank()
    results = bank.retrieve_relevant(
        error_sig="AttributeError: 'NoneType' object has no attribute 'name'",
        task_type="fallback_test",
        top_k=1
    )

    assert len(results) == 1
    assert results[0]["id"] == "legacy_1"
    assert "lesson" in results[0]


def test_retrieve_relevant_async(tmp_path, monkeypatch):
    """Verifies retrieve_relevant_async works asynchronously."""
    db_file = tmp_path / "test_retrieve_async.db"
    monkeypatch.setenv("VAZUS_DB_PATH", str(db_file))

    bank = LessonMemoryBank()
    lesson_id = asyncio.run(bank.save_lesson_async(
        task_type="async_retrieval",
        error_sig="TimeoutError: async operation timed out",
        lesson_text="Increase timeout limit.",
        fix_hint="Use asyncio.timeout(300)"
    ))

    results = asyncio.run(bank.retrieve_relevant_async(
        error_sig="TimeoutError: async operation timed out",
        task_type="async_retrieval",
        top_k=1
    ))

    assert len(results) == 1
    assert results[0]["id"] == lesson_id


def test_reflexion_evaluator_error_trace_remediation():
    """Verifies that non-empty error_trace ensures passed=False and score deduction."""
    from vazus_core.auto_improver import ReflexionEvaluator
    evaluator = ReflexionEvaluator()
    code = "def add(a, b):\n    return a + b\n"

    # Passing evaluation without error
    res_clean = evaluator.evaluate(code=code, error_trace="")
    assert res_clean.passed is True
    assert res_clean.score >= 0.7

    # Failing evaluation with error_trace
    res_error = evaluator.evaluate(code=code, error_trace="ZeroDivisionError: division by zero")
    assert res_error.passed is False
    assert res_error.score < 0.70


def test_retrieval_success_count_weighting(tmp_path, monkeypatch):
    """Verifies that retrieve_relevant weights candidate scores by similarity (0.75) + success_count (0.25)."""
    db_file = tmp_path / "test_weighting_success.db"
    monkeypatch.setenv("VAZUS_DB_PATH", str(db_file))

    bank = LessonMemoryBank()

    def mock_get_embedding(text: str) -> list[float]:
        vec = [0.0] * 768
        vec[0] = 1.0
        return vec

    with patch.object(UnifiedEmbeddingManager, "get_embedding", side_effect=mock_get_embedding):
        id1 = bank.save_lesson(
            task_type="test",
            error_sig="TypeError: unsupported operand type for +",
            lesson_text="Cast string to int before addition variant 1.",
            fix_hint="int(x) + int(y)"
        )

        id2 = bank.save_lesson(
            task_type="test",
            error_sig="TypeError: unsupported operand type for +",
            lesson_text="Cast string to int before addition variant 2.",
            fix_hint="int(x) + int(y)"
        )

        for _ in range(5):
            bank.mark_lesson_used(id2)

        results = bank.retrieve_relevant(
            error_sig="TypeError: unsupported operand type for +",
            task_type="test",
            top_k=2
        )

        assert len(results) == 2
        assert results[0]["id"] == id2
        assert results[0]["success_count"] == 5


