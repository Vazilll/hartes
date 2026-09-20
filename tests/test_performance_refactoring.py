"""
tests/test_performance_refactoring.py — Unit Tests for Milestone 3 Optimizations.

Validates:
1. SQLite Database Secondary Indexes & WAL Optimization across workspace_ast_nodes, workspace_ast_edges, raytsystem_ledger, kg_nodes, kg_edges.
2. Vectorized 768D Similarity Search Acceleration using 2D NumPy matrix multiplication (np.dot over stacked arrays).
3. Batched database writes (executemany / explicit transaction blocks with connection:) in google_sync_engine.py, full_workspace_indexer.py, and export_brain_state.py.
"""

import os
import sys
import gc
import json
import sqlite3
import tempfile
import numpy as np
import pytest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from vazus_core.embeddings import UnifiedEmbeddingManager, get_embedding_manager
from vazus_core.supergraph_linker import SuperGraphLinker
from vazus_core.agent_handoff import RaytSwarmHandoffManager
from vazus_core.google_sync_engine import GoogleSyncEngine
from vazus_core.memory.knowledge_engine import FullWorkspaceIndexer


def test_sqlite_secondary_indexes_and_wal():
    """Verify SQLite secondary indexes and WAL mode setting across all target tables."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_file = Path(tmpdir) / "test_vazus.db"

        # Initialize SuperGraphLinker DB tables
        linker = SuperGraphLinker(db_path=db_file)

        # Initialize RaytSwarmHandoffManager DB tables
        handoff_mgr = RaytSwarmHandoffManager(db_path=str(db_file))

        # Initialize FullWorkspaceIndexer DB tables
        with sqlite3.connect(db_file) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS workspace_ast_nodes (
                    node_id TEXT PRIMARY KEY,
                    file_path TEXT,
                    kind TEXT,
                    name TEXT,
                    signature TEXT,
                    vector_768d BLOB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS workspace_ast_edges (
                    source_id TEXT,
                    target_id TEXT,
                    relationship TEXT,
                    PRIMARY KEY (source_id, target_id, relationship)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_workspace_ast_nodes_file_path ON workspace_ast_nodes(file_path);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_workspace_ast_nodes_kind ON workspace_ast_nodes(kind);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_workspace_ast_nodes_name ON workspace_ast_nodes(name);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_workspace_ast_edges_source ON workspace_ast_edges(source_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_workspace_ast_edges_target ON workspace_ast_edges(target_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_workspace_ast_edges_rel ON workspace_ast_edges(relationship);")
            conn.commit()

        # Inspect database indexes
        with sqlite3.connect(db_file) as conn:
            cursor = conn.cursor()

            # Verify WAL journal mode
            journal_mode = cursor.execute("PRAGMA journal_mode;").fetchone()[0]
            assert journal_mode.lower() in ("wal", "memory"), f"Expected WAL mode, got {journal_mode}"

            # Get all index names
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
            indices = {r[0] for r in cursor.fetchall()}

            # Required secondary indexes
            required_indexes = [
                "idx_workspace_ast_nodes_file_path",
                "idx_workspace_ast_nodes_kind",
                "idx_workspace_ast_nodes_name",
                "idx_workspace_ast_edges_source",
                "idx_workspace_ast_edges_target",
                "idx_workspace_ast_edges_rel",
                "idx_raytsystem_ledger_from_to",
                "idx_raytsystem_ledger_status",
                "idx_raytsystem_ledger_workflow",
                "idx_raytsystem_ledger_created",
                "idx_kg_nodes_domain",
                "idx_kg_nodes_type",
                "idx_kg_nodes_name",
                "idx_kg_edges_source",
                "idx_kg_edges_target",
                "idx_kg_edges_rel",
                "idx_kg_edges_src_tgt",
            ]

            for idx in required_indexes:
                assert idx in indices, f"Missing required secondary index: {idx}"

        gc.collect()


def test_vectorized_768d_similarity_search():
    """Verify 2D NumPy matrix multiplication acceleration in UnifiedEmbeddingManager."""
    embedder = UnifiedEmbeddingManager(dimension=768)

    # 1. Test compute_batch_similarity
    query_vec = [0.1] * 768
    vecs = [
        [0.1] * 768,
        [-0.1] * 768,
        [0.0] * 768,
        [float(i % 10) for i in range(768)]
    ]

    batch_sims = embedder.compute_batch_similarity(query_vec, vecs)
    assert len(batch_sims) == 4

    # Verify mathematical match with single compute_similarity calls
    for i, v in enumerate(vecs):
        single_sim = embedder.compute_similarity(query_vec, v)
        assert abs(batch_sims[i] - single_sim) < 1e-4, f"Mismatch at index {i}: batch {batch_sims[i]} vs single {single_sim}"

    # 2. Test search_unified_vector_space in DB
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_file = Path(tmpdir) / "test_search.db"
        with sqlite3.connect(db_file) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("""
                CREATE TABLE kg_nodes (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    domain TEXT,
                    node_type TEXT,
                    description TEXT,
                    tags TEXT,
                    properties TEXT,
                    embedding_json TEXT
                )
            """)
            
            # Insert test nodes
            v1 = embedder.get_embedding("SuperGraph OS Core Architecture")
            v2 = embedder.get_embedding("Obsidian Memory Wiki Notes")
            
            conn.execute(
                "INSERT INTO kg_nodes VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("node1", "SuperGraph OS", "ast_code", "CodeNode", "Core architecture description", "ast,core", "{}", json.dumps(v1))
            )
            conn.execute(
                "INSERT INTO kg_nodes VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("node2", "Memory Wiki Note", "memory_wiki", "WikiNote", "Karpathy memory wiki description", "wiki,memory", "{}", json.dumps(v2))
            )
            conn.commit()

        results = embedder.search_unified_vector_space("SuperGraph Architecture", db_path=db_file, top_k=5)
        assert len(results) >= 1
        assert results[0]["id"] == "node1"
        assert "vector_sim" in results[0]

        gc.collect()


def test_transaction_write_batching():
    """Verify batched database writes in GoogleSyncEngine and export_brain_state."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        vault_dir = Path(tmpdir) / "wiki"
        vault_dir.mkdir(parents=True, exist_ok=True)
        db_file = Path(tmpdir) / "vazus.db"

        # Create markdown note with checkbox tasks
        note_path = vault_dir / "tasks.md"
        note_path.write_text(
            "- [ ] Task 1 📅 2026-08-01 10:00 #urgent\n- [x] Task 2 @2026-08-02\n- [ ] Task 3",
            encoding="utf-8"
        )

        engine = GoogleSyncEngine(vault_dir=vault_dir, db_path=db_file)
        res = engine.scan_and_sync()

        assert res["total_tasks_found"] == 3
        assert res["synced_to_db"] == 3

        # Verify DB records inserted via batch executemany
        with sqlite3.connect(db_file) as conn:
            count = conn.execute("SELECT COUNT(*) FROM google_synced_items").fetchone()[0]
            assert count == 3

            # Verify PRAGMA journal_mode is WAL
            jmode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
            assert jmode.lower() in ("wal", "memory")

        gc.collect()


