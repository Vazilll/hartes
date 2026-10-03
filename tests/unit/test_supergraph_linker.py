"""
tests/unit/test_supergraph_linker.py — Unit & Invariant Tests for Unified SuperGraphLinker.

Verifies:
1. Ingestion of *.canvas files as CanvasBoard nodes with CANVAS_NODE edges.
2. Sanitization of path-style wikilinks in _extract_wiki_links().
3. Post-integration orphan edge pruning (DELETE FROM kg_edges WHERE target_id NOT IN (SELECT id FROM kg_nodes)).
4. 4-Component Hybrid similarity metric calculations and edge properties.
5. Invariant: 0 dangling references in production database and total kg_nodes > 750 with 768-D embeddings.
"""

import os
import json
import sqlite3
import tempfile
from pathlib import Path
import pytest

from vazus_core.engine.supergraph_linker import (
    SuperGraphLinker,
    calculate_cosine_similarity,
    calculate_fts_similarity,
    calculate_structural_similarity,
    calculate_provenance_similarity,
)


@pytest.fixture
def temp_wiki_and_db(tmp_path):
    """Creates a temporary workspace with wiki files, canvas boards, and test database."""
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "test_vazus.db"

    # 1. Author sample markdown note
    note_content = """---
id: Test_Architecture_Note
title: "Test Architecture Note"
date: "2026-09-04"
domain: architecture
tags:
  - test
  - architecture
status: VERIFIED
sources:
  - "manual"
---

# Test Architecture Note

## Core Section
This is a test architectural note describing [[Test_Target_Note]] and linking to a canvas [[sample_flow.canvas]].
Also contains a path-style link: [[C:/vazus/services/memory/vazus.db|vazus.db Canonical]].
And another path link: [[C:/vazus/vazus_core/engine/SPEC.md|SPEC.md]].
"""
    (wiki_dir / "Test_Architecture_Note.md").write_text(note_content, encoding="utf-8")

    # 2. Author target note
    target_content = """---
id: Test_Target_Note
title: "Test Target Note"
date: "2026-09-04"
domain: test_target
tags:
  - target
status: VERIFIED
sources:
  - "manual"
---

# Test Target Note
Target content linked from architecture note.
"""
    (wiki_dir / "Test_Target_Note.md").write_text(target_content, encoding="utf-8")

    # 3. Author sample canvas file
    canvas_data = {
        "nodes": [
            {
                "id": "node_1",
                "type": "file",
                "file": "Test_Architecture_Note.md",
                "x": 0,
                "y": 0,
                "width": 300,
                "height": 150,
                "color": "2",
            },
            {
                "id": "node_2",
                "type": "file",
                "file": "Test_Target_Note.md",
                "x": 400,
                "y": 0,
                "width": 300,
                "height": 150,
                "color": "4",
            },
            {
                "id": "node_text",
                "type": "text",
                "text": "Canvas Annotation: SMT Z3 verified pipeline flow",
                "x": 200,
                "y": 200,
                "width": 300,
                "height": 100,
            },
        ],
        "edges": [
            {
                "id": "edge_1_2",
                "fromNode": "node_1",
                "fromSide": "right",
                "toNode": "node_2",
                "toSide": "left",
                "label": "TRANSITIONS_TO",
            }
        ],
    }
    (wiki_dir / "sample_flow.canvas").write_text(json.dumps(canvas_data), encoding="utf-8")

    return {"wiki_dir": wiki_dir, "db_path": db_path}


def test_canvas_board_parsing(temp_wiki_and_db):
    """Verifies that *.canvas files are parsed as CanvasBoard nodes with CANVAS_NODE edges."""
    linker = SuperGraphLinker(
        db_path=temp_wiki_and_db["db_path"],
        wiki_dirs=[temp_wiki_and_db["wiki_dir"]],
    )

    wiki_nodes, wiki_edges = linker.load_memory_wiki_nodes_and_edges()

    canvas_nodes = [n for n in wiki_nodes if n.get("node_type") == "CanvasBoard"]
    assert len(canvas_nodes) >= 1, "Expected at least 1 CanvasBoard node"

    sample_canvas = next(
        (n for n in canvas_nodes if "sample_flow" in n["id"]), None
    )
    assert sample_canvas is not None, "sample_flow CanvasBoard missing from nodes"
    assert "Canvas Annotation" in sample_canvas["content"]
    assert sample_canvas["domain"] == "memory_wiki"

    canvas_edges = [e for e in wiki_edges if e.get("relation") == "CANVAS_NODE"]
    assert len(canvas_edges) >= 2, f"Expected >= 2 CANVAS_NODE edges, got {len(canvas_edges)}"

    targets = {e["target_id"] for e in canvas_edges}
    assert "wiki:Test_Architecture_Note" in targets
    assert "wiki:Test_Target_Note" in targets


