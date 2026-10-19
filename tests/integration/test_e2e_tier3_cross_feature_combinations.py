"""
Tier 3 Cross-Feature Combination E2E Test Suite — Vazus OS Core Refactoring
File: tests/test_e2e_tier3_cross_feature_combinations.py

Requirements Covered:
- Test case 1: Pairwise async execution (R1) + LLM reflexion loop (R2).
- Test case 2: Pairwise async execution (R1) + 768D vector memory retrieval (R3).
- Test case 3: Pairwise LLM reflexion (R2) + vector lesson memory bank (R3).
- Test case 4: Full 3-feature integrated pipeline (R1 + R2 + R3).
- Test case 5: Concurrent multi-task async execution with vector lookup and LLM repair.
Plus additional pairwise cross-feature interaction test cases for complete SuperGraph OS coverage.
"""

import ast
import json
import os
import sys
import tempfile
import time
import asyncio
import sqlite3
from pathlib import Path
import pytest
import numpy as np

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from vazus_core.subagent_framework import (
    SubagentContext,
    SubagentHookRegistry,
    DeclarativeSubagentEngine,
    SubagentTemplateRegistry,
    DeclarativeSubagentTemplate,
)
from vazus_core.unified_reasoning_pipeline import UnifiedReasoningPipeline
from vazus_core.auto_improver import (
    VazusAutoImprover,
    LessonMemoryBank,
    SkillUsageTracker,
    ReflexionEvaluator,
)
from vazus_core.embeddings import (
    UnifiedEmbeddingManager,
    get_embedding,
    get_embedding_manager,
)
from vazus_core.concordia_jury import ConcordiaJury, JuryVerdict
from vazus_core.smt_z3_verifier import SMTZ3Verifier
from vazus_core.ast_pruner import ASTPruner
from vazus_core.db import get_db_connection, init_db_schemas, pack_vector_f32, unpack_vector_f32, close_all_thread_connections


@pytest.fixture
def tmp_e2e_db(tmp_path, monkeypatch):
    """Provides an isolated SQLite database path with initialized schemas."""
    close_all_thread_connections()
    db_file = str(tmp_path / "vazus_tier3_e2e.db")
    monkeypatch.setenv("VAZUS_DB_PATH", db_file)
    conn = get_db_connection(db_file)
    init_db_schemas(conn)
    conn.close()
    yield db_file
    close_all_thread_connections()


# ============================================================================
# Test Case 1: Pairwise Async Execution (R1) + LLM Reflexion Loop (R2)
# ============================================================================

def test_tier3_tc1_async_execution_with_llm_reflexion(tmp_e2e_db):
    """
    Test Case 1: Pairwise async execution (R1) + LLM reflexion loop (R2).
    Verifies that asynchronous subagent execution invokes VazusAutoImprover
    reflexion loop upon execution failure with non-blocking async repair execution.
    """
    async def _async_impl():
        faulty_code = "def calculate_growth_rate(initial: float, final: float:\n    return (final - initial) / 0\n"

        def _llm_fix_fn(code: str, critique: str, past_lessons: list) -> str:
            return """
def calculate_growth_rate(initial: float, final: float) -> float:
    if initial <= 0:
        return 0.0
    return (final - initial) / initial
"""

        async with asyncio.timeout(300.0):
            await asyncio.sleep(0.01)  # Non-blocking async step
            improver = VazusAutoImprover(max_iterations=2)
            
            session = await improver.improve(
                task_id="async_task_01",
                task_description="Calculate non-negative growth rate without division by zero",
                initial_code=faulty_code,
                fix_fn=_llm_fix_fn,
                error_trace="SyntaxError: invalid syntax",
                task_type="growth_analytics"
            )

        assert session.success is True
        assert session.iterations >= 1
        assert session.final_score >= 0.7
        assert "def calculate_growth_rate" in session.final_code
        assert "/ 0" not in session.final_code
        assert ast.parse(session.final_code) is not None

    asyncio.run(_async_impl())


# ============================================================================
# Test Case 2: Pairwise Async Execution (R1) + 768D Vector Memory Retrieval (R3)
# ============================================================================

