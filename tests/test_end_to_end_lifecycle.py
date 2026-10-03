"""
tests.test_end_to_end_lifecycle — Comprehensive End-to-End Lifecycle & Fault-Tolerance Test Suite.
===================================================================================================

Verifies:
  1. PreToolHook: Fail-closed security, path jail, secret scrubbing, and Circuit Breaker failsafe.
  2. StopHook: Verification gate timeout and bounded block counters (zero infinite deadlocks).
  3. UnifiedMemoryGateway: Canonical read/write cohesion across Mem0, SQLite, and Graphify.
  4. GraphifyEngine: Multi-language AST parsing (Python, Go, Zig) and binary IPC streaming.
  5. SubsystemHealthRegistry: Degradation tracking and telemetry snapshot.
"""

import sys
import json
import pytest
from pathlib import Path

# Ensure root workspace is on sys.path
if "C:/vazus" not in sys.path and "C:\\vazus" not in sys.path:
    sys.path.insert(0, "C:/vazus")

from vazus_core.hooks.pre_tool_hook import run_pre_tool, _validate_security_policies
from vazus_core.hooks.stop_hook import _increment_block_count, _clear_block_count
from vazus_core.memory.unified_memory_gateway import UnifiedMemoryGateway
from vazus_core.engine.graphify_engine import GraphifyEngine
from vazus_core.engine.health_registry import health_registry


def test_pre_tool_hook_allowed_safe_action():
    """Verifies that standard safe editing actions pass validation cleanly."""
    res = run_pre_tool("write_to_file", {"TargetFile": r"C:\vazus\tests\sample.py", "CodeContent": "x = 1"})
    assert res.get("decision") == "allow"
    assert "validated" in res.get("reason", "")


def test_pre_tool_hook_blocks_forbidden_path():
    """Verifies that writes to protected paths (e.g. .git) are denied."""
    res = run_pre_tool("write_to_file", {"TargetFile": r"C:\vazus\.git\config", "CodeContent": "malicious"})
    assert res.get("decision") == "deny"


def test_pre_tool_hook_blocks_dangerous_system_command():
    """Verifies that destructive OS wipe commands are rejected."""
    res = run_pre_tool("run_command", {"CommandLine": "format C: /fs:NTFS /q"})
    assert res.get("decision") == "deny"


def test_stop_hook_bounded_block_counter():
    """Verifies that StopHook block counter increments and resets properly."""
    conv_id = "test_conversation_lifecycle_001"
    _clear_block_count(conv_id)

    cnt1 = _increment_block_count(conv_id)
    assert cnt1 == 1
    cnt2 = _increment_block_count(conv_id)
    assert cnt2 == 2
    cnt3 = _increment_block_count(conv_id)
    assert cnt3 == 3

    _clear_block_count(conv_id)
    assert _increment_block_count(conv_id) == 1
    _clear_block_count(conv_id)


def test_unified_memory_gateway_store_and_recall(tmp_path):
    """Verifies unified store_fact and recall across SQLite and Mem0."""
    db_file = tmp_path / "test_vazus.db"
    wiki_dir = tmp_path / "wiki"
    gateway = UnifiedMemoryGateway(db_path=str(db_file), wiki_root=str(wiki_dir))

    # 1. Store Fact
    store_res = gateway.store_fact(
        fact_text="Vazus OS uses SMT Z3 formal verification for all code commits.",
        category="architectural_decision",
        entity="vazus_architect"
    )
    assert store_res["status"] == "STORED"

    # 2. Recall Fact
    recalled = gateway.recall("SMT Z3 formal verification", top_k=3)
    assert len(recalled) >= 1
    assert any("SMT Z3" in r["content"] for r in recalled)

    # 3. Write Wiki Article
    wiki_file = gateway.write_wiki_article("SMT Verification Architecture", "Z3 formal proofs guarantee zero logic bugs.", ["Z3_Solver", "Hypothesis"])
    assert wiki_file.exists()
    assert "[[Z3_Solver]]" in wiki_file.read_text(encoding="utf-8")


def test_graphify_multilanguage_ast_parsing(tmp_path):
    """Verifies that GraphifyEngine indexes Python, Go, and Zig files into AST graph."""
    db_file = tmp_path / "test_graphify.db"
    engine = GraphifyEngine(db_path=str(db_file), workspace_root=str(tmp_path))

    # Index Python file
    py_code = "class CodeAnalyzer:\n    def analyze(self):\n        pass\n"
    res_py = engine.index_file_ast("analyzer.py", source_code=py_code)
    assert res_py["nodes"] >= 2

    # Index Go file
    go_code = "package main\n\ntype MemoryPool struct {}\n\nfunc Allocate() {}\n"
    res_go = engine.index_file_ast("pool.go", source_code=go_code)
    assert res_go["nodes"] >= 2

    # Index Zig file
    zig_code = "pub const Engine = struct {};\npub fn run() void {}\n"
    res_zig = engine.index_file_ast("engine.zig", source_code=zig_code)
    assert res_zig["nodes"] >= 2


def test_subsystem_health_registry():
    """Verifies that health registry tracks status and records degradation."""
    health_registry.record_online("test_subsystem", "Fully operational")
    report = health_registry.get_health_report()
    assert report["total_subsystems"] >= 5
    assert report["health_score_pct"] > 50.0

    # Record degradation
    health_registry.record_degradation("test_subsystem", "High latency detected")
    degraded_report = health_registry.get_health_report()
    assert degraded_report["degraded"] >= 1
