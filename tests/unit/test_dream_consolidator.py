"""
Unit tests for vazus_core.memory.dream_consolidator (Mem0 Dream Sleep-Time Engine).
"""

import time
import sqlite3
import pytest
from vazus_core.memory.dream_consolidator import DreamConsolidator


@pytest.fixture
def temp_dream_db(tmp_path):
    db_file = tmp_path / "test_dream.db"
    conn = sqlite3.connect(str(db_file))
    with conn:
        conn.executescript("""
            CREATE TABLE reflexion_lessons (
                id TEXT PRIMARY KEY,
                task_type TEXT,
                error_sig TEXT,
                lesson_text TEXT,
                fix_hint TEXT,
                success_count INTEGER,
                created_at REAL,
                embedding_json TEXT
            );

            CREATE TABLE memory_facts_v2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fact_text TEXT,
                category TEXT,
                confidence REAL,
                provenance TEXT,
                source_agent TEXT,
                content_hash TEXT,
                embedding_json TEXT,
                valid_from REAL,
                valid_until REAL,
                superseded_by INTEGER,
                created_at REAL,
                updated_at REAL
            );

            CREATE TABLE kg_nodes (
                id TEXT PRIMARY KEY,
                name TEXT,
                domain TEXT,
                node_type TEXT,
                description TEXT,
                tags TEXT,
                properties TEXT,
                embedding_json TEXT
            );

            CREATE TABLE kg_edges (
                source_id TEXT,
                target_id TEXT,
                relation TEXT,
                strength REAL DEFAULT 1.0,
                properties TEXT,
                PRIMARY KEY (source_id, target_id, relation)
            );

            CREATE TABLE telemetry_call_edges (
                caller TEXT NOT NULL,
                callee TEXT NOT NULL,
                hit_count INTEGER DEFAULT 0,
                total_time_ns INTEGER DEFAULT 0,
                last_seen REAL,
                PRIMARY KEY (caller, callee)
            );
        """)

        # Insert duplicate lessons
        t0 = time.time()
        conn.execute("INSERT INTO reflexion_lessons VALUES ('l1', 'code', 'err1', 'fix1', 'hint1', 2, ?, '[]')", (t0,))
        conn.execute("INSERT INTO reflexion_lessons VALUES ('l2', 'code', 'err1', 'fix1_dup', 'hint1', 3, ?, '[]')", (t0 - 10,))

        # Insert valid & orphaned edges
        conn.execute("INSERT INTO kg_nodes (id, name) VALUES ('n1', 'node1')")
        conn.execute("INSERT INTO kg_nodes (id, name) VALUES ('n2', 'node2')")
        conn.execute("INSERT INTO kg_edges (source_id, target_id, relation) VALUES ('n1', 'n2', 'CALLS')")
        conn.execute("INSERT INTO kg_edges (source_id, target_id, relation) VALUES ('n1', 'ghost_node', 'CALLS')")

        # Insert old telemetry edge
        conn.execute("INSERT INTO telemetry_call_edges VALUES ('c1', 'c2', 1, 100, ?)", (t0 - (40 * 86400),))
        conn.execute("INSERT INTO telemetry_call_edges VALUES ('c1', 'c3', 10, 1000, ?)", (t0,))

    conn.close()
    return str(db_file)


def test_dream_consolidator_dedup_and_prune(temp_dream_db):
    consolidator = DreamConsolidator(db_path=temp_dream_db)
    stats = consolidator.run_full_consolidation(run_vacuum=False)

    assert stats["lessons_deduped"] == 1
    assert stats["orphaned_edges_pruned"] == 1
    assert stats["telemetry_compacted"] == 1

    conn = sqlite3.connect(temp_dream_db)
    cur = conn.cursor()

    # Verify lesson deduplication and success count accumulation
    cur.execute("SELECT id, success_count FROM reflexion_lessons")
    remaining_lessons = cur.fetchall()
    assert len(remaining_lessons) == 1
    assert remaining_lessons[0][0] == "l1"
    assert remaining_lessons[0][1] == 5  # 2 + 3

    # Verify orphaned edge pruned
    cur.execute("SELECT source_id, target_id FROM kg_edges")
    remaining_edges = cur.fetchall()
    assert len(remaining_edges) == 1
    assert remaining_edges[0] == ("n1", "n2")

    # Verify stale telemetry edge compacted
    cur.execute("SELECT caller, callee FROM telemetry_call_edges")
    remaining_telemetry = cur.fetchall()
    assert len(remaining_telemetry) == 1
    assert remaining_telemetry[0] == ("c1", "c3")

    conn.close()
