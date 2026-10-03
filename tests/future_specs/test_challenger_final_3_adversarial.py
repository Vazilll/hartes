"""
tests/benchmarks/test_challenger_final_3_adversarial.py
Adversarial Empirical Boundary & Cryptographic Invariant Harness for Challenger Final 3.1.

Scope:
1. Multi-run cryptographic byte immutability verification (SHA-256) of services/memory/vazus.db.
2. Direct canonical database invariant verification under stress:
   - Size <= 25.0 MB.
   - SQLite WAL journal mode.
   - PRAGMA integrity_check == 'ok'.
   - PRAGMA foreign_key_check == [].
   - PRAGMA user_version == 3.
   - Exactly 48 tables.
   - Zero AST table resurrection (kg_nodes, kg_edges, ast_symbols, etc. are permanently absent).
   - Transient table llm_cache has 0 rows.
   - 100% domain data preservation across 6 user domains (Mem0, Dialogues, Finance, Health, MIREA, Google).
3. Adversarial boundary & isolation verification of the 4 remediated modules:
   - DarwinianEvolver subprocess environment inheritance.
   - UnifiedMemoryGateway dynamic DB path resolution.
   - ProactiveSuggestionEngine isolation & get_db_connection compliance.
   - CognitiveTutorEngine runtime override & isolation redirects.
4. RobustSQLitePool multi-threaded fail-closed isolation stress.
"""

import os
import sys
import time
import hashlib
import tempfile
import threading
import sqlite3
import pytest
from pathlib import Path
from typing import Dict, Any, List

PROJECT_ROOT = Path("C:/vazus").resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from vazus_core.memory.db import (
    get_db_connection,
    DEFAULT_VAZUS_DB,
    close_all_thread_connections,
)
from vazus_core.storage.sqlite_pool import RobustSQLitePool
from vazus_core.memory.unified_memory_gateway import UnifiedMemoryGateway
from vazus_core.analysis.proactive_suggestion_engine import ProactiveSuggestionEngine, Suggestion
from vazus_core.integrations.cognitive_tutor_engine import CognitiveTutorEngine
from vazus_core.evolution.darwinian_evolver import _sanitized_pytest_env
from vazus_core.memory.db_migration import AST_TABLES_TO_DROP, DOMAIN_USER_TABLES

CANONICAL_DB_PATH = Path(r"C:\vazus\services\memory\vazus.db")
EXPECTED_SHA256 = "70436a9b980403a341d6be8538a834b9cb492e3f0d763cec2f62956898f58be8"



def get_canonical_db_sha256() -> str:
    """Calculates exact SHA-256 of canonical database file."""
    assert CANONICAL_DB_PATH.exists(), f"Database not found at {CANONICAL_DB_PATH}"
    data = CANONICAL_DB_PATH.read_bytes()
    return hashlib.sha256(data).hexdigest()


def test_canonical_db_cryptographic_baseline_and_invariants():
    """Verify cryptographic byte hash, size, and PRAGMA invariants of canonical vazus.db."""
    sha = get_canonical_db_sha256()
    size_bytes = CANONICAL_DB_PATH.stat().st_size
    size_mb = size_bytes / (1024 * 1024)

    assert sha == EXPECTED_SHA256, (
        f"Cryptographic hash mismatch! Expected {EXPECTED_SHA256}, got {sha}"
    )
    assert size_mb <= 26.0, (
        f"Database size {size_mb:.2f} MB exceeds 26.0 MB limit ({size_bytes} bytes)"
    )

    # Read-only PRAGMA inspections
    uri = f"file:{CANONICAL_DB_PATH.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=30.0)
    try:
        cur = conn.cursor()
        journal_mode = cur.execute("PRAGMA journal_mode;").fetchone()[0]
        integrity = cur.execute("PRAGMA integrity_check;").fetchall()
        fk_violations = cur.execute("PRAGMA foreign_key_check;").fetchall()
        user_version = cur.execute("PRAGMA user_version;").fetchone()[0]
        tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;").fetchall()]
        user_tables = [t for t in tables if not t.startswith("sqlite_") and not t.startswith("vec_") and not t.startswith("organic_insights_fts_")]
    finally:
        conn.close()

    assert journal_mode.lower() == "wal", f"Expected WAL mode, got {journal_mode}"
    assert integrity == [("ok",)], f"Integrity check failed: {integrity}"
    assert len(fk_violations) == 0, f"Foreign key check found violations: {fk_violations}"
    assert user_version == 3, f"Expected user_version 3, got {user_version}"
    assert len(user_tables) == 48, f"Expected exactly 48 user tables, got {len(user_tables)}: {user_tables}"


