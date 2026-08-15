"""
tests.test_organic_hermes_bridge
Tests for Hermes Skill Syncer and Organic Memory Bridge in vazus_core.
"""

import os
import pytest
from vazus_core.hermes_skill_syncer import sync_hermes_skills
from vazus_core.organic_memory_bridge import record_insight, search_memory, get_organic_summary

def test_hermes_skill_syncer():
    count = sync_hermes_skills()
    assert count > 0, "Should sync at least 1 Hermes skill into Antigravity skills directory"

def test_organic_memory_bridge():
    unique_tag = "unit_test_unique_organic_insight_9876"
    record_insight("test_category", f"Insight for {unique_tag}")
    results = search_memory(unique_tag)
    assert len(results) > 0, "Should retrieve recorded memory insight from vazus.db"
    assert any(r.get("category") == "test_category" for r in results)

    summary = get_organic_summary()
    assert summary["node_count"] > 0, "vazus.db should have non-zero node_count"
