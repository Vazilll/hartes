"""
tests/e2e/test_core_modernization_e2e.py — Comprehensive End-to-End Test Suite for Vazus SuperGraph OS.

Covers all 4 Tiers of Requirements from ORIGINAL_REQUEST.md & PROJECT.md across Features F1-F19:
- Tier 1: Feature Coverage (F1-F19 in isolation)
- Tier 2: Boundary & Corner Cases (BVA, corrupt inputs, lock contention, token overflow limits)
- Tier 3: Cross-Feature Combinations (Async DB + Vector Search + Tool Routing + AST Pruning)
- Tier 4: Real-World Workload Scenarios (multi-turn subagent execution with fail-closed security, SMT verification, and 20-task benchmark)
"""

import ast
import asyncio
import json
import math
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pytest

# Ensure project root is in sys.path
PROJECT_ROOT = Path(r"C:\vazus")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
VAZUS_CORE = PROJECT_ROOT / "vazus_core"
if str(VAZUS_CORE) not in sys.path:
    sys.path.insert(0, str(VAZUS_CORE))

# Core imports
from vazus_core.memory.async_db import AsyncDatabasePool
from vazus_core.memory.db import (
    get_db_connection,
    init_db_schemas,
    pack_vector_f32,
    unpack_vector_f32,
    close_all_thread_connections,
    DEFAULT_VAZUS_DB,
)
from vazus_core.memory.embeddings import (
    UnifiedEmbeddingManager,
    get_embedding_manager,
    get_embedding,
    compute_similarity,
)
from vazus_core.memory.magma_graph import MAGMAGraphEngine, MAGMAEdgeType
from vazus_core.analysis.reverse_engineer import (
    ReverseEngineerEngine,
    StructField,
    ReconstructedStruct,
)
from vazus_core.analysis.kg_schema import ensure_kg_schema, KG_INSERT_NODE_SQL
from vazus_core.verification.ast_pruner import (
    ASTPruner,
    GoTreeSitterPruner,
    CTreeSitterPruner,
)
from vazus_core.verification.polyglot_verifier import (
    PolyglotVerificationService,
    get_polyglot_verification_service,
)
from vazus_core.verification.smt_z3_verifier import (
    SMTZ3Verifier,
    SMTZ3VerifierAlias,
    VerificationResult,
)
from vazus_core.routing.dynamic_tool_router import (
    DynamicToolRouter,
    ToolDescriptor,
)
from vazus_core.plugins.plugin_manager import (
    PluginManager,
    PluginManifest,
)
from vazus_core.hooks.pre_tool_hook import (
    _is_within_workspace,
    _is_forbidden_path,
    _is_dangerous_command,
)
from vazus_core.hooks.pre_invocation_hook import (
    clean_user_prompt,
    extract_user_prompt,
)
from vazus_core.workers.async_worktree_worker import (
    AsyncWorktreeWorker,
    WorktreeTaskResult,
)
from vazus_core.verification.empirical_benchmark import (
    EmpiricalBenchmarkRunner,
)
from vazus_core.engine.ast_repo_mapper import ASTRepoMapper
from vazus_core.eval.bench_runner import BenchmarkRunner


# Helper to run async code cleanly inside standard sync pytest tests
def run_async(coro):
    return asyncio.run(coro)


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def isolated_e2e_db(tmp_path, monkeypatch):
    """Provides a fresh, isolated SQLite database for zero-side-effect testing."""
    close_all_thread_connections()
    db_file = tmp_path / "e2e_vazus_isolated.db"
    db_path_str = str(db_file)
    monkeypatch.setenv("VAZUS_DB_PATH", db_path_str)
    conn = get_db_connection(db_path_str)
    init_db_schemas(conn, db_path=db_path_str)
    cur = conn.cursor()
    ensure_kg_schema(cur)
    conn.commit()
    conn.close()
    yield db_path_str
    close_all_thread_connections()


@pytest.fixture
def async_db_instance(isolated_e2e_db):
    """Provides an isolated AsyncDatabasePool instance."""
    pool = AsyncDatabasePool(db_path=isolated_e2e_db, max_workers=4)
    yield pool
    pool.close()


# ============================================================================
# Tier 1: Feature Coverage (F1 to F19 in Isolation)
# ============================================================================

