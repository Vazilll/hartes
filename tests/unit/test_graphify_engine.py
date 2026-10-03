"""
Tests for vazus_core.engine.graphify_engine — GraphifyASTVisitor + GraphifyEngine.

Covers:
  - GraphifyASTVisitor: correct extraction of nodes (Module, Class, Function)
    and edges (DEFINES, INHERITS, CALLS, IMPORTS)
  - GraphifyEngine.index_codebase: persists into SQLite graphify_nodes / graphify_edges
  - GraphifyEngine.get_compact_subgraph_context: returns deterministic topology string
"""
from __future__ import annotations

import ast
import sqlite3
from pathlib import Path


from vazus_core.engine.graphify_engine import GraphifyASTVisitor, GraphifyEngine


SAMPLE_SOURCE = '''
import os
from pathlib import Path

class MyService:
    """A demo service."""

    def process(self, data: str) -> str:
        result = helper(data)
        return result

def helper(x):
    return x.strip()
'''


class TestGraphifyASTVisitor:
    def _parse(self, src: str, rel: str = "demo.py") -> GraphifyASTVisitor:
        tree = ast.parse(src)
        visitor = GraphifyASTVisitor(rel)
        visitor.visit(tree)
        return visitor

    def test_module_node_created(self):
        v = self._parse(SAMPLE_SOURCE, "demo.py")
        node_types = [n["type"] for n in v.nodes]
        assert "Module" in node_types

    def test_class_node_extracted(self):
        v = self._parse(SAMPLE_SOURCE, "demo.py")
        names = [n["name"] for n in v.nodes]
        assert "MyService" in names

    def test_function_nodes_extracted(self):
        v = self._parse(SAMPLE_SOURCE, "demo.py")
        names = [n["name"] for n in v.nodes]
        assert "process" in names
        assert "helper" in names

    def test_defines_edges_present(self):
        v = self._parse(SAMPLE_SOURCE, "demo.py")
        edge_types = [e["type"] for e in v.edges]
        assert "DEFINES" in edge_types

    def test_import_edges_present(self):
        v = self._parse(SAMPLE_SOURCE, "demo.py")
        edge_types = [e["type"] for e in v.edges]
        assert "IMPORTS" in edge_types

    def test_calls_edge_present(self):
        v = self._parse(SAMPLE_SOURCE, "demo.py")
        edge_types = [e["type"] for e in v.edges]
        assert "CALLS" in edge_types

    def test_inherits_edge_for_subclass(self):
        src = "class Child(Parent): pass"
        v = self._parse(src, "child.py")
        inherit_edges = [e for e in v.edges if e["type"] == "INHERITS"]
        assert any(e["target"] == "Parent" for e in inherit_edges)

    def test_async_function_node_type(self):
        src = "async def fetch(): pass"
        v = self._parse(src, "async_mod.py")
        async_nodes = [n for n in v.nodes if n["type"] == "AsyncFunction"]
        assert len(async_nodes) == 1
        assert async_nodes[0]["name"] == "fetch"