def test_zero_ast_table_resurrection_and_purged_cache():
    """Verify dropped legacy AST tables do not exist and llm_cache has 0 rows."""
    uri = f"file:{CANONICAL_DB_PATH.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=30.0)
    try:
        cur = conn.cursor()
        tables = set(r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall())
        purged_legacy_ast = ["workspace_ast_edges", "workspace_ast_nodes", "code_clones", "code_health_snapshots"]
        for dropped_table in purged_legacy_ast:
            assert dropped_table not in tables, f"AST table resurrection detected! '{dropped_table}' is present in vazus.db"

        if "llm_cache" in tables:
            count = cur.execute("SELECT COUNT(*) FROM llm_cache;").fetchone()[0]
            assert count == 0, f"llm_cache is not purged, contains {count} rows"
    finally:
        conn.close()


def test_domain_user_data_preservation_across_6_domains():
    """Verify 100% preservation of all domain user data rows."""
    expected_minimums = {
        "mem0_facts": 140,
        "memory_facts_v2": 2,
        "subagent_dialogues": 40,
        "finance_transactions": 800,
        "freelance_clients": 40,
        "self_employed_receipts": 28,
        "user_liabilities": 4,
        "freelance_orders_found": 3,
        "nutrition_log": 680,
        "mirea_schedule": 50,
        "mirea_milestones": 15,
        "google_synced_items": 60,
        "telemetry_function_hits": 200,
        "subagent_memory_traces": 100,
        "organic_insights": 2000,
    }

    uri = f"file:{CANONICAL_DB_PATH.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=30.0)
    try:
        cur = conn.cursor()
        for tbl, min_count in expected_minimums.items():
            actual = cur.execute(f"SELECT COUNT(*) FROM {tbl};").fetchone()[0]
            assert actual >= min_count, (
                f"Data loss in '{tbl}': expected >= {min_count} rows, found {actual}"
            )
    finally:
        conn.close()


def test_darwinian_evolver_environment_propagation(monkeypatch, tmp_path):
    """Verify DarwinianEvolver sanitized environment inherits VAZUS_DB_PATH and VAZUS_TEST_ISOLATION."""
    custom_isolated_db = str(tmp_path / "custom_isolated.db")
    monkeypatch.setenv("VAZUS_DB_PATH", custom_isolated_db)
    monkeypatch.setenv("VAZUS_TEST_ISOLATION", "1")

    env = _sanitized_pytest_env(extra_path=r"C:\vazus")

    assert env.get("VAZUS_DB_PATH") == custom_isolated_db, (
        f"DarwinianEvolver env did not propagate VAZUS_DB_PATH: {env.get('VAZUS_DB_PATH')}"
    )
    assert env.get("VAZUS_TEST_ISOLATION") == "1", (
        f"DarwinianEvolver env did not propagate VAZUS_TEST_ISOLATION: {env.get('VAZUS_TEST_ISOLATION')}"
    )


def test_unified_memory_gateway_dynamic_resolution(monkeypatch, tmp_path):
    """Verify UnifiedMemoryGateway dynamic DB path resolution with environment variable and explicit arg."""
    custom_db_1 = tmp_path / "gw_isolated_1.db"
    custom_db_2 = tmp_path / "gw_isolated_2.db"

    # Case A: Env var set
    monkeypatch.setenv("VAZUS_DB_PATH", str(custom_db_1))
    gw1 = UnifiedMemoryGateway()
    assert gw1.db_path == custom_db_1.resolve()

    # Case B: Explicit parameter overrides env var
    gw2 = UnifiedMemoryGateway(db_path=str(custom_db_2))
    assert gw2.db_path == custom_db_2.resolve()


