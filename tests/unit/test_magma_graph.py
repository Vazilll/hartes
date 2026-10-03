"""
tests/test_magma_graph.py — Tests for MAGMA 4-Graph Engine.
"""

import tempfile
import pytest
from pathlib import Path
from vazus_core.memory.magma_graph import MAGMAGraphEngine, MAGMAEdgeType


@pytest.fixture
def temp_magma():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test_magma.db")
        engine = MAGMAGraphEngine(db_path=db_path)
        yield engine


def test_magma_add_and_hebbian_reinforce(temp_magma):
    # 1. Add edge
    success = temp_magma.add_edge("node_a", "node_b", relation=MAGMAEdgeType.CAUSAL, strength=0.5)
    assert success is True

    # 2. Hebbian reinforce
    new_w = temp_magma.reinforce_co_retrieval("node_a", "node_b", boost=0.1, relation=MAGMAEdgeType.CAUSAL)
    assert new_w > 0.5
    assert new_w <= 1.0


def test_magma_intent_aware_traverse(temp_magma):
    # Setup graph topology
    temp_magma.add_edge("root", "design_doc", relation=MAGMAEdgeType.CAUSAL, strength=0.9)
    temp_magma.add_edge("root", "ast_signature", relation=MAGMAEdgeType.ENTITY, strength=0.9)
    temp_magma.add_edge("root", "v1_release", relation=MAGMAEdgeType.TEMPORAL, strength=0.9)

    # Intent: "why" -> causal prioritized
    causal_results = temp_magma.intent_aware_traverse("root", intent="why did we choose this", max_depth=1)
    assert len(causal_results) >= 1
    assert causal_results[0]["node_id"] == "design_doc"

    # Intent: "when" -> temporal prioritized
    temporal_results = temp_magma.intent_aware_traverse("root", intent="when was this committed", max_depth=1)
    assert len(temporal_results) >= 1
    assert temporal_results[0]["node_id"] == "v1_release"


def test_magma_exponential_decay(temp_magma):
    temp_magma.add_edge("old_node", "stale_node", relation=MAGMAEdgeType.SEMANTIC, strength=0.04)
    # Decay with threshold 0.05 should prune the edge
    pruned = temp_magma.apply_exponential_decay(half_life_days=30, min_threshold=0.05)
    assert pruned == 1
