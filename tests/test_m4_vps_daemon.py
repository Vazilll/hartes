"""
Unit tests for Milestone 4 (F10, F11, F12):
- F10: Lightweight Headless VPS Daemon (vazus_autonomous_harness/daemon/vps_daemon.py)
- F11: Dual Setup Targets & Systemd Service (setup_vps_target1.sh, setup_orangepi_target2.sh, vazus-flywheel.service)
- F12: OpenColab Asynchronous Queue Bridge (vazus_autonomous_harness/daemon/colab_bridge.py)
"""

import json
import time
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

import httpx

from vazus_autonomous_harness.daemon.vps_daemon import (
    VpsDaemon,
    DEFAULT_VPS_IP,
    DEFAULT_MEMORY_LIMIT_MB,
    DEFAULT_MEMORY_WARNING_MB,
)
from vazus_autonomous_harness.daemon.colab_bridge import (
    ColabBridge,
)


@pytest.fixture
def temp_colab_queue(tmp_path):
    queue_dir = tmp_path / "colab_queue"
    queue_dir.mkdir(parents=True, exist_ok=True)
    return queue_dir


@pytest.fixture
def temp_config_file(tmp_path):
    cfg_file = tmp_path / "test_daemon.env"
    cfg_file.write_text(
        "VAZUS_VPS_IP=157.228.174.15\n"
        "MEMORY_LIMIT_MB=200.0\n"
        "MEMORY_WARNING_MB=150.0\n"
        "NODE_TTL_SEC=60.0\n"
        "GITHUB_REPOSITORY=Vazilll/hartes\n",
        encoding="utf-8",
    )
    return str(cfg_file)


# ==============================================================================
# F12: OpenColab Bridge Tests
# ==============================================================================

class TestColabBridge:
    def test_colab_bridge_initialization(self, temp_colab_queue):
        bridge = ColabBridge(queue_root=temp_colab_queue)
        assert bridge.inbox_dir.exists()
        assert bridge.active_dir.exists()
        assert bridge.outbox_dir.exists()
        assert bridge.root == temp_colab_queue

    def test_colab_bridge_submit_job(self, temp_colab_queue):
        bridge = ColabBridge(queue_root=temp_colab_queue)
        job_id = bridge.submit_job(
            task_type="SMT_VERIFICATION",
            code="import z3; s = z3.Solver()",
            metadata={"priority": "HIGH"},
        )
        assert isinstance(job_id, str)
        assert len(job_id) > 0

        # Verify manifest in inbox
        pending = bridge.list_pending_jobs()
        assert len(pending) == 1
        assert job_id in pending[0]

        inbox_file = bridge.inbox_dir / f"task_{job_id}.json"
        assert inbox_file.exists()
        manifest_data = json.loads(inbox_file.read_text(encoding="utf-8"))
        assert manifest_data["job_id"] == job_id
        assert manifest_data["task_type"] == "SMT_VERIFICATION"
        assert manifest_data["status"] == "PENDING"
        assert manifest_data["metadata"]["priority"] == "HIGH"

    def test_colab_bridge_poll_result_before_completion(self, temp_colab_queue):
        bridge = ColabBridge(queue_root=temp_colab_queue)
        job_id = bridge.submit_job("TEST", "print(1)")
        result = bridge.poll_result(job_id)
        assert result is None

    def test_colab_bridge_claim_and_complete_lifecycle(self, temp_colab_queue):
        bridge = ColabBridge(queue_root=temp_colab_queue)
        job_id = bridge.submit_job("MODEL_TUNE", "train_model()")

        # 1. Colab worker claims job
        claimed = bridge.claim_job(worker_id="colab_a100_node")
        assert claimed is not None
        assert claimed.job_id == job_id
        assert claimed.status == "RUNNING"
        assert claimed.worker_id == "colab_a100_node"

        # Verify file moved from inbox to active
        assert len(bridge.list_pending_jobs()) == 0
        assert len(bridge.list_active_jobs()) == 1

        # 2. Polling before completion is still None
        assert bridge.poll_result(job_id) is None

        # 3. Colab worker completes job
        result_payload = {"accuracy": 0.985, "epochs": 10}
        comp_res = bridge.complete_job(
            job_id=job_id,
            status="SUCCESS",
            result_data=result_payload,
            execution_time_sec=14.2,
        )
        assert comp_res.job_id == job_id
        assert comp_res.status == "SUCCESS"

        # Verify active directory cleaned and outbox contains result
        assert len(bridge.list_active_jobs()) == 0
        assert len(bridge.list_completed_jobs()) == 1

        # 4. Polling now returns the result dict
        polled = bridge.poll_result(job_id)
        assert polled is not None
        assert polled["job_id"] == job_id
        assert polled["status"] == "SUCCESS"
        assert polled["result_data"]["accuracy"] == 0.985

    def test_colab_bridge_keepalive_mechanism(self, temp_colab_queue):
        bridge = ColabBridge(queue_root=temp_colab_queue)

        # Initially, keepalive does not exist
        initial_status = bridge.get_keepalive_status()
        assert initial_status["alive"] is False

        # Worker emits keepalive heartbeat
        ts = bridge.update_keepalive(worker_id="colab_t4_gpu", gpu_info={"vram_gb": 16})
        assert ts > 0

        # Status is now alive
        status = bridge.get_keepalive_status(timeout_seconds=60.0)
        assert status["alive"] is True
        assert status["worker_id"] == "colab_t4_gpu"
        assert status["gpu_info"]["vram_gb"] == 16
        assert status["age_seconds"] >= 0.0

        # Simulated expiration
        status_expired = bridge.get_keepalive_status(timeout_seconds=0.0)
        assert status_expired["alive"] is False


