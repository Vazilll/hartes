import json
import pytest
import sqlite3
import sqlite_vec
from unittest.mock import patch

import sys
from pathlib import Path
sys.path.insert(0, str(Path(r"C:\vazus").resolve()))

from vazus_core.memory.db import get_db_connection, init_db_schemas, _init_vector_tables
from vazus_core.memory.organic_memory_bridge import record_insight
from scripts.vazus_organic_mcp import vazus_record_insight


@pytest.fixture
def memory_db():
    """Creates a temporary in-memory database with full vazus schemas and sqlite-vec loaded."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    init_db_schemas(conn)
    return conn


def test_sqlite_vec_version():
    """Verify sqlite-vec extension is present and can report version."""
    assert sqlite_vec is not None
    conn = sqlite3.connect(":memory:")
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    version = conn.execute("SELECT vec_version();").fetchone()[0]
    assert version.startswith("v0.")
    conn.close()


def test_vec_kg_nodes_schema_and_shadow_tables(memory_db):
    """Verify vec_kg_nodes is created as a virtual table with all necessary shadow tables."""
    cur = memory_db.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'vec_kg_nodes%';")
    tables = {r[0] for r in cur.fetchall()}
    assert "vec_kg_nodes" in tables
    assert "vec_kg_nodes_info" in tables
    assert "vec_kg_nodes_chunks" in tables
    assert "vec_kg_nodes_rowids" in tables
    assert "vec_kg_nodes_vector_chunks00" in tables
    assert "vec_kg_nodes_metadatachunks00" in tables
    assert "vec_kg_nodes_metadatatext00" in tables

    # Querying count must not raise 'could not initialize insert rowids id statement' or other errors
    cnt = cur.execute("SELECT count(*) FROM vec_kg_nodes;").fetchone()[0]
    assert cnt == 0


def test_triggers_insert_update_delete(memory_db):
    """Verify trg_kg_nodes_insert, trg_kg_nodes_update, and trg_kg_nodes_delete sync vectors properly."""
    cur = memory_db.cursor()
    v1 = json.dumps([0.1] * 768)
    v2 = json.dumps([0.5] * 768)

    # 1. Insert into kg_nodes
    cur.execute("""
        INSERT INTO kg_nodes (id, name, domain, node_type, description, tags, properties, embedding_json)
        VALUES (?, ?, 'test_domain', 'test_node', 'description', 'tag1', '{}', ?)
    """, ("node_unit_1", "Node Unit 1", v1))
    memory_db.commit()

    # Check sync to vec_kg_nodes
    cnt = cur.execute("SELECT count(*) FROM vec_kg_nodes WHERE node_id = 'node_unit_1';").fetchone()[0]
    assert cnt == 1

    # KNN search test
    knn_rows = cur.execute("""
        SELECT node_id, distance
        FROM vec_kg_nodes
        WHERE embedding MATCH ? AND k = 1;
    """, (v1,)).fetchall()
    assert len(knn_rows) == 1
    assert knn_rows[0][0] == "node_unit_1"
    assert pytest.approx(knn_rows[0][1], abs=1e-4) == 0.0

    # 2. Update embedding in kg_nodes
    cur.execute("""
        UPDATE kg_nodes SET embedding_json = ? WHERE id = ?
    """, (v2, "node_unit_1"))
    memory_db.commit()

    cnt_after_upd = cur.execute("SELECT count(*) FROM vec_kg_nodes WHERE node_id = 'node_unit_1';").fetchone()[0]
    assert cnt_after_upd == 1

    # Search with v2 matches at 0 distance
    knn_v2 = cur.execute("""
        SELECT node_id, distance
        FROM vec_kg_nodes
        WHERE embedding MATCH ? AND k = 1;
    """, (v2,)).fetchall()
    assert knn_v2[0][0] == "node_unit_1"
    assert pytest.approx(knn_v2[0][1], abs=1e-4) == 0.0

    # 3. Delete from kg_nodes
    cur.execute("DELETE FROM kg_nodes WHERE id = 'node_unit_1';")
    memory_db.commit()

    cnt_after_del = cur.execute("SELECT count(*) FROM vec_kg_nodes WHERE node_id = 'node_unit_1';").fetchone()[0]
    assert cnt_after_del == 0


def test_insert_or_replace_deduplication(memory_db):
    """Verify that INSERT OR REPLACE into kg_nodes does not produce duplicate rows in vec_kg_nodes."""
    cur = memory_db.cursor()
    v1 = json.dumps([0.2] * 768)
    v2 = json.dumps([0.3] * 768)

    # First insert
    cur.execute("""
        INSERT OR REPLACE INTO kg_nodes (id, name, domain, node_type, description, tags, properties, embedding_json)
        VALUES (?, ?, 'organic_memory', 'insight', 'desc', 'tag', '{}', ?)
    """, ("dedup_test_node", "Dedup 1", v1))
    memory_db.commit()
    assert cur.execute("SELECT count(*) FROM vec_kg_nodes WHERE node_id = 'dedup_test_node';").fetchone()[0] == 1

    # Second insert with REPLACE
    cur.execute("""
        INSERT OR REPLACE INTO kg_nodes (id, name, domain, node_type, description, tags, properties, embedding_json)
        VALUES (?, ?, 'organic_memory', 'insight', 'desc', 'tag', '{}', ?)
    """, ("dedup_test_node", "Dedup 2", v2))
    memory_db.commit()
    assert cur.execute("SELECT count(*) FROM vec_kg_nodes WHERE node_id = 'dedup_test_node';").fetchone()[0] == 1


def test_self_healing_recovers_corrupted_virtual_table():
    """Verify that _init_vector_tables automatically recovers if shadow tables are corrupted or missing."""
    conn = sqlite3.connect(":memory:")
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    init_db_schemas(conn)

    # Insert a node into kg_nodes
    v = json.dumps([0.4] * 768)
    conn.execute("INSERT INTO kg_nodes (id, name, embedding_json) VALUES ('heal_node_1', 'Heal 1', ?);", (v,))
    conn.commit()
    assert conn.execute("SELECT count(*) FROM vec_kg_nodes WHERE node_id = 'heal_node_1';").fetchone()[0] == 1

    # Simulate damage by dropping vec_kg_nodes_rowids
    conn.execute("DROP TABLE vec_kg_nodes_rowids;")

    # Now query should fail with missing table error
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("SELECT count(*) FROM vec_kg_nodes;").fetchone()

    # Re-run _init_vector_tables
    _init_vector_tables(conn)

    # Table must now be repaired, queryable, and backfilled from kg_nodes
    cnt = conn.execute("SELECT count(*) FROM vec_kg_nodes WHERE node_id = 'heal_node_1';").fetchone()[0]
    assert cnt == 1

    # Insert after self-healing works without errors
    v2 = json.dumps([0.5] * 768)
    conn.execute("INSERT INTO kg_nodes (id, name, embedding_json) VALUES ('heal_node_2', 'Heal 2', ?);", (v2,))
    conn.commit()
    assert conn.execute("SELECT count(*) FROM vec_kg_nodes WHERE node_id = 'heal_node_2';").fetchone()[0] == 1
    conn.close()


def test_record_insight_end_to_end(tmp_path):
    """Verify record_insight inserts into organic_insights, kg_nodes, and vec_kg_nodes without errors."""
    test_db = str(tmp_path / "test_vazus.db")
    res = record_insight(
        category="unit_test_cat",
        insight="End to end verification insight for sqlite-vec fix",
        db_path=test_db
    )
    assert res["status"] == "SUCCESS"
    assert res["node_id"].startswith("insight_")

    conn = get_db_connection(test_db)
    cur = conn.cursor()

    # Check organic_insights
    cur.execute("SELECT insight, category FROM organic_insights WHERE node_id = ?;", (res["node_id"],))
    ins_row = cur.fetchone()
    assert ins_row is not None
    assert ins_row[0] == "End to end verification insight for sqlite-vec fix"
    assert ins_row[1] == "unit_test_cat"

    # Check kg_nodes
    cur.execute("SELECT id, name, domain, node_type FROM kg_nodes WHERE id = ?;", (res["node_id"],))
    node_row = cur.fetchone()
    assert node_row is not None
    assert node_row[0] == res["node_id"]

    # Check vec_kg_nodes
    cur.execute("SELECT count(*) FROM vec_kg_nodes WHERE node_id = ?;", (res["node_id"],))
    vec_cnt = cur.fetchone()[0]
    assert vec_cnt == 1

    conn.close()


def test_vazus_record_insight_mcp_wrapper(tmp_path):
    """Verify vazus_record_insight tool in vazus_organic_mcp handles calls properly."""
    test_db = str(tmp_path / "test_mcp_vazus.db")
    with patch.dict("os.environ", {"VAZUS_DB_PATH": test_db}):
        raw_json = vazus_record_insight(
            category="mcp_test_cat",
            insight="Testing vazus_record_insight MCP wrapper function"
        )
        data = json.loads(raw_json)
        assert data["status"] == "SUCCESS"
        assert data["category"] == "mcp_test_cat"
        assert "node_id" in data

        conn = get_db_connection(test_db)
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM vec_kg_nodes WHERE node_id = ?;", (data["node_id"],))
        assert cur.fetchone()[0] == 1
        conn.close()
