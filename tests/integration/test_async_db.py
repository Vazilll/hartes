"""
tests/integration/test_async_db.py — Comprehensive Tests for AsyncDatabasePool & Async Embeddings.
"""

import asyncio
import pytest
import tempfile
from pathlib import Path

from vazus_core.memory.async_db import (
    AsyncDatabasePool,
    execute_query_async,
    execute_mutation_async,
    execute_batch_async,
)
from vazus_core.memory.embeddings import (
    UnifiedEmbeddingManager,
    EmbeddingMicroBatcher,
    get_embedding_async,
    compute_batch_similarity_async,
    search_unified_vector_space_async,
)


@pytest.mark.anyio
async def test_async_database_pool_query():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test_async.db")
        pool = AsyncDatabasePool(db_path=db_path, max_workers=2)

        # Create table and insert
        await pool.execute_mutation("CREATE TABLE items (id TEXT PRIMARY KEY, val INTEGER)")
        await pool.execute_mutation("INSERT INTO items (id, val) VALUES (?, ?)", ("item_1", 42))

        # Query
        rows = await pool.execute_query("SELECT id, val FROM items WHERE id=?", ("item_1",))
        assert len(rows) == 1
        assert rows[0][0] == "item_1"
        assert rows[0][1] == 42

        # Batch insert
        await pool.execute_batch("INSERT INTO items (id, val) VALUES (?, ?)", [("item_2", 100), ("item_3", 200)])
        all_rows = await pool.execute_query("SELECT count(*) FROM items")
        assert all_rows[0][0] == 3

        await pool.aclose()


@pytest.mark.anyio
async def test_async_db_helper_coroutines():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test_helpers.db")

        await execute_mutation_async("CREATE TABLE logs (id TEXT PRIMARY KEY, msg TEXT)", db_path=db_path)
        rowcount = await execute_mutation_async("INSERT INTO logs (id, msg) VALUES (?, ?)", ("l1", "init"), db_path=db_path)
        assert rowcount == 1

        batch_count = await execute_batch_async(
            "INSERT INTO logs (id, msg) VALUES (?, ?)",
            [("l2", "event2"), ("l3", "event3")],
            db_path=db_path
        )
        assert batch_count == 2

        rows = await execute_query_async("SELECT id, msg FROM logs ORDER BY id", db_path=db_path)
        assert len(rows) == 3
        assert rows[0][0] == "l1"
        assert rows[1][0] == "l2"
        assert rows[2][0] == "l3"


@pytest.mark.anyio
async def test_async_db_high_concurrency_lock_free():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test_stress.db")
        pool = AsyncDatabasePool(db_path=db_path, max_workers=4)

        await pool.execute_mutation("CREATE TABLE stress_items (id TEXT PRIMARY KEY, num INTEGER)")

        tasks = [
            pool.execute_mutation("INSERT INTO stress_items (id, num) VALUES (?, ?)", (f"item_{i}", i))
            for i in range(25)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for idx, res in enumerate(results):
            assert not isinstance(res, Exception), f"Task {idx} raised: {res}"
            assert res == 1

        count_rows = await pool.execute_query("SELECT count(*) FROM stress_items")
        assert count_rows[0][0] == 25
        pool.close()


@pytest.mark.anyio
async def test_async_embeddings_coroutines():
    manager = UnifiedEmbeddingManager(dimension=768)

    # 1. Async embedding generation
    vec1 = await manager.get_embedding_async("Kernel SuperGraph OS Architecture")
    vec2 = await get_embedding_async("AST Graph Topo Code Verification")
    assert len(vec1) == 768
    assert len(vec2) == 768

    # 2. Async batch similarity computation
    sims = await manager.compute_batch_similarity_async(vec1, [vec2, vec1])
    assert len(sims) == 2
    assert abs(sims[1] - 1.0) < 1e-3

    sims_global = await compute_batch_similarity_async(vec1, [vec2])
    assert len(sims_global) == 1


@pytest.mark.anyio
async def test_embedding_micro_batcher_coalescing():
    batcher = EmbeddingMicroBatcher(batch_size=8, timeout_ms=10.0)

    # Dispatch 10 parallel async embedding requests
    prompts = [f"Subagent query prompt task {i}" for i in range(10)]
    tasks = [batcher.get_embedding(p) for p in prompts]
    results = await asyncio.gather(*tasks)

    assert len(results) == 10
    for emb in results:
        assert len(emb) == 768
        assert not any(x != x for x in emb)  # No NaNs