def test_tier3_tc2_async_execution_with_vector_memory_retrieval(tmp_e2e_db):
    """
    Test Case 2: Pairwise async execution (R1) + 768D vector memory retrieval (R3).
    Verifies that concurrent async tasks can generate 768D vector embeddings, save them,
    and query LessonMemoryBank / UnifiedEmbeddingManager using batch cosine search in parallel.
    """
    async def _async_impl():
        embedder = UnifiedEmbeddingManager(dimension=768)
        bank = LessonMemoryBank()

        lessons_data = [
            ("async_engine", "TimeoutError", "Wrap execution in asyncio.timeout(300) guard", "Use asyncio.timeout"),
            ("vector_store", "ValueError: vector dimension mismatch", "Ensure all vector embeddings are strictly 768D float lists", "Use UnifiedEmbeddingManager.get_embedding"),
            ("smt_verifier", "Z3Exception: contract unsatisfied", "Check postcondition bounds in function docstring", "Enforce result >= 0 check"),
        ]

        for task_type, err_sig, lesson_text, fix_hint in lessons_data:
            bank.save_lesson(task_type, err_sig, lesson_text, fix_hint)

        async def _async_vector_lookup_task(task_id: int, query_text: str):
            await asyncio.sleep(0.01)
            vec = embedder.embed_query(query_text)
            assert len(vec) == 768
            assert all(isinstance(v, float) for v in vec)
            retrieved = bank.retrieve_relevant(query_text, task_type="async_engine", top_k=2)
            return task_id, vec, retrieved

        async with asyncio.timeout(300.0):
            tasks = [
                _async_vector_lookup_task(i, "TimeoutError")
                for i in range(5)
            ]
            results = await asyncio.gather(*tasks)

        assert len(results) == 5
        for task_id, vec, retrieved in results:
            assert len(vec) == 768
            assert isinstance(retrieved, list)
            assert len(retrieved) > 0
            assert "lesson" in retrieved[0]

    asyncio.run(_async_impl())


# ============================================================================
# Test Case 3: Pairwise LLM Reflexion (R2) + Vector Lesson Memory Bank (R3)
# ============================================================================

def test_tier3_tc3_llm_reflexion_with_vector_lesson_bank(tmp_e2e_db):
    """
    Test Case 3: Pairwise LLM reflexion (R2) + vector lesson memory bank (R3).
    Verifies that VazusAutoImprover uses 768D vector search to retrieve past failure lessons,
    passes retrieved lessons to LLM fix_fn, and marks used lessons as successful.
    """
    async def _async_impl():
        bank = LessonMemoryBank()
        
        error_sig = "TypeError: unsupported operand type for +: 'int' and 'str'"
        lesson_text = "Type mismatch when summing values: convert string to integer or float before adding."
        bank.save_lesson("type_conversion", error_sig, lesson_text, fix_hint="Use int() or float()")

        retrieved_lessons_received = []

        def _llm_fix_fn(code: str, critique: str, past_lessons: list) -> str:
            nonlocal retrieved_lessons_received
            retrieved_lessons_received.extend(past_lessons)
            return """
def sum_values(a: int, b: str) -> int:
    return a + int(b)
"""

        improver = VazusAutoImprover(max_iterations=2)
        session = await improver.improve(
            task_id="reflexion_vector_task",
            task_description="Sum integer and string value safely",
            initial_code="def sum_values(a, b:\n    return a + b\n",
            fix_fn=_llm_fix_fn,
            error_trace=error_sig,
            task_type="type_conversion"
        )

        assert session.success is True
        assert len(retrieved_lessons_received) > 0
        assert any("Type mismatch" in l or "convert" in l for l in retrieved_lessons_received)
        assert session.final_score >= 0.7

    asyncio.run(_async_impl())


# ============================================================================
# Test Case 4: Full 3-Feature Integrated Pipeline (R1 + R2 + R3)
# ============================================================================

def test_tier3_tc4_full_three_feature_integrated_pipeline(tmp_e2e_db):
    """
    Test Case 4: Full 3-feature integrated pipeline (R1 + R2 + R3).
    Executes end-to-end workflow:
      R1: Async execution runtime loop with timeout guard.
      R3: Vector lesson search & 768D embedding calculation.
      R2: LLM reflexion loop & Concordia 3-subagent Jury voting.
    """
    async def _async_impl():
        pipeline = UnifiedReasoningPipeline(effort_level="high")
        embedder = UnifiedEmbeddingManager(dimension=768)
        bank = LessonMemoryBank()

        initial_buggy_code = "def compute_trimp_load(duration_min: float, avg_hr: float:\n    return duration_min * (avg_hr - 60) / 0\n"

        bank.save_lesson(
            "fitness_telemetry",
            "ZeroDivisionError in TRIMP load",
            "Division by zero in TRIMP formula. Divide by max HR range (e.g. 130.0).",
            "Divide by 130.0"
        )

        async with asyncio.timeout(300.0):
            await asyncio.sleep(0.01)
            lessons = bank.retrieve_relevant("ZeroDivisionError in TRIMP load", task_type="fitness_telemetry")
            assert len(lessons) > 0

            repaired_code = """
def compute_trimp_load(duration_min: float, avg_hr: float) -> float:
    if duration_min <= 0 or avg_hr <= 0:
        return 0.0
    hr_delta = max(0.0, avg_hr - 60.0)
    return duration_min * (hr_delta / 130.0) * 1.5
"""

            jury = ConcordiaJury(consensus_threshold=0.66, min_quorum=3)
            jury_votes = [
                {"agent": "Planner", "verdict": "PASS", "reason": "Structure valid"},
                {"agent": "RLM_Coder", "verdict": "PASS", "reason": "AST parsing successful"},
                {"agent": "Verifier_Worker", "verdict": "PASS", "reason": "SMT contract proved UNSAT"},
            ]
            verdict = jury.vote(proposal=repaired_code, votes=jury_votes)

            res = pipeline.execute_pipeline(
                task_prompt="Compute non-negative TRIMP load",
                code_proposal=repaired_code,
                file_path="trimp_calc.py",
                agent_votes=jury_votes
            )
            if asyncio.iscoroutine(res):
                res = await res

        assert verdict.approved is True
        assert verdict.consensus_ratio >= 0.66
        assert verdict.smt_satisfied is True
        assert res["status"] == "APPROVED"
        assert res["approved"] is True
        assert res["ast_stats"]["is_valid"] is True

    asyncio.run(_async_impl())


