import pytest
import os
from vazus_core.evolution.closed_loop_orchestrator import ClosedLoopSelfImprover


def test_closed_loop_hotspot_discovery():
    improver = ClosedLoopSelfImprover()
    hotspots = improver.discover_hotspots(max_targets=5)
    assert isinstance(hotspots, list)
    if hotspots:
        first = hotspots[0]
        assert "file_path" in first
        assert "module_name" in first
        assert "suggestions_count" in first


def test_closed_loop_self_improvement_cycle():
    improver = ClosedLoopSelfImprover()
    result = improver.run_self_improvement_cycle(
        target_module="vazus_core.verification.smt_z3_verifier",
        generations=1
    )
    assert result["status"] == "SUCCESS"
    assert "evolution" in result
    assert result["evolution"]["status"] == "EVOLUTION_COMPLETED"
    assert result["evolution"]["final_fitness"] > 0.0
    assert len(result["evolution"]["history"]) >= 1
    assert "layer_reports" in result["evolution"]["history"][0]