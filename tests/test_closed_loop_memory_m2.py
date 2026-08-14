"""
tests.test_closed_loop_memory_m2
Unit tests for Milestone 2 closed-loop memory logging and database schema unification.
"""

import os
import json
import sqlite3
import pytest
import time
from pathlib import Path

from vazus_core.db import get_db_connection, init_db_schemas
from vazus_core.organic_memory_bridge import (
    record_code_optimization,
    get_recent_optimizations,
    search_optimization_insights,
    record_insight,
    search_memory,
    get_organic_summary
)
from vazus_core.supergraph_linker import SuperGraphLinker


def test_db_schema_unification(tmp_path):
    test_db = tmp_path / "test_vazus_unified.db"
    conn = get_db_connection(test_db)
    
    # Check tables exist
    cursor = conn.cursor()
    tables = [row[0] for row in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    assert "organic_insights" in tables
    assert "kg_nodes" in tables
    assert "kg_edges" in tables

    # Check WAL mode
    journal_mode = cursor.execute("PRAGMA journal_mode;").fetchone()[0]
    assert journal_mode.lower() == "wal"
    conn.close()


def test_record_code_optimization(tmp_path):
    test_db = tmp_path / "test_opt_memory.db"
    
    before_metrics = {"ast_tokens": 1000, "exec_time_ms": 100.0, "memory_bytes": 50000}
    after_metrics = {"ast_tokens": 220, "exec_time_ms": 25.0, "memory_bytes": 10000}
    
    result = record_code_optimization(
        module_name="vazus_core.ast_pruner",
        optimization_type="ast_signature_compression",
        before_metrics=before_metrics,
        after_metrics=after_metrics,
        ast_reduction_pct=78.0,
        speedup_pct=300.0,
        memory_reduction_bytes=40000,
        db_path=str(test_db)
    )
    
    assert result["status"] == "SUCCESS"
    assert result["module_name"] == "vazus_core.ast_pruner"
    assert result["ast_reduction_pct"] == 78.0
    assert result["speedup_pct"] == 300.0
    assert result["memory_reduction_bytes"] == 40000
    assert result["node_id"].startswith("opt:vazus_core.ast_pruner:")

    # Verify organic_insights database row
    conn = get_db_connection(test_db)
    cur = conn.cursor()
    row = cur.execute("SELECT category, insight, timestamp FROM organic_insights WHERE category = 'code_optimization'").fetchone()
    assert row is not None
    payload = json.loads(row["insight"])
    assert payload["module_name"] == "vazus_core.ast_pruner"
    assert payload["ast_reduction_pct"] == 78.0

    # Verify kg_nodes database row with 768-dim vector embedding
    kg_row = cur.execute("SELECT id, name, domain, node_type, properties, embedding_json FROM kg_nodes WHERE domain = 'code_optimization'").fetchone()
    assert kg_row is not None
    assert kg_row["id"] == result["node_id"]
    assert kg_row["node_type"] == "verified_refactor"
    
    embedding = json.loads(kg_row["embedding_json"])
    assert isinstance(embedding, list)
    assert len(embedding) == 768
    conn.close()


def test_get_recent_optimizations(tmp_path):
    test_db = tmp_path / "test_recent_opt.db"
    
    record_code_optimization(
        module_name="vazus_core.embeddings",
        optimization_type="lru_cache_refactor",
        before_metrics={"ast_tokens": 500},
        after_metrics={"ast_tokens": 100},
        ast_reduction_pct=80.0,
        speedup_pct=150.0,
        memory_reduction_bytes=5000,
        db_path=str(test_db)
    )
    
    recent = get_recent_optimizations(limit=10, db_path=str(test_db))
    assert len(recent) == 1
    assert recent[0]["module_name"] == "vazus_core.embeddings"
    assert recent[0]["optimization_type"] == "lru_cache_refactor"


def test_search_optimization_insights(tmp_path):
    test_db = tmp_path / "test_search_opt.db"
    
    record_code_optimization(
        module_name="vazus_core.ast_pruner",
        optimization_type="ast_signature_compression",
        before_metrics={"ast_tokens": 1000},
        after_metrics={"ast_tokens": 200},
        ast_reduction_pct=80.0,
        speedup_pct=250.0,
        memory_reduction_bytes=10000,
        db_path=str(test_db)
    )
    
    search_res = search_optimization_insights("ast_signature_compression", top_k=5, db_path=str(test_db))
    assert len(search_res) > 0
    assert search_res[0]["domain"] == "code_optimization"


def test_supergraph_linker_schema_init(tmp_path):
    test_db = tmp_path / "test_supergraph.db"
    linker = SuperGraphLinker(db_path=test_db)
    
    conn = get_db_connection(test_db)
    cursor = conn.cursor()
    tables = [row[0] for row in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    assert "organic_insights" in tables
    assert "kg_nodes" in tables
    assert "kg_edges" in tables
    assert "llm_cache" in tables
    conn.close()


def test_wikilink_recommendations_threshold(tmp_path):
    from vazus_core.organic_memory_bridge import recommend_wikilinks, recommend_wikilinks_for_insight
    test_db = tmp_path / "test_wikilink_rec.db"

    # Insert two highly similar nodes
    r1 = record_insight(
        category="architecture",
        insight="Karpathy Memory Wiki semantic markdown notes linking and Zettelkasten Obsidian format",
        db_path=str(test_db)
    )

    r2 = record_insight(
        category="architecture",
        insight="Obsidian Zettelkasten Markdown notes exporter for Karpathy Memory Wiki index",
        db_path=str(test_db)
    )

    # Test wikilink recommendation with threshold 0.70
    recs = recommend_wikilinks(
        text_or_query="Karpathy Memory Wiki Zettelkasten Obsidian notes",
        threshold=0.70,
        top_k=5,
        db_path=str(test_db)
    )

    assert len(recs) > 0
    for rec in recs:
        assert rec["similarity"] >= 0.70
        assert rec["wikilink"].startswith("[[Zettel_")
        assert "wikilink_annotated" in rec

    # Test recommend_wikilinks_for_insight helper
    wikilink_strings = recommend_wikilinks_for_insight(
        insight_text="Karpathy Memory Wiki Zettelkasten Obsidian notes",
        threshold=0.70,
        top_k=5,
        db_path=str(test_db)
    )
    assert len(wikilink_strings) > 0
    assert wikilink_strings[0].startswith("[[Zettel_")


def test_record_insight_auto_wikilinks(tmp_path):
    test_db = tmp_path / "test_auto_wikilinks.db"

    # Seed first insight
    record_insight(
        category="performance",
        insight="Optimized 768D float vector similarity matrix multiplication using NumPy 2D dot product",
        db_path=str(test_db)
    )

    # Record second insight similar to the first
    res = record_insight(
        category="performance",
        insight="Fast 768D vector space dot product matrix multiplication for NumPy similarity",
        db_path=str(test_db),
        auto_wikilink_threshold=0.70
    )

    assert res["status"] == "SUCCESS"
    assert "wikilink_recommendations" in res
    assert len(res["wikilink_recommendations"]) > 0

    # Verify RECOMMENDED_WIKILINK edge in kg_edges
    conn = get_db_connection(test_db)
    cur = conn.cursor()
    edge = cur.execute("SELECT source_id, target_id, relation, strength FROM kg_edges WHERE relation = 'RECOMMENDED_WIKILINK'").fetchone()
    assert edge is not None
    assert edge["relation"] == "RECOMMENDED_WIKILINK"
    assert edge["strength"] >= 0.70
    conn.close()