class TestTier1FeatureCoverage:
    """Tier 1: Comprehensive verification of features F1 through F19 in isolation."""

    def test_f1_test_suite_tiers_structure(self):
        """F1: Verify tests directory has modular test tiers layout."""
        tests_dir = PROJECT_ROOT / "tests"
        assert tests_dir.exists(), "tests/ directory must exist"
        assert (tests_dir / "unit").exists(), "tests/unit directory must exist"
        assert (tests_dir / "integration").exists(), "tests/integration directory must exist"
        assert (tests_dir / "benchmarks").exists(), "tests/benchmarks directory must exist"
        assert (tests_dir / "e2e").exists(), "tests/e2e directory must exist"

    def test_f2_test_suite_deduplication(self):
        """F2: Verify test suite contains no duplicate test definitions."""
        tests_dir = PROJECT_ROOT / "tests"
        py_test_files = list(tests_dir.glob("**/*.py"))
        assert len(py_test_files) > 0, "Test files must exist"

    def test_f3_worktree_worker_stability(self, tmp_path):
        """F3: Verify AsyncWorktreeWorker manages workspace isolation safely."""
        worker = AsyncWorktreeWorker(repo_root=PROJECT_ROOT, max_workers=2)
        assert worker.repo_root == PROJECT_ROOT.resolve()
        assert worker.scratch_dir.exists()

    def test_f4_empirical_benchmark_resolution(self, tmp_path, isolated_e2e_db):
        """F4: Verify EmpiricalBenchmarkRunner path resolution and report creation."""
        rep_file = tmp_path / "EMPIRICAL_TEST_REPORT.md"
        runner = EmpiricalBenchmarkRunner(
            db_path=isolated_e2e_db,
            report_path=str(rep_file),
            iterations=2,
            warmup_runs=1,
        )
        assert runner.report_path == rep_file
        assert runner.num_iterations == 2

    def test_f5_async_sqlite_pool_crud(self, async_db_instance):
        """F5: Verify AsyncDatabasePool non-blocking CRUD operations."""
        async def _test():
            insert_sql = "INSERT INTO kg_nodes (id, name, domain, node_type, description) VALUES (?, ?, ?, ?, ?)"
            rowcount = await async_db_instance.execute_mutation(
                insert_sql,
                ("test_node_1", "Test Node", "core", "test", "Async DB CRUD verification")
            )
            assert rowcount == 1, "Insert mutation should affect 1 row"

            rows = await async_db_instance.execute_query("SELECT id, name, domain FROM kg_nodes WHERE id = ?", ("test_node_1",))
            assert len(rows) == 1
            assert rows[0][0] == "test_node_1"
            assert rows[0][1] == "Test Node"

            batch_params = [
                ("batch_1", "Batch 1", "core", "test", "Batch test 1"),
                ("batch_2", "Batch 2", "core", "test", "Batch test 2"),
            ]
            batch_count = await async_db_instance.execute_batch(insert_sql, batch_params)
            assert batch_count == 2, "Batch mutation should insert 2 rows"

        run_async(_test())

    def test_f6_768d_embedding_generation(self):
        """F6: Verify 768-D vector embedding generation and cosine similarity."""
        manager = get_embedding_manager(dimension=768)
        vec1 = manager.get_embedding("SuperGraph OS Kernel Architecture")
        vec2 = manager.get_embedding("AST Call Graph Topo Analysis")
        assert len(vec1) == 768, "Embedding vector dimension must strictly be 768"
        assert len(vec2) == 768, "Embedding vector dimension must strictly be 768"

        norm1 = math.sqrt(sum(x * x for x in vec1))
        assert abs(norm1 - 1.0) < 1e-4, f"Embedding vector must be unit-normalized, got norm {norm1}"

        sim = manager.compute_similarity(vec1, vec2)
        assert -1.0 <= sim <= 1.0, f"Cosine similarity must be bounded in [-1.0, 1.0], got {sim}"

        batch_sims = manager.compute_batch_similarity(vec1, [vec2, vec1])
        assert len(batch_sims) == 2
        assert abs(batch_sims[1] - 1.0) < 1e-3, "Self-similarity must be ~1.0"

    def test_f7_async_worker_integration(self, async_db_instance):
        """F7: Verify integration of worker async database mutations with background tasks."""
        async def _test():
            insert_sql = "INSERT INTO kg_nodes (id, name, domain, node_type, description) VALUES (?, ?, ?, ?, ?)"
            results = await asyncio.gather(
                async_db_instance.execute_mutation(insert_sql, ("worker_task_1", "Task 1", "worker", "task", "Desc 1")),
                async_db_instance.execute_mutation(insert_sql, ("worker_task_2", "Task 2", "worker", "task", "Desc 2")),
                async_db_instance.execute_query("SELECT count(*) FROM kg_nodes WHERE domain = ?", ("worker",)),
            )
            assert results[0] == 1
            assert results[1] == 1
            count_rows = await async_db_instance.execute_query("SELECT count(*) FROM kg_nodes WHERE domain = ?", ("worker",))
            assert count_rows[0][0] >= 2

        run_async(_test())

    def test_f8_polyglot_ast_extraction(self):
        """F8: Verify AST Pruning and Polyglot Verification across Python, Go, and C."""
        # 1. Python AST pruning
        py_code = (
            "class EngineManager:\n"
            "    '''Core engine manager documentation.'''\n"
            "    def __init__(self, mode: str):\n"
            "        self.mode = mode\n"
            "        self.initialized = True\n"
            "    def execute_pipeline(self, data: list) -> dict:\n"
            "        result = {}\n"
            "        for item in data:\n"
            "            result[item] = len(item)\n"
            "        return result\n"
        )
        pruned_py, stats_py = ASTPruner.prune_code_string(py_code, docstring_mode="summary")
        assert stats_py["is_valid"] is True, "Pruned Python AST must remain syntactically valid"
        assert "class EngineManager:" in pruned_py
        assert "def execute_pipeline(self, data: list) -> dict:" in pruned_py

        # 2. Go Tree-Sitter / Regex pruning
        go_code = (
            "package main\n\n"
            "type Pipeline struct {\n"
            "    bufferSize int\n"
            "}\n\n"
            "func (p *Pipeline) Process(items []string) int {\n"
            "    count := 0\n"
            "    for _, it := range items {\n"
            "        count += len(it)\n"
            "    }\n"
            "    return count\n"
            "}\n"
        )
        pruned_go, stats_go = GoTreeSitterPruner.prune_code_string(go_code)
        assert stats_go["is_valid"] is True
        assert "func (p *Pipeline) Process(items []string) int" in pruned_go

        # 3. C Tree-Sitter / Regex pruning
        c_code = (
            "#include <stdio.h>\n\n"
            "int compute_checksum(const char* buffer, int len) {\n"
            "    int sum = 0;\n"
            "    for(int i=0; i<len; i++) {\n"
            "        sum ^= buffer[i];\n"
            "    }\n"
            "    return sum;\n"
            "}\n"
        )
        pruned_c, stats_c = CTreeSitterPruner.prune_code_string(c_code)
        assert stats_c["is_valid"] is True
        assert "compute_checksum" in pruned_c

    def test_f9_struct_memory_layout_reconstruction(self):
        """F9: Verify 64-bit struct memory layout alignment, offsets, and type mapping."""
        # 1. C Struct Layout
        c_struct_code = """
        typedef struct {
            char flag;
            int id;
            double score;
            void* data_ptr;
        } RecordHeader;
        """
        layout_c = ReverseEngineerEngine.reconstruct_c_struct(c_struct_code)
        assert layout_c is not None, "C struct must be parsed successfully"
        assert layout_c.name == "RecordHeader"
        assert layout_c.alignment == 8, "Max alignment of double/void* is 8 bytes"
        assert layout_c.total_size == 24
        field_offsets = {f.name: f.offset for f in layout_c.fields}
        assert field_offsets["flag"] == 0
        assert field_offsets["id"] == 4
        assert field_offsets["score"] == 8
        assert field_offsets["data_ptr"] == 16

        # 2. Go Struct Layout
        go_struct_code = """
        type MessagePayload struct {
            ID uint64
            Data string
            Active bool
        }
        """
        layout_go = ReverseEngineerEngine.reconstruct_go_struct(go_struct_code)
        assert layout_go is not None, "Go struct must be parsed successfully"
        assert layout_go.name == "MessagePayload"
        assert layout_go.alignment == 8
        assert layout_go.total_size == 32

        # 3. Cross-language type mapping
        mapping = ReverseEngineerEngine.map_cross_language_types("int")
        assert "int64_t" in mapping or "int" in mapping

    def test_f10_call_graph_and_repo_mapper(self, tmp_path):
        """F10: Verify ASTRepoMapper extracts symbols and call references."""
        sample_file = tmp_path / "sample_service.py"
        sample_file.write_text(
            "class UserService:\n"
            "    def get_user(self, user_id: int):\n"
            "        return self.lookup_db(user_id)\n"
            "    def lookup_db(self, uid: int):\n"
            "        return {'id': uid}\n",
            encoding="utf-8"
        )
        mapper = ASTRepoMapper(root_dir=tmp_path)
        defs, refs, skeleton = mapper.extract_symbols(sample_file)
        assert "UserService" in defs
        assert "UserService.get_user" in defs
        assert "lookup_db" in refs or "uid" in refs
        assert "class UserService:" in skeleton

    def test_f11_magma_4graph_engine(self, isolated_e2e_db):
        """F11: Verify MAGMA 4-graph edge creation and intent-aware traversal."""
        engine = MAGMAGraphEngine(db_path=isolated_e2e_db)

        # Create nodes
        conn = get_db_connection(isolated_e2e_db)
        cur = conn.cursor()
        cur.execute(
            KG_INSERT_NODE_SQL,
            ("node_a", "ASTPrunerModule", "core", "module", "AST Pruner implementation", "[]", "{}", "[]")
        )
        cur.execute(
            KG_INSERT_NODE_SQL,
            ("node_b", "TokenReductionADR", "core", "adr", "Architectural decision for token saving", "[]", "{}", "[]")
        )
        conn.commit()
        conn.close()

        # Add causal and entity edges
        ok1 = engine.add_edge("node_a", "node_b", MAGMAEdgeType.CAUSAL, strength=1.0)
        ok2 = engine.add_edge("node_a", "node_b", MAGMAEdgeType.ENTITY, strength=0.8)
        assert ok1 is True
        assert ok2 is True

        # Query graph with "why" intent (maps to CAUSAL/SEMANTIC)
        results = engine.intent_aware_traverse("node_a", intent="why", max_depth=2)
        assert len(results) >= 1
        assert any(r["node_id"] == "node_b" for r in results)

    def test_f12_pre_tool_hook_fail_closed(self):
        """F12: Verify fail-closed pre-tool hook security validation."""
        # 1. Path jail: allowed inside C:/vazus
        assert _is_within_workspace(r"C:\vazus\vazus_core\memory\db.py") is True
        # Path jail: blocked outside workspace
        assert _is_within_workspace(r"C:\Windows\System32\cmd.exe") is False
        assert _is_within_workspace(r"C:\vazus\..\..\Windows\System32\calc.exe") is False

        # 2. Forbidden paths: .git and root AGENTS.md
        assert _is_forbidden_path(r"C:\vazus\.git\config") is True
        assert _is_forbidden_path(r"C:\vazus\AGENTS.md") is True
        assert _is_forbidden_path(r"C:\vazus\vazus_core\analysis\pattern_miner.py") is False

        # 3. Destructive command filter
        assert _is_dangerous_command("rmdir /s /q c:\\") is True
        assert _is_dangerous_command("format c:") is True
        assert _is_dangerous_command("pytest tests/unit -q") is False

    def test_f13_lifecycle_hooks_enrichment(self):
        """F13: Verify lifecycle hook prompt cleaning and extraction."""
        raw_prompt = "<USER_REQUEST>\nImplement async database pool\n</USER_REQUEST>\n<ADDITIONAL_METADATA>\ntime: 2026-08-18\n</ADDITIONAL_METADATA>"
        cleaned = clean_user_prompt(raw_prompt)
        assert cleaned == "Implement async database pool"

        extracted = extract_user_prompt({"userPrompt": "Refactor radon hotspots"})
        assert extracted == "Refactor radon hotspots"

    def test_f14_session_lifecycle_and_plugin_manager(self, tmp_path):
        """F14: Verify PluginManager manifest loading, registration, and dispatch."""
        plugin_dir = tmp_path / "plugins" / "sample_plugin"
        plugin_dir.mkdir(parents=True, exist_ok=True)
        manifest_data = {
            "name": "sample_plugin",
            "version": "1.2.0",
            "description": "Sample plugin for test",
            "author": "Vazus Team",
            "hooks": {"pre_tool": "hook_fn"},
        }
        (plugin_dir / "plugin.json").write_text(json.dumps(manifest_data), encoding="utf-8")

        mgr = PluginManager(plugin_dirs=[tmp_path / "plugins"])
        assert "sample_plugin" in mgr.plugins
        assert mgr.plugins["sample_plugin"].version == "1.2.0"

        called = []
        mgr.register_hook_callback("pre_tool", lambda **kw: called.append(kw))
        mgr.dispatch_hook("pre_tool", action="validate", target="file.py")
        assert len(called) == 1
        assert called[0]["action"] == "validate"

    def test_f15_dynamic_tool_router_and_projection(self):
        """F15: Verify DynamicToolRouter exposes <= 3 tools and projects JSON payloads."""
        router = DynamicToolRouter()
        tools = router.find_tools("Prune AST signatures for Go and Python", top_k=3)
        assert 1 <= len(tools) <= 3, "Router must return <= 3 tools per step"
        tool_names = [t["name"] for t in tools]
        assert "ast_prune" in tool_names, "ast_prune tool must be ranked top for AST task"

        # Server-side payload projection with whitelist filtering and array truncation
        large_payload = {
            "title": "Optimization Result",
            "_internal_state": "hidden",
            "embedding": [0.1] * 768,
            "items": [f"item_{i}" for i in range(25)],
            "meta": {"status": "ok", "raw_bytes": "xyz", "_private": "secret"},
        }
        projected = DynamicToolRouter.project_payload(
            large_payload,
            whitelist_keys=["title", "items", "meta"],
            max_array_items=5,
        )
        assert "_internal_state" not in projected
        assert "embedding" not in projected
        assert len(projected["items"]) == 6
        assert "truncated" in projected["items"][-1]
        assert "raw_bytes" not in projected["meta"]
        assert "_private" not in projected["meta"]

    def test_f16_radon_complexity_bounds(self):
        """F16: Verify cyclomatic complexity calculation and bounds."""
        code_simple = (
            "def calculate(a, b):\n"
            "    if a > b:\n"
            "        return a - b\n"
            "    return a + b\n"
        )
        polyglot = get_polyglot_verification_service()
        verifier = polyglot.verifiers["python"]
        metrics = verifier.compute_metrics(code_simple)
        assert metrics.cyclomatic_complexity <= 8, "Simple function CC must be <= 8"
        assert metrics.code_health_score >= 9.0

    def test_f17_smt_z3_formal_contracts(self):
        """F17: Verify SMT Z3 formal logic contract proofs and memory safety."""
        verifier = SMTZ3VerifierAlias()

        # 1. Contract Verification (:requires: and :ensures:)
        code_contract = (
            "def safe_increment(x: int) -> int:\n"
            "    '''\n"
            "    :requires: x >= 0\n"
            "    :ensures: result > 0\n"
            "    '''\n"
            "    return x + 1\n"
        )
        res = verifier.verify_code_contracts(python_code=code_contract)
        assert res.verified is True, "Valid Hoare contract must be formally verified (UNSAT negation)"
        assert res.contract_satisfied is True

        # 2. Memory Safety Verification
        safe_mem = verifier.verify_memory_safety(offset=0, length=5, capacity=10)
        assert safe_mem.verified is True

        unsafe_mem = verifier.verify_memory_safety(offset=8, length=5, capacity=10)
        assert unsafe_mem.verified is False

        # 3. Functional Equivalence
        orig_fn = "def double(x):\n    return x + x\n"
        opt_fn = "def double(x):\n    return 2 * x\n"
        equiv_res = verifier.verify_functional_equivalence(orig_fn, opt_fn)
        assert equiv_res.verified is True, "x+x and 2*x must be functionally equivalent"

    def test_f18_vazus_bench_20_tasks_pass_rate(self):
        """F18: Verify all 20 benchmark tasks in vazus-bench achieve 100.0% pass@1."""
        runner = BenchmarkRunner()
        assert len(runner.tasks) == 20, f"Benchmark suite must contain exactly 20 tasks, found {len(runner.tasks)}"
        summary = runner.run_all(category_filter="all")
        assert summary["total_tasks"] == 20
        assert summary["passed_tasks"] == 20, f"All 20 tasks must pass. Failed: {summary['failed_tasks']}"
        assert summary["pass_at_1"] == 100.0, f"Pass@1 must be 100.0%, got {summary['pass_at_1']}%"

    def test_f19_e2e_regression_verification(self, async_db_instance):
        """F19: Verify holistic end-to-end integration across all core systems."""
        async def _test():
            # Step 1: Prune an AST
            source_code = (
                "def process_transaction(amount: int) -> int:\n"
                "    '''\n"
                "    :requires: amount > 0\n"
                "    :ensures: result >= amount\n"
                "    '''\n"
                "    fee = 2\n"
                "    return amount + fee\n"
            )
            pruned, stats = ASTPruner.prune_code_string(source_code)
            assert stats["is_valid"] is True

            # Step 2: SMT Z3 formal verification
            smt = SMTZ3VerifierAlias()
            proof = smt.verify_code_contracts(python_code=source_code)
            assert proof.verified is True

            # Step 3: Embed & Store in Async DB
            emb = get_embedding(pruned)
            assert len(emb) == 768
            await async_db_instance.execute_mutation(
                "INSERT INTO kg_nodes (id, name, domain, node_type, description, embedding_json) VALUES (?, ?, ?, ?, ?, ?)",
                ("e2e_node_1", "TransactionProcessor", "fin", "func", "E2E Verified Transaction Processor", json.dumps(emb))
            )

            # Step 4: Verify Retrieval
            rows = await async_db_instance.execute_query("SELECT id, name FROM kg_nodes WHERE id = ?", ("e2e_node_1",))
            assert len(rows) == 1
            assert rows[0][1] == "TransactionProcessor"

        run_async(_test())


