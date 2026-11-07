"""
tests.test_telemetry — Verification for CloudTelemetryBridge, Google Drive Sync, and Spark Directives.
"""

import json
from pathlib import Path
from vazus_autonomous_harness.telemetry.cloud_bridge import (
    CloudTelemetryBridge,
    SystemHealthReport,
    resolve_relevant_notebook,
    KNOWN_NOTEBOOKS,
)


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
    assert len(report.structured_directives) == 1

    paths = bridge.sync_to_cloud(report)
    spark_md = paths[f"{tmp_path.name}_spark_actions"]
    assert spark_md.exists()

    content = spark_md.read_text(encoding="utf-8")
    assert "ATTENTION GEMINI SPARK" in content
    assert "Simulated Invariant Divergence" in content
    assert "Target Grounded Knowledge Bases" in content


def test_resolve_relevant_notebook():
    nb_arch = resolve_relevant_notebook("SMT substrate invariant violation")
    assert nb_arch["id"] == KNOWN_NOTEBOOKS["architecture"]["id"]

    nb_math = resolve_relevant_notebook("calculus derivative error in boolean algebra")
    assert nb_math["id"] == KNOWN_NOTEBOOKS["math"]["id"]

    nb_skill = resolve_relevant_notebook("skill state cot token reduction error")
    assert nb_skill["id"] == KNOWN_NOTEBOOKS["mechanisms"]["id"]


def test_bidirectional_spark_queues(tmp_path):
    bridge = CloudTelemetryBridge(drive_root=tmp_path)
    alerts = [{
        "title": "Test Anomaly",
        "severity": "CRITICAL",
        "context": "Memory threshold exceeded in flywheel",
        "trace": "MemoryError"
    }]
    report = bridge.collect_health(active_alerts=alerts)
    bridge.sync_to_cloud(report)

    # Check spark_inbox created
    inbox = tmp_path / "spark_inbox"
    assert inbox.exists()
    inbox_files = list(inbox.glob("*.json"))
    assert len(inbox_files) == 1

    # Simulate Spark placing an RFC resolution in spark_outbox
    outbox = tmp_path / "spark_outbox"
    assert outbox.exists()
    mock_solution = {
        "directive_id": report.structured_directives[0]["directive_id"],
        "status": "RESOLVED",
        "resolution_doc_url": "https://docs.google.com/document/d/mock123",
        "rfc_summary": "Adjusted memory pooling limits in configuration",
    }
    with open(outbox / "response_001.json", "w", encoding="utf-8") as f:
        json.dump(mock_solution, f)

    # Poll responses
    responses = bridge.poll_spark_responses()
    assert len(responses) == 1
    assert responses[0]["status"] == "RESOLVED"
    assert "mock123" in responses[0]["resolution_doc_url"]
