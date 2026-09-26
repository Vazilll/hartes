"""
tests.test_telemetry — Verification for CloudTelemetryBridge and Google Drive Sync.
"""

import pytest
import json
from pathlib import Path
from vazus_autonomous_harness.telemetry.cloud_bridge import CloudTelemetryBridge, SystemHealthReport


def test_collect_health():
    bridge = CloudTelemetryBridge()
    report = bridge.collect_health()

    assert isinstance(report, SystemHealthReport)
    assert report.status in ["OPTIMAL", "DEGRADED", "ALERT"]
    assert report.z3_hard_gate_ok is True
    assert report.z3_latency_ms >= 0.0
    assert report.total_skills >= 4
    assert "level_1" in report.skill_levels
    assert report.spark_action_required is False


def test_sync_to_local_and_drive(tmp_path):
    bridge = CloudTelemetryBridge(drive_root=tmp_path)
    report = bridge.collect_health()
    paths = bridge.sync_to_cloud(report)

    assert f"{tmp_path.name}_json" in paths
    json_path = paths[f"{tmp_path.name}_json"]
    assert json_path.exists()

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["z3_hard_gate_ok"] is True
    assert data["status"] == "OPTIMAL"


def test_alert_dispatch(tmp_path):
    bridge = CloudTelemetryBridge(drive_root=tmp_path)
    alerts = [{
        "title": "Simulated Invariant Divergence",
        "severity": "HIGH",
        "context": "SMT constraint rejected parameter delta",
        "trace": "z3.Z3Exception: unsat core triggered"
    }]
    report = bridge.collect_health(active_alerts=alerts)

    assert report.status == "ALERT"
    assert report.spark_action_required is True
    assert "[SPARK INTERVENTION REQUIRED]" in report.action_prompt_for_spark

    paths = bridge.sync_to_cloud(report)
    spark_md = paths[f"{tmp_path.name}_spark_actions"]
    assert spark_md.exists()

    content = spark_md.read_text(encoding="utf-8")
    assert "ATTENTION GEMINI SPARK" in content
    assert "Simulated Invariant Divergence" in content