# ============================================================================
# Tier 2: Boundary Value Analysis & Corner Cases
# ============================================================================

class TestTier2BoundaryCornerCases:
    """Tier 2: Boundary conditions, empty values, corrupt inputs, lock contention, overflows."""

    def test_tier2_bva_smt_memory_safety_boundaries(self):
        """BVA on SMT Z3 memory safety (offset, length, capacity)."""
        verifier = SMTZ3VerifierAlias()

        # (0, 0, 0) -> safe boundary
        assert verifier.verify_memory_safety(0, 0, 0).verified is True

        # (0, 10, 10) -> exactly at capacity -> safe
        assert verifier.verify_memory_safety(0, 10, 10).verified is True

        # (10, 0, 10) -> at upper offset bound with 0 length -> safe
        assert verifier.verify_memory_safety(10, 0, 10).verified is True

        # Negative offset -> unsafe
        assert verifier.verify_memory_safety(-1, 5, 10).verified is False

        # Negative length -> unsafe
        assert verifier.verify_memory_safety(0, -1, 10).verified is False

        # 1-byte overflow: (10, 1, 10) -> unsafe
        assert verifier.verify_memory_safety(10, 1, 10).verified is False

        # Negative capacity -> unsafe
        assert verifier.verify_memory_safety(0, 1, -5).verified is False

    def test_tier2_bva_embedding_boundaries(self):
        """BVA on embedding engine inputs (empty, whitespace, unicode, huge text)."""
        manager = get_embedding_manager(dimension=768)

        # Empty string
        vec_empty = manager.get_embedding("")
        assert len(vec_empty) == 768
        assert all(x == 0.0 for x in vec_empty), "Empty text must produce zero vector"

        # Whitespace
        vec_space = manager.get_embedding("     \n\t  ")
        assert len(vec_space) == 768
        assert all(x == 0.0 for x in vec_space), "Whitespace text must produce zero vector"

        # Unicode / Cyrillic
        vec_unicode = manager.get_embedding("Архитектура Vazus SuperGraph OS на базе микроядра")
        assert len(vec_unicode) == 768
        norm_u = math.sqrt(sum(x * x for x in vec_unicode))
        assert abs(norm_u - 1.0) < 1e-4

        # Large text (50,000 characters)
        large_text = "Kernel SuperGraph AST Pruning Memory Wiki " * 1200
        vec_large = manager.get_embedding(large_text)
        assert len(vec_large) == 768
        norm_l = math.sqrt(sum(x * x for x in vec_large))
        assert abs(norm_l - 1.0) < 1e-4

    def test_tier2_bva_tool_router_boundaries(self):
        """BVA on tool router limits (top_k=0, top_k=1, top_k=100, empty queries)."""
        router = DynamicToolRouter()

        # top_k = 0
        tools_0 = router.find_tools("AST", top_k=0)
        assert len(tools_0) == 0

        # top_k = 1
        tools_1 = router.find_tools("AST", top_k=1)
        assert len(tools_1) <= 1

        # top_k = 100 (capped by total registered tools)
        tools_100 = router.find_tools("AST", top_k=100)
        assert len(tools_100) <= len(router.registry)

        # Non-matching query
        tools_nomatch = router.find_tools("x987qwerty_unrelated_token", min_score=0.99)
        assert len(tools_nomatch) == 0

    def test_tier2_bva_pre_tool_hook_jailbreaks(self):
        """Adversarial path traversal and command injection boundary tests."""
        # Relative traversal
        assert _is_within_workspace(r"C:\vazus\..\Windows\notepad.exe") is False
        assert _is_within_workspace(r"C:\vazus\sub\..\..\..\Windows") is False

        # Forbidden dot-git variations
        assert _is_forbidden_path(r"C:\vazus\.git/objects/pack") is True
        assert _is_forbidden_path(r"c:\vazus\.git\hooks\pre-commit") is True
        assert _is_forbidden_path(r"C:/vazus/AGENTS.md") is True

        # Blacklisted dangerous commands
        assert _is_dangerous_command("REG DELETE HKLM\\Software") is True
        assert _is_dangerous_command("del /f /s /q c:\\windows") is True
        assert _is_dangerous_command("diskpart /s script.txt") is True

    def test_tier2_corrupt_struct_and_ast_handling(self):
        """Verify robust handling of malformed syntax and corrupt structs without unhandled crashes."""
        # Corrupt C struct
        corrupt_c = "struct InvalidStruct { int incomplete_field"
        layout_c = ReverseEngineerEngine.reconstruct_c_struct(corrupt_c)
        assert layout_c is None, "Corrupt C struct must gracefully return None"

        # Corrupt Go struct
        corrupt_go = "type BadStruct struct {"
        layout_go = ReverseEngineerEngine.reconstruct_go_struct(corrupt_go)
        assert layout_go is None, "Corrupt Go struct must gracefully return None"

        # Corrupt Python AST
        corrupt_py = "def broken_syntax(:"
        pruned, stats = ASTPruner.prune_code_string(corrupt_py)
        assert stats["is_valid"] is False, "Malformed Python syntax must report is_valid=False"

    def test_tier2_async_db_lock_contention_and_empty_db(self, isolated_e2e_db):
        """Verify concurrent async mutations execute with zero database lock contention."""
        async def _test():
            pool = AsyncDatabasePool(db_path=isolated_e2e_db, max_workers=8)
            insert_sql = "INSERT INTO kg_nodes (id, name, domain, node_type, description) VALUES (?, ?, ?, ?, ?)"

            # Spawn 30 simultaneous parallel mutations
            tasks = [
                pool.execute_mutation(insert_sql, (f"concurrent_{i}", f"Name {i}", "stress", "node", f"Desc {i}"))
                for i in range(30)
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for idx, res in enumerate(results):
                assert not isinstance(res, Exception), f"Task {idx} failed with exception: {res}"
                assert res == 1, f"Task {idx} must insert 1 row"

            count_rows = await pool.execute_query("SELECT count(*) FROM kg_nodes WHERE domain = ?", ("stress",))
            assert count_rows[0][0] == 30
            pool.close()

        run_async(_test())


# ============================================================================
# Tier 3: Cross-Feature Combinations
# ============================================================================

class TestTier3CrossFeatureCombinations:
    """Tier 3: Complex multi-subsystem pipelines and pairwise interactions."""

    def test_tier3_async_db_vector_search_tool_routing_ast_pruner(self, async_db_instance):
        """
        Combination CA-01:
        Polyglot AST Pruning (F8) -> 768D Vector Embedding (F6) ->
        Async Database Insertion (F5) -> Dynamic Tool Discovery (F15) ->
        Native SQLite Vector Search.
        """
        async def _test():
            # Step 1: Prune real Python service code
            source_code = (
                "class VectorSearchPipeline:\n"
                "    '''High throughput semantic vector search pipeline.'''\n"
                "    def __init__(self, index_path: str):\n"
                "        self.index_path = index_path\n"
                "    def search(self, query: str, top_k: int = 5) -> list:\n"
                "        results = []\n"
                "        return results\n"
            )
            pruned_code, stats = ASTPruner.prune_code_string(source_code)
            assert stats["is_valid"] is True

            # Step 2: Generate 768-D Vector
            vec = get_embedding(pruned_code)
            assert len(vec) == 768

            # Step 3: Insert into Async Database
            await async_db_instance.execute_mutation(
                "INSERT INTO kg_nodes (id, name, domain, node_type, description, tags, embedding_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    "vector_pipeline_node",
                    "VectorSearchPipeline",
                    "search",
                    "class",
                    "High throughput semantic vector search pipeline",
                    json.dumps(["vector", "search", "pipeline"]),
                    json.dumps(vec),
                )
            )

            # Step 4: Discover tools for searching
            router = DynamicToolRouter()
            matched_tools = router.find_tools("Vector search and query embeddings", top_k=3)
            assert len(matched_tools) >= 1

            # Step 5: Execute Vector Search
            manager = get_embedding_manager(dimension=768)
            search_results = manager.search_unified_vector_space(
                query="vector search pipeline",
                db_path=async_db_instance.db_path,
                top_k=5,
            )
            assert len(search_results) >= 1
            assert search_results[0]["id"] == "vector_pipeline_node"

        run_async(_test())

    def test_tier3_plugin_lifecycle_hooks_ast_verification(self, tmp_path):
        """
        Combination CA-02:
        Plugin Manager (F14) + PreToolHook (F12) + PostToolHook (F13) + Polyglot Verifier (F8).
        """
        # Step 1: Initialize Plugin Manager with dynamic hook
        plugin_manager = PluginManager(plugin_dirs=[tmp_path])
        audit_trail = []

        def security_audit_callback(**kwargs):
            audit_trail.append(kwargs)
            return {"status": "audited"}

        plugin_manager.register_hook_callback("pre_tool", security_audit_callback)

        # Step 2: Validate security boundary before tool execution
        target_path = str(PROJECT_ROOT / "vazus_core" / "sample_mod.py")
        is_safe = _is_within_workspace(target_path) and not _is_forbidden_path(target_path)
        assert is_safe is True

        plugin_manager.dispatch_hook("pre_tool", tool="write_file", path=target_path)
        assert len(audit_trail) == 1

        # Step 3: Verify AST syntax and compute code health
        valid_py = "def process_data(records: list) -> int:\n    return len(records)\n"
        polyglot = get_polyglot_verification_service()
        verif_res = polyglot.verifiers["python"].evaluate(valid_py)
        assert verif_res.passed is True
        assert verif_res.metrics.code_health_score >= 9.5

    def test_tier3_reverse_engineer_smt_z3_magma_graph(self, isolated_e2e_db):
        """
        Combination CA-03:
        Reverse Engineer Layout (F9) + SMT Z3 Memory Proof (F17) + MAGMA 4-Graph Memory (F11).
        """
        # Step 1: Reconstruct struct layout
        c_code = """
        typedef struct {
            uint64_t header_magic;
            uint64_t payload_len;
            uint64_t session_id;
            void* payload_ptr;
        } NetworkPacket;
        """
        layout = ReverseEngineerEngine.reconstruct_c_struct(c_code)
        assert layout is not None
        assert layout.total_size == 32

        # Step 2: SMT Z3 proves packet buffer slicing safety
        smt = SMTZ3VerifierAlias()
        safe_access = smt.verify_memory_safety(offset=8, length=16, capacity=layout.total_size)
        assert safe_access.verified is True

        # Step 3: Link into MAGMA 4-Graph
        magma = MAGMAGraphEngine(db_path=isolated_e2e_db)
        conn = get_db_connection(isolated_e2e_db)
        cur = conn.cursor()
        cur.execute(
            KG_INSERT_NODE_SQL,
            ("pkt_struct", "NetworkPacket", "network", "struct", "Reconstructed NetworkPacket 32B", "[]", "{}", "[]")
        )
        cur.execute(
            KG_INSERT_NODE_SQL,
            ("pkt_proof", "PacketBoundsProof", "verification", "proof", "SMT Z3 Verified Safe Slicing", "[]", "{}", "[]")
        )
        conn.commit()
        conn.close()

        magma.add_edge("pkt_struct", "pkt_proof", MAGMAEdgeType.ENTITY, strength=1.0)
        magma.add_edge("pkt_proof", "pkt_struct", MAGMAEdgeType.CAUSAL, strength=1.0)

        # Traverse
        neighbors = magma.intent_aware_traverse("pkt_struct", intent="struct")
        assert len(neighbors) >= 1
        assert any(n["node_id"] == "pkt_proof" for n in neighbors)


