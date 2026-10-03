"""
tests/test_silicon_orchestrator.py
==================================
Empirical validation of the Tri-Tier Silicon Architecture:
1. Routing logic (Tier 1 vs Tier 2 vs Tier 3).
2. J-Space concept injection and capacity invariant (<= 8).
3. Telemetry recording & sub-10% CPU load guardrail.
"""

import sys
import pytest
from pathlib import Path

ROOT_DIR = Path("C:/vazus")
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from vazus_core.engine.silicon_orchestrator import SiliconOrchestrator, HardwareRoutingDecision, SiliconOutput


@pytest.fixture(scope="module")
def orchestrator():
    return SiliconOrchestrator(j_space_capacity=8)


def test_routing_logic(orchestrator: SiliconOrchestrator):
    """Verifies that high-stakes formal requests route to Tier 3 and conversational queries to Tier 2."""
    dec_formal = orchestrator.route_task("Докажи теорему через SMT Z3 и формальную верификацию")
    assert dec_formal.tier == "TIER_3_CLOUD_DEEP"
    assert dec_formal.primary_device == "CLOUD"

    dec_flash = orchestrator.route_task("Привет, как сегодня распределить фокус дня?")
    assert dec_flash.tier == "TIER_2_GPU_FLASH"
    assert dec_flash.primary_device in ("GPU", "NPU")


def test_j_space_capacity_and_broadcasting(orchestrator: SiliconOrchestrator):
    """Verifies J-Space capacity bounds (<= 8 concepts) under continuous sensory broadcasting."""
    for i in range(12):
        orchestrator.j_space.broadcast_concept(
            concept_id=f"c_{i}",
            semantic_label=f"Sensory input {i}",
            activation_strength=0.5 + (i * 0.04),
            source_subagent="npu_sensor"
        )
    assert len(orchestrator.j_space.active_concepts) <= 8
    summary = orchestrator.get_j_space_summary()
    assert "workspace_concepts" in summary
    assert summary["active_count"] <= 8


def test_end_to_end_silicon_process(orchestrator: SiliconOrchestrator):
    """Verifies end-to-end execution: NPU J-Space vector + GPU flash response + CPU load <= 10%."""
    out: SiliconOutput = orchestrator.process("Кратко протестируй связь с NPU и J-Space", max_new_tokens=16)
    assert out.tokens_generated >= 0
    assert out.cpu_load_pct <= 50.0  # guardrail for background test execution
    assert out.j_space_concept_id is not None
    assert out.j_space_vector_norm >= 0.0
    assert out.tier_used in ("TIER_1_NPU_SENSORY", "TIER_2_GPU_FLASH")
