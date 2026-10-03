"""
test_cloud_local_circuits.py -- Test Suite for Cloud & Local Circuits in Vazus OS.

Verifies:
1. hub.get_system_status() includes j_space, sandbox, cloud_run, jules, local_npu.
2. hub.verify_all_circuits() verifies all 6 core circuits:
   - Local NPU / Hardware
   - J-Space Vector Index
   - Windows Sandbox Hardware Isolation
   - SQLite WAL Database & Backups
   - Cloud Sync
   - Dream Memory Consolidation
3. daemon_sidecar.run_single_heartbeat() executes cloud sync and returns cloud_synced flag.
4. J-Space indexer and WSB Sandbox status methods.
5. Jules Cloud VM dispatch and session inspection with graceful fallback.
"""

import os
import pytest
from unittest.mock import patch
from vazus_core.engine.unified_hub import VazusUnifiedHub
from vazus_core.workers.daemon_sidecar import run_single_heartbeat
from vazus_core.memory.j_space_tool_indexer import JSpaceToolIndexer
from vazus_core.sandbox.wsb_sandbox_controller import WSBSandboxController


def test_hub_system_status_contains_required_sections():
    """Verify hub.get_system_status() returns j_space, sandbox, cloud_run, jules, local_npu."""
    hub = VazusUnifiedHub()
    status = hub.get_system_status()

    assert isinstance(status, dict)
    assert "j_space" in status, "j_space section missing from get_system_status"
    assert "sandbox" in status, "sandbox section missing from get_system_status"
    assert "cloud_run" in status, "cloud_run section missing from get_system_status"
    assert "jules" in status, "jules section missing from get_system_status"
    assert "local_npu" in status, "local_npu section missing from get_system_status"

    # Validate j_space details
    j_space = status["j_space"]
    assert isinstance(j_space, dict)
    assert "table_status" in j_space
    assert "vectors_count" in j_space
    assert "indexed_tools" in j_space

    # Validate sandbox details
    sandbox = status["sandbox"]
    assert isinstance(sandbox, dict)
    assert "available" in sandbox
    assert "isolation" in sandbox
    assert "status" in sandbox


def test_hub_verify_all_circuits():
    """Verify hub.verify_all_circuits() returns status for all 6 circuits."""
    hub = VazusUnifiedHub()
    circuits_report = hub.verify_all_circuits()

    assert isinstance(circuits_report, dict)
    assert circuits_report.get("total_circuits") == 6
    assert "circuits" in circuits_report

    circuits = circuits_report["circuits"]
    expected_circuit_keys = [
        "local_npu",
        "j_space",
        "sandbox",
        "database_backup",
        "cloud_sync",
        "dream_consolidation",
    ]

    for key in expected_circuit_keys:
        assert key in circuits, f"Circuit '{key}' missing from circuits dictionary"
        c = circuits[key]
        assert "name" in c
        assert "status" in c
        assert "verified" in c
        assert isinstance(c["verified"], bool)

    # Also verify top-level convenience keys
    for key in expected_circuit_keys:
        assert key in circuits_report, f"Top-level circuit key '{key}' missing"

    assert circuits_report.get("verified_count", 0) >= 4, "At least 4 core circuits must be healthy in test sandbox"


def test_daemon_heartbeat_cloud_sync():
    """Verify daemon_sidecar.run_single_heartbeat() executes cloud sync and returns cloud_synced flag."""
    report = run_single_heartbeat()

    assert isinstance(report, dict)
    assert "cloud_synced" in report, "cloud_synced flag missing from heartbeat report"
    assert report["cloud_synced"] is True, "Heartbeat cloud sync should succeed"
    assert "j_space_status" in report, "j_space_status missing from heartbeat report"
    assert "npu_status" in report, "npu_status missing from heartbeat report"
    assert report["status"] == "HEALTHY"


def test_j_space_indexer_get_status():
    """Verify JSpaceToolIndexer.get_status() queries vectors and metadata tables."""
    indexer = JSpaceToolIndexer()
    status = indexer.get_status()

    assert isinstance(status, dict)
    assert status.get("table_status") in ("ONLINE", "EXISTS")
    assert status.get("vectors_count", 0) >= 0
    assert status.get("indexed_tools", 0) >= 0
    assert status.get("status") in ("ONLINE", "READY", "EMPTY")


def test_sandbox_controller_status():
    """Verify WSBSandboxController availability and status reporting."""
    available = WSBSandboxController.is_available()
    assert isinstance(available, bool)

    hub = VazusUnifiedHub()
    sb_status = hub.check_sandbox_status()
    assert sb_status["available"] == available
    assert "isolation" in sb_status
    if available:
        assert sb_status["isolation"] == "HARDWARE_APPCONTAINER"
        assert sb_status["status"] == "READY"


def test_jules_dispatch_graceful_fallback():
    """Verify hub.dispatch_to_jules returns graceful fallback when offline."""
    hub = VazusUnifiedHub()
    with patch.dict(os.environ, {"VAZUS_JULES_OFFLINE": "1"}):
        res = hub.dispatch_to_jules(prompt="Precommit check verification", source_id="vazus-test")
        assert isinstance(res, dict)
        assert res.get("fallback") is True
        assert res.get("dispatched") is False
        assert "reason" in res


def test_jules_get_sessions():
    """Verify hub.get_jules_sessions returns a list of sessions."""
    hub = VazusUnifiedHub()
    # 1. Mocked session list test
    with patch("vazus_core.workers.jules_client.JulesClient.list_sessions_async") as mock_list:
        from vazus_core.workers.jules_client import JulesSession
        fake_session = JulesSession(id="session-1", state="COMPLETED", title="Test Session")
        mock_list.return_value = {"fallback": False, "reason": None, "sessions": [fake_session]}
        sessions = hub.get_jules_sessions()
        assert isinstance(sessions, list)
        assert len(sessions) == 1
        assert sessions[0]["id"] == "session-1"

    # 2. Offline / fallback test without network latency
    with patch.dict(os.environ, {"VAZUS_JULES_OFFLINE": "1"}):
        offline_sessions = hub.get_jules_sessions()
        assert isinstance(offline_sessions, list)
