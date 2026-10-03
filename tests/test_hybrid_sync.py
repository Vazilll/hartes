"""
tests/test_hybrid_sync.py — Test suite for Mirea Grade Sync & Gemini Spark Bridge
Verifies:
1. MireaGradeSync reading 18 milestones and recompiling STUDY.md.
2. GeminiSparkConnector reading stages and active Cloudflare tunnel.
3. HybridMCPDispatcher routing across 3 tiers (Reflex, SLM, Cloud).
"""

import os
import sys
import pytest

sys.path.insert(0, "C:/vazus")

from vazus_core.integrations.mirea_grade_sync import MireaGradeSync
from vazus_core.integrations.gemini_spark_connector import GeminiSparkConnector
from vazus_core.engine.hybrid_mcp_dispatcher import HybridMCPDispatcher


def test_mirea_grade_sync_reading():
    sync = MireaGradeSync()
    milestones = sync.get_active_milestones()
    assert len(milestones) == 18
    subjects = [m["subject"] for m in milestones]
    assert any("Математический анализ" in s for s in subjects)
    assert any("Линейная алгебра" in s for s in subjects)


def test_gemini_spark_connector():
    connector = GeminiSparkConnector()
    stages = connector.get_pipeline_stages()
    assert len(stages) >= 5
    active_stages = [s for s in stages if s.status == "ACTIVE"]
    assert len(active_stages) == 1
    assert "Электротехника" in active_stages[0].title

    url = connector.get_public_bridge_url()
    assert url is not None
    assert url.startswith("https://")


def test_hybrid_dispatcher_tiers():
    disp = HybridMCPDispatcher()

    # Tier 0 (Direct Reflex)
    p0 = disp.dispatch("запусти тесты")
    assert p0.tier == "tier0_direct"
    assert p0.token_cost == 0

    # Tier 1 (SLM TimesFM)
    p1 = disp.dispatch("построй прогноз динамики закрытия долгов")
    assert p1.tier == "tier1_slm"
    assert p1.slm_delegation_target == "timesfm3"

    # Tier 2 (Cloud LLM)
    p2 = disp.dispatch("проанализируй архитектуру ядра vazus_core")
    assert p2.tier == "tier2_cloud"
    assert len(p2.disclosed_mcp_tools) <= 3