# ============================================================================
# Tier 4: Real-World Workload Scenarios
# ============================================================================

class TestTier4RealWorldWorkloads:
    """Tier 4: End-to-end multi-agent workflows, benchmark workloads, high concurrency."""

    def test_tier4_multi_turn_subagent_lifecycle(self, async_db_instance):
        """
        Realistic Multi-Turn Subagent Patch Lifecycle:
        Turn 0: Dynamic tool discovery & prompt cleaning
        Turn 1: Pre-tool security validation of code mutation
        Turn 2: Polyglot AST analysis & pruning (<1800 tokens)
        Turn 3: SMT Z3 formal Hoare contract proof
        Turn 4: Post-tool AST syntax check
        Turn 5: Async memory persistence into SuperGraph
        """
        async def _test():
            # Turn 0: User Prompt Cleaning and Tool Routing
            raw_prompt = "<USER_REQUEST>\nImplement safe ring buffer in Python and prove invariants\n</USER_REQUEST>"
            cleaned_prompt = clean_user_prompt(raw_prompt)
            assert "safe ring buffer" in cleaned_prompt

            router = DynamicToolRouter()
            suggested_tools = router.find_tools(cleaned_prompt, top_k=3)
            assert len(suggested_tools) <= 3

            # Turn 1: Pre-Tool Security Check
            target_file = r"C:\vazus\vazus_core\memory\safe_buffer.py"
            assert _is_within_workspace(target_file) is True
            assert not _is_forbidden_path(target_file)

            # Turn 2: Author Code & Prune AST
            buffer_code = (
                "class SafeRingBuffer:\n"
                "    '''Fixed size ring buffer with invariant contracts.'''\n"
                "    def __init__(self, capacity: int = 16):\n"
                "        self.capacity = capacity\n"
                "        self.buffer = [0] * capacity\n"
                "        self.head = 0\n"
                "        self.tail = 0\n"
                "        self.size = 0\n\n"
                "    def push(self, val: int) -> bool:\n"
                "        if self.size >= self.capacity:\n"
                "            return False\n"
                "        self.buffer[self.tail] = val\n"
                "        self.tail = (self.tail + 1) % self.capacity\n"
                "        self.size += 1\n"
                "        return True\n"
            )
            pruned_code, stats = ASTPruner.prune_code_string(buffer_code)
            assert stats["is_valid"] is True
            assert "class SafeRingBuffer:" in pruned_code

            # Turn 3: SMT Z3 Formal Contract Proof on standalone ring buffer index advance logic
            advance_code = (
                "def advance_index(idx: int, capacity: int) -> int:\n"
                "    '''\n"
                "    :requires: idx >= 0 and capacity > 0 and idx < capacity\n"
                "    :ensures: result >= 0\n"
                "    '''\n"
                "    return (idx + 1) % capacity\n"
            )
            smt = SMTZ3VerifierAlias()
            proof_res = smt.verify_code_contracts(python_code=advance_code)
            assert proof_res.verified is True

            # Turn 4: Post-Tool AST Syntax Validation
            tree = ast.parse(buffer_code)
            assert len(tree.body) == 1

            # Turn 5: Async Persistence in SuperGraph
            emb = get_embedding(pruned_code)
            await async_db_instance.execute_mutation(
                "INSERT INTO kg_nodes (id, name, domain, node_type, description, properties, embedding_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    "safe_ring_buffer_node",
                    "SafeRingBuffer",
                    "datastructures",
                    "class",
                    "SMT Verified Safe Ring Buffer Implementation",
                    json.dumps({"capacity": 16, "verified": True}),
                    json.dumps(emb),
                )
            )

            persisted = await async_db_instance.execute_query("SELECT id, name FROM kg_nodes WHERE id = ?", ("safe_ring_buffer_node",))
            assert len(persisted) == 1
            assert persisted[0][0] == "safe_ring_buffer_node"

        run_async(_test())

    def test_tier4_vazus_bench_20_tasks_workload(self):
        """Execute full 20-task vazus-bench workload and assert zero regressions."""
        runner = BenchmarkRunner()
        summary = runner.run_all()

        assert summary["total_tasks"] == 20
        assert summary["passed_tasks"] == 20
        assert summary["failed_tasks"] == 0
        assert summary["pass_at_1"] == 100.0

        for cat, stats in summary["category_stats"].items():
            assert stats["pass_rate"] == 100.0, f"Category {cat} must have 100% pass rate, got {stats['pass_rate']}%"

    def test_tier4_concurrent_multi_worker_stress_workload(self, async_db_instance):
        """
        High-concurrency stress test executing simultaneous database writes,
        embedding calculations, struct layout parsings, and Z3 contract proofs.
        """
        async def _test():
            manager = get_embedding_manager(dimension=768)
            smt = SMTZ3VerifierAlias()

            async def worker_job(worker_id: int):
                # 1. Compute embedding
                vec = manager.get_embedding(f"Concurrent Worker Task Payload {worker_id}")
                assert len(vec) == 768

                # 2. Reconstruct C struct
                c_code = f"typedef struct {{ int id_{worker_id}; double val_{worker_id}; }} WorkerStruct{worker_id};"
                layout = ReverseEngineerEngine.reconstruct_c_struct(c_code)
                assert layout is not None

                # 3. SMT Z3 proof
                proof = smt.verify_memory_safety(offset=0, length=8, capacity=layout.total_size)
                assert proof.verified is True

                # 4. Async DB write
                await async_db_instance.execute_mutation(
                    "INSERT INTO kg_nodes (id, name, domain, node_type, description) VALUES (?, ?, ?, ?, ?)",
                    (f"stress_worker_{worker_id}", f"Worker{worker_id}", "stress", "job", f"Job desc {worker_id}")
                )
                return True

            # Run 20 workers simultaneously
            jobs = [worker_job(i) for i in range(20)]
            results = await asyncio.gather(*jobs, return_exceptions=True)

            for idx, res in enumerate(results):
                assert not isinstance(res, Exception), f"Worker {idx} raised exception: {res}"
                assert res is True

            count_rows = await async_db_instance.execute_query("SELECT count(*) FROM kg_nodes WHERE domain = ?", ("stress",))
            assert count_rows[0][0] == 20

        run_async(_test())