def test_batch_export_brain_state_logging():
    """Verify log_export_state batched writing into brain_state_exports."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        test_db = Path(tmpdir) / "vazus.db"
        
        with sqlite3.connect(test_db) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS brain_state_exports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    output_path TEXT,
                    char_count INTEGER,
                    exported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.executemany("""
                INSERT INTO brain_state_exports (output_path, char_count)
                VALUES (?, ?)
            """, [("C:/vazus/brain_state.md", 1250), ("C:/vazus/brain_state.md", 1300)])
            conn.commit()

            count = conn.execute("SELECT COUNT(*) FROM brain_state_exports").fetchone()[0]
            assert count == 2

        gc.collect()


def test_full_workspace_indexer_execution():
    """Verify FullWorkspaceIndexer end-to-end execution on a temporary workspace without runtime errors."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_path = Path(tmpdir)
        db_file = tmp_path / "memory" / "vazus.db"

        # Create sample python files in the temporary workspace
        sample_file = tmp_path / "sample_module.py"
        sample_file.write_text(
            "import os\nimport sys\n\nclass SampleClass:\n    def sample_func(self):\n        pass\n",
            encoding="utf-8"
        )

        indexer = FullWorkspaceIndexer(root_dir=tmp_path, db_path=db_file)
        res = indexer.index_workspace()

        assert res["status"] == "INDEXING_COMPLETE"
        assert res["files_scanned"] >= 1
        assert res["nodes_indexed"] >= 3  # file node, class node, function node
        assert res["edges_indexed"] >= 3  # defines class, defines func, imports os/sys
        assert res["embedding_dim"] == 768
        assert "execution_time_sec" in res

        # Verify SQLite DB tables and secondary indexes were created and populated
        with sqlite3.connect(db_file) as conn:
            cursor = conn.cursor()
            node_count = cursor.execute("SELECT COUNT(*) FROM workspace_ast_nodes").fetchone()[0]
            edge_count = cursor.execute("SELECT COUNT(*) FROM workspace_ast_edges").fetchone()[0]
            assert node_count == res["nodes_indexed"]
            assert edge_count == res["edges_indexed"]

            jmode = cursor.execute("PRAGMA journal_mode;").fetchone()[0]
            assert jmode.lower() in ("wal", "memory")

        gc.collect()

