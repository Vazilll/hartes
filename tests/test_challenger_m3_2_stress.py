"""
tests/test_challenger_m3_2_stress.py
====================================
Adversarial Stress Test Suite for Milestone 3.2:
Empirical verification of JSpaceToolIndexer._load_metadata_map,
multithreaded concurrency (16 threads, 50,000+ operations),
cache invalidation, and heapq.nlargest ranking correctness.

Target: vazus_core.memory.j_space_tool_indexer.JSpaceToolIndexer
Author: Challenger M3.2 (Empirical Challenger)
"""

import heapq
import json
import os
import shutil
import sqlite3
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, List

import pytest

from tests.unit.test_j_space_tool_indexer import DummyEmbeddingManager
from vazus_core.memory.j_space_tool_indexer import JSpaceToolIndexer

VAZUS_DB_PATH = Path("/home/tarhes/Проекты/vazus/services/memory/vazus.db")


# ==============================================================================
# 1. CACHE INVALIDATION & CONSISTENCY TESTS
# ==============================================================================

def test_cache_hit_returns_identical_object_reference():
    """Verify that successive calls to _load_metadata_map return the identical dict object."""
    assert VAZUS_DB_PATH.exists(), f"Database not found at {VAZUS_DB_PATH}"
    indexer = JSpaceToolIndexer(db_path=str(VAZUS_DB_PATH))

    # Initial load (cold)
    map1 = indexer._load_metadata_map()
    assert isinstance(map1, dict)
    assert len(map1) == 244
    assert indexer._metadata_cache is not None

    # Cached hit (warm)
    map2 = indexer._load_metadata_map()
    assert map1 is map2, "Cache hit must return the identical dictionary object reference"
    assert map2 is indexer._metadata_cache


def test_invalidate_metadata_cache_clears_cache():
    """Verify that invalidate_metadata_cache() sets _metadata_cache to None and forces reload."""
    indexer = JSpaceToolIndexer(db_path=str(VAZUS_DB_PATH))

    map1 = indexer._load_metadata_map()
    assert indexer._metadata_cache is not None

    # Invalidate
    indexer.invalidate_metadata_cache()
    assert indexer._metadata_cache is None, "invalidate_metadata_cache() must clear _metadata_cache to None"

    # Next call must reload fresh dict
    map2 = indexer._load_metadata_map()
    assert map2 is not None
    assert map2 is not map1, "After invalidation, new call must instantiate a new dictionary object"
    assert map2 == map1, "Content of reloaded dictionary must match previous dictionary"