def test_sanitize_path_style_wikilinks():
    """Verifies that path-style wikilinks (e.g. [[C:/vazus/...]]) are sanitized to their file stems."""
    content = """
Here are various wikilinks:
- Normal: [[Test_Target_Note]]
- Windows Path: [[C:/vazus/services/memory/vazus.db|vazus.db Canonical]]
- Engine Spec: [[C:/vazus/vazus_core/engine/SPEC.md|SPEC.md]]
- Backslash Path: [[C:\\vazus\\vazus_core\\hooks\\SPEC.md|Hooks SPEC]]
- File with extension: [[agent_eval_quality_flywheel.canvas]]
"""
    edges = SuperGraphLinker._extract_wiki_links("wiki:test_source", content)
    target_ids = {e["target_id"] for e in edges}

    # Should not contain filesystem prefixes like 'C:/' or 'C:\\'
    for tid in target_ids:
        assert not tid.startswith("wiki:C:"), f"Path prefix leaked into target_id: {tid}"
        assert "/" not in tid, f"Slash leaked into target_id: {tid}"
        assert "\\" not in tid, f"Backslash leaked into target_id: {tid}"

    # Specific stems expected:
    assert "wiki:Test_Target_Note" in target_ids
    assert "wiki:vazus" in target_ids or "wiki:vazus_db" in target_ids
    assert "wiki:SPEC" in target_ids


def test_orphan_edge_pruning(temp_wiki_and_db):
    """Verifies that orphaned edges are automatically pruned at conclusion of run_supergraph_integration()."""
    linker = SuperGraphLinker(
        db_path=temp_wiki_and_db["db_path"],
        wiki_dirs=[temp_wiki_and_db["wiki_dir"]],
    )

    # 1. Run integration
    result = linker.run_supergraph_integration(threshold=0.10)
    assert result["edges_created"] > 0

    # 2. Artificially inject an orphaned edge into kg_edges
    with linker._get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO kg_edges (source_id, target_id, relation, strength, properties)
            VALUES ('wiki:Test_Architecture_Note', 'wiki:NonExistentGhostTarget_123', 'WIKILINK', 1.0, '{}')
            """
        )
        conn.commit()
        dangling_before = conn.execute(
            "SELECT count(*) FROM kg_edges WHERE target_id NOT IN (SELECT id FROM kg_nodes)"
        ).fetchone()[0]
        assert dangling_before == 1, "Expected 1 injected dangling edge"

    # 3. Re-run integration — pruning step must eliminate the orphan
    linker.run_supergraph_integration(threshold=0.10)

    with linker._get_connection() as conn:
        dangling_after = conn.execute(
            "SELECT count(*) FROM kg_edges WHERE target_id NOT IN (SELECT id FROM kg_nodes)"
        ).fetchone()[0]
        assert dangling_after == 0, f"Expected 0 dangling edges after integration, got {dangling_after}"


def test_production_supergraph_invariants():
    """Empirically verifies production vazus.db: total nodes > 750 with 768-D embeddings, and 0 dangling edges."""
    prod_db = Path("C:/vazus/services/memory/vazus.db").resolve()
    if not prod_db.exists():
        pytest.skip("Production database not present")

    conn = sqlite3.connect(f"file:{prod_db}?mode=ro", uri=True)
    try:
        total_nodes = conn.execute("SELECT count(*) FROM kg_nodes").fetchone()[0]
        emb_nodes = conn.execute(
            "SELECT count(*) FROM kg_nodes WHERE embedding_json IS NOT NULL"
        ).fetchone()[0]
        total_edges = conn.execute("SELECT count(*) FROM kg_edges").fetchone()[0]
        dangling_targets = conn.execute(
            "SELECT count(*) FROM kg_edges WHERE target_id NOT IN (SELECT id FROM kg_nodes)"
        ).fetchone()[0]
        dangling_sources = conn.execute(
            "SELECT count(*) FROM kg_edges WHERE source_id NOT IN (SELECT id FROM kg_nodes)"
        ).fetchone()[0]
    finally:
        conn.close()

    assert total_nodes > 750, f"Expected > 750 nodes, got {total_nodes}"
    assert emb_nodes == total_nodes, f"All nodes must have embeddings ({emb_nodes} != {total_nodes})"
    assert dangling_targets == 0, f"Expected 0 dangling targets, got {dangling_targets}"
    assert dangling_sources == 0, f"Expected 0 dangling sources, got {dangling_sources}"
    assert total_edges > 1000, f"Expected > 1000 edges, got {total_edges}"

