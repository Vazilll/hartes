"""
tests/test_memory_facts_v2.py — Test suite for memory_facts_v2 schema and tiered promotion governance.
"""

import os
import tempfile
import pytest

from vazus_core.memory.mem0_memory_engine import Mem0Engine


@pytest.fixture
def temp_mem_engine():
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_vazus.db")
    engine = Mem0Engine(db_path=db_path)
    return engine


def test_memory_facts_v2_quarantine_and_promotion(temp_mem_engine):
    engine = temp_mem_engine

    # 1. Record an untrusted observation
    res = engine.record_observation_v2(
        fact_text="Use asyncio.timeout for subagents",
        category="architecture",
        source_agent="antigravity",
        status="UNTRUSTED_OBSERVATION"
    )
    assert res["status"] == "RECORDED"
    fact_id = res["id"]

    # 2. Verified search should NOT return untrusted observations
    verified = engine.search_verified_facts_v2("asyncio timeout", top_k=5)
    assert len(verified) == 0

    # 3. Promote fact to VERIFIED_FACT
    promo = engine.promote_fact_v2(
        fact_id=fact_id,
        to_status="VERIFIED_FACT",
        by_agent="concordia_jury",
        justification="Verified by unit tests"
    )
    assert promo["status"] == "PROMOTED"
    assert promo["to"] == "VERIFIED_FACT"

    # 4. Verified search now finds it
    verified_after = engine.search_verified_facts_v2("asyncio timeout", top_k=5)
    assert len(verified_after) == 1
    assert verified_after[0]["id"] == fact_id
    assert verified_after[0]["status"] == "VERIFIED_FACT"


def test_memory_facts_v2_deduplication(temp_mem_engine):
    engine = temp_mem_engine

    res1 = engine.record_observation_v2("Duplicate fact text", category="test")
    assert res1["status"] == "RECORDED"

    # Same text should be deduplicated
    res2 = engine.record_observation_v2("Duplicate fact text", category="test")
    assert res2["status"] == "DEDUP_EXISTS"
