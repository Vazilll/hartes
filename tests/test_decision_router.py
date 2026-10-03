"""
tests/test_decision_router.py
==============================
Test suite for System 1 Decision Router:
- Replaces hardcoded string heuristics with typed decision layer
- Fast cosine/centroid routing across Silicon tiers (NPU / GPU Flash / Cloud Deep)
- Strict formal verification triggers routing to Cloud Deep with high salience
"""

import pytest
from vazus_core.engine.decision_router import SystemOneRouter, RouteTarget, RoutingResult


def test_router_initialization():
    router = SystemOneRouter()
    assert router is not None


def test_formal_proof_routed_to_tier_3():
    router = SystemOneRouter()
    res = router.decide("Докажи теорему эквивалентности графа переходов в Z3")
    assert isinstance(res, RoutingResult)
    assert res.target == RouteTarget.TIER_3_CLOUD_DEEP
    assert res.confidence >= 0.85
    assert res.j_space_salience >= 0.90


def test_deep_research_routed_to_tier_3():
    router = SystemOneRouter()
    res = router.decide("Проведи deep research по 500 источникам и построй мультиагентный консенсус")
    assert res.target == RouteTarget.TIER_3_CLOUD_DEEP
    assert res.confidence >= 0.85


def test_quick_local_query_routed_to_tier_2():
    router = SystemOneRouter()
    res = router.decide("Выведи текущие задачи и статус памяти")
    assert res.target == RouteTarget.TIER_2_GPU_FLASH
    assert res.confidence >= 0.60
    assert res.estimated_power_watts > 0.0


def test_latent_embedding_query_routed_to_tier_1():
    router = SystemOneRouter()
    res = router.decide("Извлеки 768D вектор активации для концепта в NPU")
    assert res.target == RouteTarget.TIER_1_NPU_LATENT
    assert res.confidence >= 0.70