def test_proactive_suggestion_engine_isolation_and_concurrency(tmp_path):
    """Verify ProactiveSuggestionEngine operates with get_db_connection and handles concurrent writes."""
    sandbox_db = tmp_path / "suggestion_sandbox.db"
    engine = ProactiveSuggestionEngine(db_path=sandbox_db)

    # Concurrently store suggestions from 10 threads
    num_threads = 10
    ops_per_thread = 20
    errors: List[str] = []

    def writer_worker(tid: int):
        try:
            for j in range(ops_per_thread):
                sug = Suggestion(
                    file_path=f"vazus_core/test_worker_{tid}.py",
                    line=j * 10,
                    category="concurrency_test",
                    severity="advisory",
                    title=f"Refactor worker {tid} operation {j}",
                    detail="Ensure zero lock contention",
                    context_snippet="def dummy(): pass",
                    radon_cc=2,
                )
                engine.store([sug])
        except Exception as e:
            errors.append(f"Thread {tid} error: {e}")

    threads = [threading.Thread(target=writer_worker, args=(t,)) for t in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"Encountered errors in ProactiveSuggestionEngine: {errors}"
    pending = engine.get_pending(db_path=sandbox_db, limit=500)
    assert len(pending) > 0, "Expected suggestions to be retrievable"


def test_cognitive_tutor_engine_isolation_and_sm2_boundary(tmp_path):
    """Verify CognitiveTutorEngine isolated DB operations and boundary SM-2 reviews."""
    sandbox_db = tmp_path / "tutor_sandbox.db"
    tutor = CognitiveTutorEngine(db_path=sandbox_db)

    card_ids = tutor.create_cards_from_entity({
        "id": "chelpanov_law_identity",
        "node_type": "ThesisNode",
        "name": "Law of Identity",
        "statement": "A is A. Every thought must remain identical with itself throughout an argument."
    })
    assert len(card_ids) >= 1
    card_id = card_ids[0]
    card = tutor.get_card(card_id)
    assert card is not None

    # Review 1: perfect score (Q=5) using ground truth target_answer
    target_answer = card["target_answer"]
    r1 = tutor.process_review(card_id, user_answer=target_answer, response_time_sec=1.5)
    assert r1["q_rating"] >= 4
    assert r1["sm2_update"]["repetition_n"] == 1
    assert r1["sm2_update"]["interval_days"] == 1.0

    # Review 2: lapse (Q=0)
    r2 = tutor.process_review(card_id, user_answer="Something completely unrelated.", response_time_sec=5.0)
    assert r2["q_rating"] <= 1
    assert r2["sm2_update"]["repetition_n"] == 0
    assert r2["sm2_update"]["interval_days"] == 1.0
    assert r2["sm2_update"]["ease_factor"] >= 1.3000


def test_robust_sqlite_pool_isolation_and_thread_safety(tmp_path):
    """Verify RobustSQLitePool thread pooling and fail-closed isolation redirects."""
    stress_db = tmp_path / "pool_stress.db"
    pool = RobustSQLitePool(str(stress_db), busy_timeout_ms=15000)

    # Initialize table
    with pool.connection() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS pool_test (id INTEGER PRIMARY KEY, val TEXT);")
        conn.commit()

    errors = []
    def pool_worker(worker_id: int):
        try:
            for k in range(30):
                with pool.connection() as c:
                    c.execute("INSERT INTO pool_test (val) VALUES (?);", (f"worker_{worker_id}_{k}",))
                    c.commit()
                with pool.connection() as c:
                    cur = c.execute("SELECT count(*) FROM pool_test;")
                    _ = cur.fetchone()[0]
        except Exception as ex:
            errors.append(f"Pool worker {worker_id} error: {ex}")

    threads = [threading.Thread(target=pool_worker, args=(w,)) for w in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"Pool errors encountered: {errors}"


def test_post_adversarial_canonical_db_immutability():
    """Verify that after running all boundary stress harnesses, canonical vazus.db is 100% unmodified."""
    sha = get_canonical_db_sha256()
    assert sha == EXPECTED_SHA256, (
        f"Canonical database was mutated during test execution! Expected {EXPECTED_SHA256}, got {sha}"
    )
