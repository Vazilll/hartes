"""Tests for vazus.services.memory.anti_rot."""

from __future__ import annotations

import sys
from pathlib import Path

VAZUS_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(VAZUS_ROOT))

from services.memory.anti_rot import AntiRotContextDistiller


def test_anti_rot_ingestion_and_deduplication():
    distiller = AntiRotContextDistiller()
    distiller.ingest_entry("harnet", "RAM OverlayFS verified", salience=0.8)
    distiller.ingest_entry("harnet", "RAM OverlayFS verified", salience=1.2)  # Update salience

    briefing = distiller.distill_briefing("harnet")
    assert "RAM OverlayFS verified" in briefing
    assert len(distiller._entries) == 1
    assert distiller._entries[0]["salience"] == 1.2


def test_anti_rot_distill_briefing_ordering_and_limit():
    distiller = AntiRotContextDistiller()
    for i in range(20):
        distiller.ingest_entry("core", f"Fact {i}", salience=float(i))

    briefing = distiller.distill_briefing("core", max_bullets=3)
    lines = briefing.splitlines()
    assert len(lines) == 3
    assert "Fact 19" in lines[0]
    assert "Fact 18" in lines[1]
    assert "Fact 17" in lines[2]


def test_anti_rot_prune_superseded():
    distiller = AntiRotContextDistiller()
    distiller.ingest_entry("a", "Active fact", salience=1.0)
    distiller.ingest_entry("b", "Dead fact", salience=1.0)

    # Deactivate second
    distiller._entries[1]["active"] = False
    pruned = distiller.prune_superseded()
    assert pruned == 1
    assert len(distiller._entries) == 1
    assert distiller._entries[0]["content"] == "Active fact"