# ==============================================================================
# F10: Lightweight Headless VPS Daemon Tests
# ==============================================================================

class TestVpsDaemon:
    def test_daemon_initialization_defaults(self, temp_colab_queue):
        daemon = VpsDaemon()
        assert daemon.vps_ip == DEFAULT_VPS_IP
        assert daemon.memory_limit_mb == DEFAULT_MEMORY_LIMIT_MB
        assert daemon.memory_warning_mb == DEFAULT_MEMORY_WARNING_MB
        assert daemon.tick_count == 0
        assert daemon.colab_bridge is not None

    def test_daemon_initialization_custom_config(self, temp_config_file, temp_colab_queue):
        daemon = VpsDaemon(config_path=temp_config_file)
        assert daemon.vps_ip == "157.228.174.15"
        assert daemon.node_ttl_sec == 60.0

    def test_daemon_node_registration_and_heartbeat(self, temp_colab_queue):
        daemon = VpsDaemon()
        daemon.colab_bridge = ColabBridge(queue_root=temp_colab_queue)

        # Register Tier 1.5 Edge node
        ok = daemon.register_node(
            node_id="orangepi_01",
            tier="Tier1_5_Edge",
            capabilities=["SMT_Z3", "ARM64_SOLVER"],
            ttl_seconds=2.0,
        )
        assert ok is True

        # Register Tier 2 Laptop node
        ok2 = daemon.register_node(
            node_id="laptop_01",
            tier="Tier2_Laptop",
            capabilities=["GPU", "NPU", "AGY_CLI"],
            ttl_seconds=2.0,
        )
        assert ok2 is True

        active = daemon.get_active_nodes()
        assert len(active) == 2
        node_ids = {n["node_id"] for n in active}
        assert "orangepi_01" in node_ids
        assert "laptop_01" in node_ids

        # Heartbeat node
        hb_ok = daemon.heartbeat_node("orangepi_01", metadata={"cpu": 15.2})
        assert hb_ok is True
        assert daemon.heartbeat_node("non_existent_node") is False

    def test_daemon_node_expiry_and_pruning(self, temp_colab_queue):
        daemon = VpsDaemon()
        daemon.colab_bridge = ColabBridge(queue_root=temp_colab_queue)

        # Register node with short TTL
        daemon.register_node("ephemeral_node", "Tier2_Laptop", ["REPL"], ttl_seconds=0.05)
        assert len(daemon.get_active_nodes()) == 1

        # Wait for TTL expiry
        time.sleep(0.08)
        pruned = daemon.prune_expired_nodes()
        assert "ephemeral_node" in pruned
        assert len(daemon.get_active_nodes()) == 0

    def test_daemon_memory_watchdog(self):
        daemon = VpsDaemon()
        rss = daemon.get_memory_usage_mb()
        assert isinstance(rss, float)
        assert rss > 0.0

        # Test memory limit thresholds and GC triggering
        daemon.memory_warning_mb = 1.0  # Force lower than current RSS
        tick_res = daemon.tick()
        assert tick_res["memory"]["gc_triggered"] is True

    def test_daemon_tick_lifecycle(self, temp_colab_queue):
        daemon = VpsDaemon()
        daemon.colab_bridge = ColabBridge(queue_root=temp_colab_queue)

        daemon.register_node("edge_node", "Tier1_5_Edge", ["SMT_Z3"], ttl_seconds=60.0)
        job_id = daemon.colab_bridge.submit_job("TEST_JOB", "pass")
        assert job_id is not None

        res = daemon.tick()
        assert res["tick_id"] == 1
        assert res["vps_ip"] == DEFAULT_VPS_IP
        assert "rss_mb" in res["memory"]
        assert res["nodes"]["active_count"] == 1
        assert res["nodes"]["has_arm64_smt_node"] is True
        assert res["colab_queue"]["pending_count"] == 1
        assert res["colab_queue"]["worker_alive"] is False

    def test_daemon_dispatch_cloud_job_github_success(self):
        daemon = VpsDaemon()
        payload = {"ref": "main", "inputs": {"rounds": "2"}}

        mock_resp = MagicMock()
        mock_resp.status_code = 204

        with patch("httpx.Client.post", return_value=mock_resp):
            success = daemon.dispatch_cloud_job("cloud_mega_lab.yml", payload)
            assert success is True
            assert len(daemon.dispatched_jobs_history) == 1
            assert daemon.dispatched_jobs_history[0]["success"] is True

    def test_daemon_dispatch_cloud_job_github_failure(self):
        daemon = VpsDaemon()
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.text = "Not Found"

        with patch("httpx.Client.post", return_value=mock_resp):
            success = daemon.dispatch_cloud_job("missing_workflow.yml", {})
            assert success is False

    def test_daemon_dispatch_cloud_job_jules_success(self):
        daemon = VpsDaemon()
        payload = {"prompt": "Run SMT formal proof gate", "title": "Jules Sprint"}

        mock_resp = MagicMock()
        mock_resp.status_code = 201

        with patch("httpx.Client.post", return_value=mock_resp):
            success = daemon.dispatch_cloud_job("jules", payload)
            assert success is True
            assert daemon.dispatched_jobs_history[-1]["target"] == "google_jules"

    def test_daemon_dispatch_cloud_job_network_error(self):
        daemon = VpsDaemon()
        with patch("httpx.Client.post", side_effect=httpx.ConnectError("Connection refused")):
            success = daemon.dispatch_cloud_job("cloud_mega_lab.yml", {})
            assert success is False
            assert daemon.dispatched_jobs_history[-1]["success"] is False

    @pytest.mark.anyio
    async def test_daemon_run_loop_bounded_ticks(self, temp_colab_queue):
        daemon = VpsDaemon()
        daemon.colab_bridge = ColabBridge(queue_root=temp_colab_queue)

        ticks = await daemon.run_loop(interval_seconds=0.01, max_ticks=3)
        assert len(ticks) == 3
        assert daemon.tick_count == 3


    def test_colab_bridge_corrupted_result_handling(self, temp_colab_queue):
        bridge = ColabBridge(queue_root=temp_colab_queue)
        job_id = bridge.submit_job("TEST", "code")
        # Write corrupted JSON to outbox
        corrupted_file = bridge.outbox_dir / f"result_{job_id}.json"
        corrupted_file.write_text("{invalid json", encoding="utf-8")
        assert bridge.poll_result(job_id) is None

    def test_colab_bridge_claim_nonexistent_job(self, temp_colab_queue):
        bridge = ColabBridge(queue_root=temp_colab_queue)
        assert bridge.claim_job("non_existent_uuid") is None

    def test_colab_bridge_multiple_jobs_order(self, temp_colab_queue):
        bridge = ColabBridge(queue_root=temp_colab_queue)
        j1 = bridge.submit_job("TASK1", "code1")
        time.sleep(0.02)
        j2 = bridge.submit_job("TASK2", "code2")

        c1 = bridge.claim_job()
        assert c1.job_id == j1
        c2 = bridge.claim_job()
        assert c2.job_id == j2

    def test_colab_bridge_keepalive_corrupted(self, temp_colab_queue):
        bridge = ColabBridge(queue_root=temp_colab_queue)
        bridge.keepalive_file.write_text("corrupted json", encoding="utf-8")
        st = bridge.get_keepalive_status()
        assert st["alive"] is False

    def test_daemon_critical_memory_status(self):
        daemon = VpsDaemon()
        daemon.memory_warning_mb = 1.0
        daemon.memory_limit_mb = 2.0  # Force lower than current RSS
        res = daemon.tick()
        assert res["memory"]["status"] == "CRITICAL_EXCEEDS_BUDGET"

    def test_daemon_unregistered_node_heartbeat(self):
        daemon = VpsDaemon()
        assert daemon.heartbeat_node("ghost_node") is False