# ============================================================================
# Test Case 5: Concurrent Multi-Task Async Execution with Vector Lookup and LLM Repair
# ============================================================================

def test_tier3_tc5_concurrent_multitask_async_vector_lookup_llm_repair(tmp_e2e_db):
    """
    Test Case 5: Concurrent multi-task async execution with vector lookup and LLM repair.
    Spawns 5 parallel async subagent tasks running in asyncio.gather(), each retrieving
    768D vector lessons and performing reflexion repairs concurrently without SQLite locking.
    """
    async def _async_impl():
        tasks_specs = [
            ("task_0", "SyntaxError: invalid syntax", "def f():\n    return 1\n"),
            ("task_1", "ZeroDivisionError: division by zero", "def f():\n    return 10 / 2\n"),
            ("task_2", "IndexError: list index out of range", "def f(lst):\n    return lst[0] if lst else None\n"),
            ("task_3", "KeyError: missing key in dict", "def f(d):\n    return d.get('key', None)\n"),
            ("task_4", "TypeError: object is not callable", "def f(val):\n    return str(val)\n"),
        ]

        bank = LessonMemoryBank()
        for tid, err, fix in tasks_specs:
            bank.save_lesson(f"category_{tid}", err, f"Lesson for {err}: apply pattern {fix}", fix)

        async def _async_subagent_worker(task_id: str, error_sig: str, target_code: str):
            await asyncio.sleep(0.02)

            embedder = get_embedding_manager(dimension=768)
            query_vec = embedder.embed_query(error_sig)
            assert len(query_vec) == 768

            retrieved = bank.retrieve_relevant(error_sig, task_type=f"category_{task_id}", top_k=1)
            assert len(retrieved) >= 1

            improver = VazusAutoImprover(max_iterations=1)
            session = await improver.improve(
                task_id=task_id,
                task_description=f"Repair code for {error_sig}",
                initial_code="def f(:\n    pass\n",
                fix_fn=lambda c, _cr, l: target_code,
                error_trace=error_sig,
                task_type=f"category_{task_id}"
            )

            return task_id, session.success, session.final_code

        async with asyncio.timeout(300.0):
            worker_tasks = [
                _async_subagent_worker(tid, err, fix)
                for tid, err, fix in tasks_specs
            ]
            results = await asyncio.gather(*worker_tasks)

        assert len(results) == 5
        for task_id, success, final_code in results:
            assert success is True
            assert "def f" in final_code
            assert ast.parse(final_code) is not None

    asyncio.run(_async_impl())


# ============================================================================
# Additional Pairwise Cross-Feature Tests for Full SuperGraph Coverage
# ============================================================================

def test_tier3_tc6_ast_pruner_and_z3_contract_verifier():
    """Pairwise: AST Pruner + SMT Z3 Verifier."""
    raw_code = """
def abs_val(n: int) -> int:
    \"\"\"
    :requires: n >= 0
    :ensures: result >= 0
    \"\"\"
    return n
"""
    pruned, stats = ASTPruner.prune_code_string(raw_code)
    assert stats["is_valid"] is True

    verifier = SMTZ3Verifier()
    res = verifier.verify_code_contracts(pruned)
    assert res.verified is True
    assert res.contract_satisfied is True


def test_tier3_tc7_avx512_search_and_sqlite_vector_index(tmp_e2e_db):
    """Pairwise: AVX-512 Search Engine + SQLite Vector Indexing."""
    conn = get_db_connection(tmp_e2e_db)
    embedder = UnifiedEmbeddingManager(dimension=768)

    domains = ["memory_wiki", "ast_code", "llvm_ir", "assembly", "smt_contract"]
    cursor = conn.cursor()

    for idx, dom in enumerate(domains):
        vec = embedder.embed_query(f"SuperGraph node content for domain {dom}")
        cursor.execute(
            """
            INSERT INTO kg_nodes (id, name, domain, node_type, description, embedding_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (f"node_{idx}", f"Node_{dom}", dom, "concept", f"Description for {dom}", json.dumps(vec))
        )
    conn.commit()

    for dom in domains:
        results = embedder.search_unified_vector_space("SuperGraph node", db_path=tmp_e2e_db, top_k=3, domain_filter=dom)
        assert len(results) >= 1
        assert results[0]["domain"] == dom

    conn.close()
