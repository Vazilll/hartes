"""
tests/test_dream_consolidation.py — Verification suite for Mem0 Dream consolidation.

Tests:
1. Full DreamConsolidator execution and return statistics format.
2. Status tracking and bi-temporal / log inspection.
3. Reflexion lesson deduplication logic.
4. Orphaned knowledge graph edge pruning logic.
5. Autonomous background trigger integration via daemon_sidecar run_single_heartbeat().
6. Unified hub integration for dream consolidation status and manual execution.
"""

import time
import pytest
from vazus_core.memory.db import get_db_connection
from vazus_core.memory.dream_consolidator import (
    DreamConsolidator,
    get_consolidation_status,
    run_dream_consolidation,
)
from vazus_core.workers.daemon_sidecar import run_single_heartbeat
from vazus_core.engine.unified_hub import VazusUnifiedHub


def test_dream_consolidator_execution():
    """Verify DreamConsolidator runs without errors and returns correct statistics."""
    consolidator = DreamConsolidator()
    stats = consolidator.run_full_consolidation(run_vacuum=False)

    assert isinstance(stats, dict), "Consolidation result must be a dictionary"
    expected_keys = {
        "lessons_deduped",
        "facts_consolidated",
        "orphaned_edges_pruned",
        "telemetry_compacted",
    }
    assert expected_keys.issubset(stats.keys()), f"Missing keys in stats: {expected_keys - stats.keys()}"

    for k in expected_keys:
        assert isinstance(stats[k], int), f"Stat {k} must be an integer"
        assert stats[k] >= 0, f"Stat {k} must be non-negative"


def test_dream_consolidation_status_tracking():
    """Verify that consolidation runs are recorded in the database log and reflected in status."""
    consolidator = DreamConsolidator()
    stats = consolidator.run_full_consolidation()

    status = consolidator.get_consolidation_status()
    assert isinstance(status, dict)
    assert status["status"] == "SUCCESS"
    assert status["last_run"] is not None
    assert status["hours_since_last"] is not None
    assert status["hours_since_last"] < 1.0
    assert status["stats"] == stats

    # Also verify module helper
    helper_status = get_consolidation_status(consolidator.db_path)
    assert helper_status["status"] == "SUCCESS"
    assert helper_status["last_run"] == status["last_run"]


def test_reflexion_lesson_deduplication():
    """Verify that duplicate reflexion lessons are merged and deleted."""
    consolidator = DreamConsolidator()
    conn = get_db_connection(consolidator.db_path)

    # Detect primary key column for reflexion_lessons
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(reflexion_lessons)")
    cols = [c[1] for c in cur.fetchall()]
    pk_col = "lesson_id" if "lesson_id" in cols else "id"

    test_err = f"ERR_SIG_{int(time.time() * 1000)}"
    test_type = "test_task"

    # Insert two duplicates
    if pk_col == "lesson_id":
        conn.execute(
            """INSERT INTO reflexion_lessons (lesson_id, task_type, error_sig, lesson_text, fix_hint, success_count)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ("refl_test_1", test_type, test_err, "lesson text 1", "hint 1", 2)
        )
        conn.execute(
            """INSERT INTO reflexion_lessons (lesson_id, task_type, error_sig, lesson_text, fix_hint, success_count)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ("refl_test_2", test_type, test_err, "lesson text 2", "hint 2", 3)
        )
    else:
        conn.execute(
            f"""INSERT INTO reflexion_lessons ({pk_col}, task_type, error_sig, lesson_text, fix_hint, success_count)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ("refl_test_1", test_type, test_err, "lesson text 1", "hint 1", 2)
        )
        conn.execute(
            f"""INSERT INTO reflexion_lessons ({pk_col}, task_type, error_sig, lesson_text, fix_hint, success_count)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ("refl_test_2", test_type, test_err, "lesson text 2", "hint 2", 3)
        )
    conn.commit()
    conn.close()

    deduped = consolidator.consolidate_reflexion_lessons()
    assert deduped >= 1, "Duplicate reflexion lessons should have been deduplicated"

    # Verify only one remains with combined or updated success count
    conn = get_db_connection(consolidator.db_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM reflexion_lessons WHERE error_sig = ?", (test_err,))
    count = cur.fetchone()[0]
    conn.close()
    assert count == 1, "Expected exactly 1 consolidated lesson"


def test_orphaned_kg_edges_pruning():
    """Verify that orphaned knowledge graph edges are safely pruned."""
    consolidator = DreamConsolidator()
    conn = get_db_connection(consolidator.db_path)

    # Insert orphaned edge pointing to non-existent nodes
    fake_src = "node_nonexistent_src_999"
    fake_tgt = "node_nonexistent_tgt_999"
    conn.execute(
        "INSERT OR REPLACE INTO kg_edges (source_id, target_id, relation, strength) VALUES (?, ?, ?, ?)",
        (fake_src, fake_tgt, "test_orphaned_rel", 0.5)
    )
    conn.commit()
    conn.close()

    pruned = consolidator.prune_orphaned_kg_edges()
    assert pruned >= 1, "Orphaned edge should have been pruned"


def test_daemon_sidecar_heartbeat_integration():
    """Verify daemon sidecar heartbeat inspects and integrates dream consolidation."""
    report = run_single_heartbeat()
    assert isinstance(report, dict)
    assert "dream_fresh" in report
    assert "dream_consolidation_triggered" in report
    assert report["status"] == "HEALTHY"


def test_unified_hub_integration():
    """Verify unified hub exposes dream consolidation status and manual execution."""
    hub = VazusUnifiedHub()
    status = hub.get_system_status()

    assert "dream_consolidation" in status
    assert isinstance(status["dream_consolidation"], dict)
    assert "status" in status["dream_consolidation"]

    # Test run_dream_consolidation method
    run_stats = hub.run_dream_consolidation()
    assert isinstance(run_stats, dict)
    assert "lessons_deduped" in run_stats