# ==============================================================================
# F11: Dual Setup Targets & Systemd Unit Verification Tests
# ==============================================================================

class TestDeploymentArtifacts:
    def test_setup_vps_target1_script_integrity(self):
        script_path = Path(__file__).resolve().parent.parent / "vazus_autonomous_harness" / "daemon" / "setup_vps_target1.sh"
        assert script_path.exists(), "setup_vps_target1.sh must exist"

        content = script_path.read_text(encoding="utf-8")
        assert content.startswith("#!/bin/bash"), "Must contain bash shebang"
        assert "set -e" in content, "Must enforce fail-closed set -e"
        assert "chmod 0600" in content, "Must enforce 0600 permissions on env file"
        assert "/etc/vazus/flywheel.env" in content, "Must reference flywheel.env"
        assert "MemoryMax=200M" in content, "Must enforce MemoryMax=200M limit"
        assert "MemoryHigh=160M" in content, "Must enforce MemoryHigh=160M reclaim limit"
        assert "157.228.174.15" in content, "Must target VPS IP 157.228.174.15"

    def test_setup_orangepi_target2_script_integrity(self):
        script_path = Path(__file__).resolve().parent.parent / "vazus_autonomous_harness" / "daemon" / "setup_orangepi_target2.sh"
        assert script_path.exists(), "setup_orangepi_target2.sh must exist"

        content = script_path.read_text(encoding="utf-8")
        assert content.startswith("#!/bin/bash"), "Must contain bash shebang"
        assert "set -e" in content, "Must enforce fail-closed set -e"
        assert "chmod 0600" in content, "Must enforce 0600 permissions on edge.env"
        assert "aarch64" in content or "arm64" in content, "Must verify ARM64 architecture"
        assert "python3-z3" in content or "z3" in content, "Must install native Z3 solver"
        assert "MemoryMax=2500M" in content, "Must configure edge cgroup limit"

    def test_systemd_service_unit_compliance(self):
        service_path = Path(__file__).resolve().parent.parent / "vazus_autonomous_harness" / "daemon" / "vazus-flywheel.service"
        assert service_path.exists(), "vazus-flywheel.service must exist"

        content = service_path.read_text(encoding="utf-8")
        assert "[Unit]" in content
        assert "[Service]" in content
        assert "[Install]" in content
        assert "MemoryMax=200M" in content
        assert "MemoryHigh=160M" in content
        assert "MemorySwapMax=50M" in content
        assert "EnvironmentFile=/etc/vazus/flywheel.env" in content
        assert "ProtectSystem=strict" in content
        assert "Restart=always" in content

    def test_zero_plaintext_credentials_in_daemon_package(self):
        """Scans daemon package to verify absolute absence of hardcoded secrets."""
        daemon_dir = Path(__file__).resolve().parent.parent / "vazus_autonomous_harness" / "daemon"
        forbidden_substrings = [
            "ghp_",
            "github_pat_",
            "AIzaSy",
            "sk-",
            "AKIA",
            "BEGIN RSA PRIVATE KEY",
            "BEGIN OPENSSH PRIVATE KEY",
        ]

        for file_path in daemon_dir.glob("*"):
            if file_path.is_file() and not file_path.name.endswith(".pyc"):
                text = file_path.read_text(encoding="utf-8", errors="ignore")
                for secret_marker in forbidden_substrings:
                    assert secret_marker not in text, f"Found forbidden secret marker '{secret_marker}' in {file_path.name}"
