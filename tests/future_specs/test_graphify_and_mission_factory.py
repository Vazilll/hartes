"""
Unit tests for Graphify AST Engine and Multi-Agent Mission Factory.
"""

import pytest
from pathlib import Path
from vazus_core.engine.graphify_engine import GraphifyEngine, GraphifyASTVisitor
from vazus_core.missions.mission_factory import MissionFactory, MissionTask, MissionValidator


def test_graphify_ast_indexing(tmp_path):
    db_path = tmp_path / "test_vazus.db"
    engine = GraphifyEngine(db_path=str(db_path), workspace_root=r"C:\vazus")

    # Index verification package
    res = engine.index_codebase(target_dir_rel="vazus_core/verification")
    assert res["indexed_nodes"] > 10
    assert res["indexed_edges"] > 10

    # Test compact context extraction
    ctx = engine.get_compact_subgraph_context("ASTPruner")
    assert "ASTPruner" in ctx
    assert "# GRAPHIFY TOPOLOGY" in ctx


def test_graphify_missing_symbol_handling(tmp_path):
    """Verifies that querying a non-existent symbol returns informative fallback without exception."""
    db_path = tmp_path / "test_vazus.db"
    engine = GraphifyEngine(db_path=str(db_path), workspace_root=r"C:\vazus")
    ctx = engine.get_compact_subgraph_context("NonExistentSymbol_XYZ")
    assert "not found in Graphify index" in ctx


def test_mission_validator_schema_enforcement():
    task = MissionTask(
        task_id="task_1",
        role="Planner",
        description="Plan architecture",
        input_payload={"goal": "Build Graphify"},
        output_schema_keys=["plan", "steps_count"],
        validator_fn=lambda p: isinstance(p.get("steps_count"), int) and p.get("steps_count") > 0
    )

    valid_payload = {"plan": "Step 1: Parse AST", "steps_count": 3}
    invalid_payload_1 = {"plan": "Step 1"}  # Missing steps_count
    invalid_payload_2 = {"plan": "Step 1", "steps_count": 0}  # Failed validator_fn

    ok1, reason1 = MissionValidator.validate_payload(task, valid_payload)
    assert ok1 is True

    ok2, reason2 = MissionValidator.validate_payload(task, invalid_payload_1)
    assert ok2 is False
    assert "Missing required output schema key" in reason2

    ok3, reason3 = MissionValidator.validate_payload(task, invalid_payload_2)
    assert ok3 is False
    assert "Custom validator function rejected output" in reason3


def test_mission_factory_extract_json():
    factory = MissionFactory()
    text = "Here is the result:\n```json\n{\"status\": \"OK\", \"items\": [1, 2, 3]}\n```"
    data = factory._extract_json(text)
    assert data is not None
    assert data["status"] == "OK"
    assert data["items"] == [1, 2, 3]