class TestGraphifyEngine:
    def _make_engine(self, tmp_path: Path) -> GraphifyEngine:
        db = str(tmp_path / "test_graphify.db")
        # Write a sample Python file
        code_dir = tmp_path / "src"
        code_dir.mkdir()
        (code_dir / "sample.py").write_text(SAMPLE_SOURCE, encoding="utf-8")
        engine = GraphifyEngine(db_path=db, workspace_root=str(tmp_path))
        return engine, code_dir

    def test_index_codebase_returns_counts(self, tmp_path):
        engine, code_dir = self._make_engine(tmp_path)
        result = engine.index_codebase(target_dir_rel="src")
        assert result["indexed_nodes"] > 0
        assert result["indexed_edges"] >= 0

    def test_nodes_persisted_in_db(self, tmp_path):
        engine, code_dir = self._make_engine(tmp_path)
        engine.index_codebase(target_dir_rel="src")

        with sqlite3.connect(engine.db_path) as conn:
            rows = conn.execute("SELECT COUNT(*) FROM graphify_nodes").fetchone()
        assert rows[0] > 0

    def test_edges_persisted_in_db(self, tmp_path):
        engine, code_dir = self._make_engine(tmp_path)
        engine.index_codebase(target_dir_rel="src")

        with sqlite3.connect(engine.db_path) as conn:
            rows = conn.execute("SELECT COUNT(*) FROM graphify_edges").fetchone()
        assert rows[0] > 0

    def test_get_compact_subgraph_not_found(self, tmp_path):
        engine, _ = self._make_engine(tmp_path)
        result = engine.get_compact_subgraph_context("NonExistentSymbol99")
        assert "not found" in result.lower() or "NonExistentSymbol99" in result

    def test_get_compact_subgraph_finds_indexed_symbol(self, tmp_path):
        engine, _ = self._make_engine(tmp_path)
        engine.index_codebase(target_dir_rel="src")
        result = engine.get_compact_subgraph_context("MyService")
        assert "MyService" in result
        assert "GRAPHIFY TOPOLOGY" in result

    def test_idempotent_reindex(self, tmp_path):
        """Indexing twice should not raise errors (INSERT OR REPLACE / IGNORE)."""
        engine, _ = self._make_engine(tmp_path)
        engine.index_codebase(target_dir_rel="src")
        engine.index_codebase(target_dir_rel="src")  # no exception

    def test_compute_node_centrality_and_top_symbols(self, tmp_path):
        """Tests PageRank centrality calculation and retrieval of top structural hubs."""
        engine, code_dir = self._make_engine(tmp_path)
        engine.index_codebase(target_dir_rel="src")

        centrality_scores = engine.compute_node_centrality()
        assert len(centrality_scores) > 0
        assert all(s >= 0.0 for s in centrality_scores.values())

        top_symbols = engine.get_top_central_symbols(top_k=5)
        assert len(top_symbols) > 0
        assert "name" in top_symbols[0]
        assert "centrality" in top_symbols[0]

    def test_scan_go_file_polyglot(self, tmp_path):
        """Tests Polyglot Go source scanning."""
        engine, code_dir = self._make_engine(tmp_path)
        go_file = code_dir / "service.go"
        go_code = '''
package main

import "fmt"

type OrderProcessor struct {
    ID string
}

func (o *OrderProcessor) Process() bool {
    return true
}

func MainHelper() string {
    return "ok"
}
'''
        go_file.write_text(go_code, encoding="utf-8")
        result = engine.index_codebase(target_dir_rel="src")

        assert result["indexed_nodes"] > 0
        subgraph = engine.get_compact_subgraph_context("OrderProcessor")
        assert "OrderProcessor" in subgraph or "GRAPHIFY TOPOLOGY" in subgraph

    def test_pack_binary_frame_and_ipc_streaming(self, tmp_path):
        """Tests 64-byte binary frame packing with magic 0x565A5553 and IPC streaming."""
        engine, code_dir = self._make_engine(tmp_path)
        frame = engine.pack_binary_frame(frame_type=1, symbol_id=10, hash_64=999, payload=b"test_payload")
        assert len(frame) == 64
        import struct
        magic, f_type, flags, p_len, sym_id, ts, h64, payload = struct.unpack("<IHHIIQQ32s", frame)
        assert magic == 0x565A5553
        assert f_type == 1
        assert sym_id == 10
        assert h64 == 999
        assert payload.startswith(b"test_payload")

    def test_index_file_ast_streaming(self, tmp_path):
        """Tests index_file_ast single file parsing and streaming."""
        engine, code_dir = self._make_engine(tmp_path)
        rel_path = "src/sample.py"
        res = engine.index_file_ast(rel_path, source_code=SAMPLE_SOURCE)
        assert res["nodes"] > 0
        assert res["edges"] > 0
        assert res["frames_streamed"] > 0