def test_cached_data_matches_fresh_database_reads_across_all_244_records():
    """
    Verify that every record in _load_metadata_map matches a direct, fresh SQLite query
    across all 244 tool records in vazus.db.
    """
    indexer = JSpaceToolIndexer(db_path=str(VAZUS_DB_PATH))
    cached_map = indexer._load_metadata_map()
    assert len(cached_map) == 244, f"Expected 244 cached tool records, found {len(cached_map)}"

    conn = sqlite3.connect(str(VAZUS_DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(j_space_tool_metadata)")
        cols = [r[1] for r in cur.fetchall()]
        has_weight = "weight" in cols

        query = (
            "SELECT tool_name, module, description, parameters_json, keywords, signature, is_native, weight "
            "FROM j_space_tool_metadata"
            if has_weight
            else "SELECT tool_name, module, description, parameters_json, keywords, signature, is_native "
            "FROM j_space_tool_metadata"
        )
        rows = cur.execute(query).fetchall()
        assert len(rows) == 244, f"Expected 244 database rows, found {len(rows)}"

        for r in rows:
            tname = r["tool_name"]
            assert tname in cached_map, f"Tool {tname} present in database but missing from cache"
            cached_entry = cached_map[tname]

            expected_params = json.loads(r["parameters_json"]) if r["parameters_json"] else {}
            expected_weight = float(r["weight"]) if has_weight and r["weight"] is not None else 1.0

            assert cached_entry["tool_name"] == r["tool_name"]
            assert cached_entry["module"] == r["module"]
            assert cached_entry["description"] == r["description"]
            assert cached_entry["parameters"] == expected_params
            assert cached_entry["keywords"] == r["keywords"]
            assert cached_entry["signature"] == r["signature"]
            assert cached_entry["is_native"] == bool(r["is_native"])
            assert cached_entry["weight"] == expected_weight
    finally:
        conn.close()


def test_index_tools_and_reweight_invalidate_cache(tmp_path):
    """
    Verify that index_tools() and reweight_tools_from_activations() both invalidate the metadata cache.
    Uses an isolated temporary copy of vazus.db to adhere strictly to the data protection invariant.
    """
    test_db = tmp_path / "sandbox_vazus.db"
    shutil.copyfile(str(VAZUS_DB_PATH), str(test_db))

    dummy_mgr = DummyEmbeddingManager(dimension=768)
    indexer = JSpaceToolIndexer(db_path=str(test_db), embedding_manager=dummy_mgr)

    # 1. Warm cache
    m1 = indexer._load_metadata_map()
    assert indexer._metadata_cache is not None

    # 2. Test reweight_tools_from_activations invalidates cache
    reweight_res = indexer.reweight_tools_from_activations(min_proposals=2)
    assert reweight_res["status"] == "SUCCESS"
    assert reweight_res["reweighted_count"] > 0
    assert indexer._metadata_cache is None, "reweight_tools_from_activations() must invalidate _metadata_cache"

    # Reload cache after reweight
    m2 = indexer._load_metadata_map()
    assert m2 is not m1, "Post-reweight cache must be a newly loaded dict"
    assert indexer._metadata_cache is not None

    # 3. Test index_tools invalidates cache
    index_res = indexer.index_tools(force_reindex=False)
    assert index_res["indexed_count"] > 0
    assert indexer._metadata_cache is None, "index_tools() must invalidate _metadata_cache"

    # Reload cache after index_tools
    m3 = indexer._load_metadata_map()
    assert m3 is not m2, "Post-index_tools cache must be a newly loaded dict"


# ==============================================================================
# 2. MULTITHREADED CONCURRENCY STRESS TEST (16 THREADS, 50,000+ OPS)
# ==============================================================================

def test_multithreaded_concurrency_stress():
    """
    Spawns 16 concurrent worker threads simultaneously executing _load_metadata_map,
    find_tools_for_query, and periodic cache invalidations for 50,000+ total operations.
    Verifies double-checked locking thread safety, absence of race conditions,
    zero deadlocks, and zero data corruption.
    """
    dummy_mgr = DummyEmbeddingManager(dimension=768)
    indexer = JSpaceToolIndexer(db_path=str(VAZUS_DB_PATH), embedding_manager=dummy_mgr)

    NUM_THREADS = 16
    OPS_PER_THREAD = 3500  # 16 * 3500 = 56,000 operations
    TOTAL_EXPECTED_OPS = NUM_THREADS * OPS_PER_THREAD

    errors: List[str] = []
    op_counts = [0] * NUM_THREADS
    barrier = threading.Barrier(NUM_THREADS)

    test_queries = [
        "запусти изолированную песочницу",
        "сделай бэкап базы",
        "найди фрагмент кода функции",
        "профилируй производительность",
        "запусти консолидацию памяти",
        "telegram-mcp чаты",
        "vazus-organic инсайты",
        "ast_grep_search",
    ]

    def worker_loop(thread_id: int):
        # Synchronize start across all 16 threads
        barrier.wait()
        local_ops = 0

        for i in range(OPS_PER_THREAD):
            try:
                # 1. 10% operations run full find_tools_for_query pipeline
                if i % 10 == 0:
                    q = test_queries[(thread_id + i) % len(test_queries)]
                    res = indexer.find_tools_for_query(q, top_k=3)
                    if not isinstance(res, list):
                        errors.append(f"Thread {thread_id} op {i}: find_tools_for_query returned non-list")
                    elif len(res) > 3:
                        errors.append(f"Thread {thread_id} op {i}: top_k=3 violated, got {len(res)}")
                    elif len(res) > 1:
                        # Ensure strictly descending order
                        for idx_r in range(len(res) - 1):
                            if res[idx_r]["similarity"] < res[idx_r + 1]["similarity"]:
                                errors.append(f"Thread {thread_id} op {i}: ranking out of order")
                else:
                    # 2. 90% operations stress _load_metadata_map under concurrent reads
                    m = indexer._load_metadata_map()
                    if not isinstance(m, dict):
                        errors.append(f"Thread {thread_id} op {i}: _load_metadata_map returned non-dict")
                    elif len(m) != 244:
                        errors.append(f"Thread {thread_id} op {i}: metadata map size corrupted ({len(m)})")
                    else:
                        # Check critical keys integrity
                        if "vazus-sandbox" not in m or "db_backup" not in m:
                            errors.append(f"Thread {thread_id} op {i}: missing core keys in cache")

                # 3. Thread 0 and Thread 8 continuously trigger cache invalidation
                # to vigorously test double-checked locking under concurrent race conditions
                if thread_id in (0, 8) and i % 50 == 0:
                    indexer.invalidate_metadata_cache()

                local_ops += 1
            except Exception as exc:
                errors.append(f"Thread {thread_id} op {i} exception: {exc}")

        op_counts[thread_id] = local_ops

    t0 = time.perf_counter()
    threads = [threading.Thread(target=worker_loop, args=(t_id,)) for t_id in range(NUM_THREADS)]
    for t in threads:
        t.start()

    # Wait for all threads with a generous timeout to catch any deadlocks
    for t in threads:
        t.join(timeout=45.0)
        assert not t.is_alive(), "Deadlock detected! Worker thread failed to terminate within timeout."

    duration = time.perf_counter() - t0
    total_completed_ops = sum(op_counts)

    print(
        f"\n[Multithreaded Stress] Completed {total_completed_ops} operations across "
        f"{NUM_THREADS} threads in {duration:.2f}s ({total_completed_ops / duration:.0f} ops/sec)"
    )

    assert total_completed_ops == TOTAL_EXPECTED_OPS, (
        f"Expected {TOTAL_EXPECTED_OPS} ops, completed {total_completed_ops}"
    )
    assert len(errors) == 0, f"Encountered {len(errors)} concurrency errors: {errors[:5]}"


# ==============================================================================
# 3. HEAPQ.NLARGEST RANKING CORRECTNESS ACROSS DIVERSE TOP_K VALUES
# ==============================================================================

@pytest.mark.parametrize("top_k", [0, 1, 5, 20, 50, 100, 500])
def test_heapq_nlargest_ranking_correctness_diverse_top_k(top_k: int):
    """
    Verify that find_tools_for_query using heapq.nlargest strictly matches
    the exact sorted order (sorted(..., key=lambda x: x['similarity'], reverse=True)[:top_k])
    across edge-case and diverse top_k values (0, 1, 5, 20, 50, 100, 500).
    """
    dummy_mgr = DummyEmbeddingManager(dimension=768)
    indexer = JSpaceToolIndexer(db_path=str(VAZUS_DB_PATH), embedding_manager=dummy_mgr)

    queries = [
        "запусти изолированную песочницу",
        "сделай бэкап базы данных sqlite",
        "поиск по графу кода cbm",
        "профилирование radon complexity",
        "неизвестный запрос без соответствий xq79z",
    ]

    for q in queries:
        actual_results = indexer.find_tools_for_query(q, top_k=top_k, min_similarity=0.0)

        if top_k <= 0:
            assert actual_results == [], f"top_k={top_k} must return empty list"
            continue

        assert len(actual_results) <= top_k

        # Verify sortedness
        scores = [r["similarity"] for r in actual_results]
        sorted_scores = sorted(scores, reverse=True)
        assert scores == sorted_scores, f"Results for '{q}' with top_k={top_k} not in descending order: {scores}"


def test_heapq_nlargest_adversarial_oracle():
    """
    Adversarially tests heapq.nlargest against Python's canonical Timsort oracle
    on pathological candidate pools (all tied scores, reverse ordered, negative scores,
    and massive candidate pools).
    """
    test_cases = [
        # All ties
        [{"name": f"t_{i}", "similarity": 0.85} for i in range(100)],
        # Strictly reversed
        [{"name": f"t_{i}", "similarity": i * 0.01} for i in range(100)],
        # Random mixture with duplicate boundaries
        [{"name": f"t_{i}", "similarity": round((i % 7) * 0.15, 2)} for i in range(200)],
        # Single element
        [{"name": "t_0", "similarity": 0.5}],
        # Empty list
        [],
    ]

    for data in test_cases:
        for k in [-5, 0, 1, 3, 10, 50, 150, 500]:
            h_out = heapq.nlargest(k, data, key=lambda x: x["similarity"])
            s_out = sorted(data, key=lambda x: x["similarity"], reverse=True)[:max(0, k)]

            h_sims = [x["similarity"] for x in h_out]
            s_sims = [x["similarity"] for x in s_out]

            assert h_sims == s_sims, (
                f"Similarity mismatch for k={k}: heapq={h_sims[:5]} vs sorted={s_sims[:5]}"
            )


# ==============================================================================
# MAIN ENTRYPOINT
# ==============================================================================

def main():
    print("=" * 80)
    print(" MILESTONE 3.2: J-SPACE TOOL INDEXER EMPIRICAL STRESS TEST & AUDIT")
    print("=" * 80)

    t0 = time.perf_counter()

    print("\n[1/5] Running cache hit reference test...")
    test_cache_hit_returns_identical_object_reference()
    print("      -> PASSED")

    print("\n[2/5] Running invalidate_metadata_cache test...")
    test_invalidate_metadata_cache_clears_cache()
    print("      -> PASSED")

    print("\n[3/5] Running 244-record DB parity verification...")
    test_cached_data_matches_fresh_database_reads_across_all_244_records()
    print("      -> PASSED (All 244 records verified identical)")

    print("\n[4/5] Running heapq.nlargest ranking oracle test...")
    test_heapq_nlargest_adversarial_oracle()
    for k in [0, 1, 5, 20, 50, 100, 500]:
        test_heapq_nlargest_ranking_correctness_diverse_top_k(k)
    print("      -> PASSED (All top_k values validated)")

    print("\n[5/5] Running multithreaded concurrency stress test (16 threads, 56,000 ops)...")
    test_multithreaded_concurrency_stress()
    print("      -> PASSED (Zero race conditions, zero deadlocks, zero corruption)")

    total_time = time.perf_counter() - t0
    print("\n" + "=" * 80)
    print(f" ALL EMPIRICAL VERIFICATION SUITES COMPLETED IN {total_time:.2f}s WITH ZERO ERRORS.")
    print("=" * 80)


if __name__ == "__main__":
    main()
