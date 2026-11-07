"""
tests/test_m5_topology.py -- Comprehensive Unit Tests for Milestone 5 (F13 & F14).

Covers:
- F13: Asymmetric 4-Tier Topology Coordinator (vazus_autonomous_harness/topology/coordinator.py)
  * NodeRegistration dataclass validation, lifecycle, and serialization
  * TopologyCoordinator registration, heartbeat renewal, and pruning
  * 4-Tier priority routing (Tier 2 Laptop > Tier 1.5 Edge > Tier 1 Cloud > Tier 0 VPS)
  * Dynamic failover upon lease expiration
  * Multi-capability task matching
  * Safe git synchronization with conflict detection
  * Topology summary and telemetry
- F14: Laptop Power Multiplier & Lease Manager (vazus_autonomous_harness/topology/laptop_node.py)
  * 10-minute TTL lease management (LaptopLeaseManager)
  * Sub-second graceful failover and sleep/lid-close simulation
  * Git fast-forward merge protocol preventing split-brain states (GitFastForwardSync)
  * Subprocess-isolated Local REPL Sandbox (LocalReplSandbox)
  * Antigravity CLI Quota Offloading (AgyQuotaOffloader)
  * Unified LaptopNode facade
"""

import time
import subprocess

import pytest


class DummySubprocessRunner:
    """Native deterministic subprocess runner test double."""

    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

    def __call__(self, cmd, *args, **kwargs) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=self.returncode,
            stdout=self.stdout,
            stderr=self.stderr,
        )

from vazus_autonomous_harness.topology.coordinator import (
    NodeRegistration,
    TopologyCoordinator,
    TIER_0_VPS,
    TIER_1_CLOUD,
    TIER_1_5_EDGE,
    TIER_2_LAPTOP,
    CAPABILITY_SMT_Z3,
    CAPABILITY_GPU,
    CAPABILITY_NPU,
    CAPABILITY_AGY_CLI,
    CAPABILITY_REPL,
    CAPABILITY_HEAVY_PYTEST,
    CAPABILITY_ORCHESTRATE,
    CAPABILITY_CRON,
    CAPABILITY_GIT_SYNC,
)
from vazus_autonomous_harness.topology.laptop_node import (
    LaptopNode,
    LaptopLeaseManager,
    GitFastForwardSync,
    LocalReplSandbox,
    AgyQuotaOffloader,
    DEFAULT_LAPTOP_NODE_ID,
)


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture
def coordinator():
    """Provides a fresh TopologyCoordinator instance."""
    return TopologyCoordinator()


@pytest.fixture
def sample_4tier_nodes():
    """Provides standard registrations across all 4 tiers."""
    now = time.time()
    return {
        "vps": NodeRegistration(
            node_id="vps_01",
            tier=TIER_0_VPS,
            capabilities=[CAPABILITY_ORCHESTRATE, CAPABILITY_CRON],
            lease_expires_at=now + 3600.0,
        ),
        "cloud": NodeRegistration(
            node_id="cloud_runner_01",
            tier=TIER_1_CLOUD,
            capabilities=[CAPABILITY_HEAVY_PYTEST, "JULES_VM"],
            lease_expires_at=now + 3600.0,
        ),
        "edge": NodeRegistration(
            node_id="orangepi_edge_01",
            tier=TIER_1_5_EDGE,
            capabilities=[CAPABILITY_SMT_Z3, CAPABILITY_GPU, CAPABILITY_GIT_SYNC],
            lease_expires_at=now + 3600.0,
        ),
        "laptop": NodeRegistration(
            node_id="laptop_win11_01",
            tier=TIER_2_LAPTOP,
            capabilities=[CAPABILITY_GPU, CAPABILITY_NPU, CAPABILITY_AGY_CLI, CAPABILITY_REPL],
            lease_expires_at=now + 600.0,
        ),
    }


# ==============================================================================
# 1. F13: NodeRegistration Dataclass Tests
# ==============================================================================

class TestNodeRegistration:
    def test_node_registration_fields(self):
        now = time.time()
        node = NodeRegistration(
            node_id="test_node_01",
            tier=TIER_2_LAPTOP,
            capabilities=["GPU", "REPL"],
            lease_expires_at=now + 600.0,
            metadata={"arch": "x86_64"},
        )
        assert node.node_id == "test_node_01"
        assert node.tier == TIER_2_LAPTOP
        assert node.capabilities == ["GPU", "REPL"]
        assert node.lease_expires_at == now + 600.0
        assert node.metadata == {"arch": "x86_64"}
        assert node.registered_at > 0.0

    def test_node_registration_is_active(self):
        now = time.time()
        active_node = NodeRegistration("active_1", TIER_2_LAPTOP, ["GPU"], now + 100.0)
        expired_node = NodeRegistration("expired_1", TIER_2_LAPTOP, ["GPU"], now - 10.0)

        assert active_node.is_active(current_time=now) is True
        assert expired_node.is_active(current_time=now) is False

    def test_node_registration_remaining_lease_seconds(self):
        now = time.time()
        node = NodeRegistration("node_lease", TIER_1_5_EDGE, ["SMT_Z3"], now + 250.0)
        assert pytest.approx(node.remaining_lease_seconds(current_time=now), rel=1e-2) == 250.0

        expired = NodeRegistration("node_exp", TIER_1_5_EDGE, ["SMT_Z3"], now - 50.0)
        assert expired.remaining_lease_seconds(current_time=now) == 0.0

    def test_node_registration_has_capability(self):
        node = NodeRegistration("cap_node", TIER_0_VPS, ["CRON", "ORCHESTRATE"], time.time() + 100)
        assert node.has_capability("CRON") is True
        assert node.has_capability("GPU") is False

    def test_node_registration_serialization(self):
        node = NodeRegistration("ser_node", TIER_1_CLOUD, ["HEAVY_PYTEST"], 1000.0)
        d = node.to_dict()
        assert d["node_id"] == "ser_node"
        assert d["tier"] == TIER_1_CLOUD
        assert d["capabilities"] == ["HEAVY_PYTEST"]
        assert d["lease_expires_at"] == 1000.0


# ==============================================================================
# 2. F13: TopologyCoordinator Core Tests
# ==============================================================================

class TestTopologyCoordinator:
    def test_register_single_node(self, coordinator):
        now = time.time()
        node = NodeRegistration("vps_0", TIER_0_VPS, ["CRON"], now + 3600)
        assert coordinator.register_node(node) is True
        assert "vps_0" in coordinator.nodes
        assert coordinator.nodes["vps_0"].tier == TIER_0_VPS

    def test_register_invalid_inputs(self, coordinator):
        assert coordinator.register_node("not_a_node") is False  # type: ignore
        assert coordinator.register_node(NodeRegistration("", TIER_0_VPS, [], time.time() + 10)) is False

    def test_update_duplicate_registration(self, coordinator):
        now = time.time()
        coord = coordinator
        node_v1 = NodeRegistration("node_dup", TIER_2_LAPTOP, ["GPU"], now + 100)
        coord.register_node(node_v1)
        assert len(coord.nodes) == 1

        node_v2 = NodeRegistration("node_dup", TIER_2_LAPTOP, ["GPU", "NPU", "AGY_CLI"], now + 600)
        coord.register_node(node_v2)
        assert len(coord.nodes) == 1
        assert "NPU" in coord.nodes["node_dup"].capabilities
        assert coord.nodes["node_dup"].lease_expires_at == now + 600

    def test_heartbeat_extends_lease(self, coordinator):
        now = time.time()
        node = NodeRegistration("laptop_hb", TIER_2_LAPTOP, ["GPU"], now + 30)
        coordinator.register_node(node)

        # Heartbeat extends by 600s
        success = coordinator.heartbeat_node("laptop_hb", extension_seconds=600.0)
        assert success is True
        assert coordinator.nodes["laptop_hb"].lease_expires_at >= now + 590.0

    def test_heartbeat_unregistered_node(self, coordinator):
        assert coordinator.heartbeat_node("ghost_node") is False

    def test_unregister_node(self, coordinator):
        node = NodeRegistration("temp_node", TIER_0_VPS, ["CRON"], time.time() + 100)
        coordinator.register_node(node)
        assert coordinator.unregister_node("temp_node") is True
        assert "temp_node" not in coordinator.nodes
        assert coordinator.unregister_node("temp_node") is False

    def test_prune_expired_nodes(self, coordinator):
        now = time.time()
        coordinator.register_node(NodeRegistration("active", TIER_2_LAPTOP, ["GPU"], now + 200))
        coordinator.register_node(NodeRegistration("expired_1", TIER_1_5_EDGE, ["SMT_Z3"], now - 10))
        coordinator.register_node(NodeRegistration("expired_2", TIER_0_VPS, ["CRON"], now - 100))

        pruned = coordinator.prune_expired_nodes(current_time=now)
        assert "expired_1" in pruned
        assert "expired_2" in pruned
        assert "active" not in pruned
        assert len(coordinator.nodes) == 1
        assert "active" in coordinator.nodes


# ==============================================================================
# 3. F13: 4-Tier Hierarchy & Capability-Based Routing
# ==============================================================================

class TestTopologyRouting:
    def test_opportunistic_laptop_priority(self, coordinator, sample_4tier_nodes):
        """When Laptop (Tier 2) is active, GPU requests route to Laptop over Orange Pi (Tier 1.5)."""
        for n in sample_4tier_nodes.values():
            coordinator.register_node(n)

        best_worker = coordinator.get_best_worker_for_task("GPU")
        assert best_worker is not None
        assert best_worker.node_id == "laptop_win11_01"
        assert best_worker.tier == TIER_2_LAPTOP

    def test_failover_when_laptop_offline(self, coordinator, sample_4tier_nodes):
        """When Laptop disconnects or lease expires, GPU tasks gracefully fail over to Orange Pi."""
        for n in sample_4tier_nodes.values():
            coordinator.register_node(n)

        # Simulate laptop going offline (lease expired)
        coordinator.nodes["laptop_win11_01"].lease_expires_at = time.time() - 1.0

        best_worker = coordinator.get_best_worker_for_task("GPU")
        assert best_worker is not None
        assert best_worker.node_id == "orangepi_edge_01"
        assert best_worker.tier == TIER_1_5_EDGE

    def test_smt_z3_routes_to_edge_node(self, coordinator, sample_4tier_nodes):
        """SMT formal proofs route to Orange Pi 4 Pro 6GB ARM64 edge node."""
        for n in sample_4tier_nodes.values():
            coordinator.register_node(n)

        worker = coordinator.get_best_worker_for_task(CAPABILITY_SMT_Z3)
        assert worker is not None
        assert worker.node_id == "orangepi_edge_01"
        assert worker.tier == TIER_1_5_EDGE

    def test_heavy_pytest_routes_to_cloud_plane(self, coordinator, sample_4tier_nodes):
        """Heavy 16GB Pytest matrix routes to Tier 1 Cloud runner."""
        for n in sample_4tier_nodes.values():
            coordinator.register_node(n)

        worker = coordinator.get_best_worker_for_task(CAPABILITY_HEAVY_PYTEST)
        assert worker is not None
        assert worker.node_id == "cloud_runner_01"
        assert worker.tier == TIER_1_CLOUD

    def test_cron_routes_to_vps_control_plane(self, coordinator, sample_4tier_nodes):
        """Orchestration/cron tasks route to Tier 0 VPS."""
        for n in sample_4tier_nodes.values():
            coordinator.register_node(n)

        worker = coordinator.get_best_worker_for_task(CAPABILITY_CRON)
        assert worker is not None
        assert worker.node_id == "vps_01"
        assert worker.tier == TIER_0_VPS

    def test_no_worker_has_capability(self, coordinator, sample_4tier_nodes):
        for n in sample_4tier_nodes.values():
            coordinator.register_node(n)

        assert coordinator.get_best_worker_for_task("QUANTUM_ANNEALING") is None

    def test_all_workers_expired(self, coordinator):
        past = time.time() - 100
        coordinator.register_node(NodeRegistration("n1", TIER_2_LAPTOP, ["GPU"], past))
        coordinator.register_node(NodeRegistration("n2", TIER_1_5_EDGE, ["GPU"], past))
        assert coordinator.get_best_worker_for_task("GPU") is None

    def test_multi_capability_task_routing(self, coordinator):
        now = time.time()
        # Node with partial caps
        coordinator.register_node(NodeRegistration("laptop_partial", TIER_2_LAPTOP, ["GPU"], now + 600))
        # Node with all required caps
        coordinator.register_node(NodeRegistration("laptop_full", TIER_2_LAPTOP, ["GPU", "AGY_CLI", "REPL"], now + 600))

        matched = coordinator.route_multi_capability_task(["GPU", "AGY_CLI", "REPL"])
        assert matched is not None
        assert matched.node_id == "laptop_full"

        # Capability not present on any node
        unmatched = coordinator.route_multi_capability_task(["GPU", "QUANTUM_SOLVER"])
        assert unmatched is None


# ==============================================================================
# 4. F13: Topology Summary & Telemetry
# ==============================================================================

class TestTopologySummary:
    def test_topology_summary_generation(self, coordinator, sample_4tier_nodes):
        for n in sample_4tier_nodes.values():
            coordinator.register_node(n)

        summary = coordinator.get_topology_summary()
        assert summary["total_registered"] == 4
        assert summary["total_active"] == 4
        assert summary["laptop_online"] is True
        assert summary["edge_online"] is True
        assert summary["cloud_online"] is True
        assert summary["vps_online"] is True
        assert summary["tier_distribution"][TIER_2_LAPTOP] == 1
        assert CAPABILITY_GPU in summary["available_capabilities"]


# ==============================================================================
# 5. F14: Laptop Lease Manager Tests
# ==============================================================================

class TestLaptopLeaseManager:
    def test_lease_manager_initialization(self):
        mgr = LaptopLeaseManager(node_id="laptop_custom", ttl_seconds=600.0)
        assert mgr.node_id == "laptop_custom"
        assert mgr.ttl_seconds == 600.0
        assert mgr.tier == TIER_2_LAPTOP
        assert mgr.is_registered is False

    def test_lease_manager_dynamic_registration(self, coordinator):
        mgr = LaptopLeaseManager()
        reg = mgr.register(coordinator, ttl_seconds=600.0)
        assert reg.node_id == DEFAULT_LAPTOP_NODE_ID
        assert reg.tier == TIER_2_LAPTOP
        assert reg.lease_expires_at > time.time() + 500
        assert mgr.is_registered is True
        assert coordinator.nodes[DEFAULT_LAPTOP_NODE_ID] is not None

    def test_lease_manager_heartbeat(self, coordinator):
        mgr = LaptopLeaseManager()
        mgr.register(coordinator, ttl_seconds=600.0)
        now = time.time()
        assert mgr.heartbeat(coordinator, extension_seconds=600.0) is True
        assert coordinator.nodes[DEFAULT_LAPTOP_NODE_ID].lease_expires_at >= now + 590.0

    def test_lease_manager_graceful_disconnect_triggers_failover(self, coordinator):
        mgr = LaptopLeaseManager()
        mgr.register(coordinator, ttl_seconds=600.0)

        # Register fallback edge node
        edge = NodeRegistration("edge_backup", TIER_1_5_EDGE, [CAPABILITY_GPU], time.time() + 3600)
        coordinator.register_node(edge)

        # While laptop is active, GPU routes to laptop
        assert coordinator.get_best_worker_for_task("GPU").node_id == DEFAULT_LAPTOP_NODE_ID

        # Graceful disconnect expires lease immediately
        assert mgr.disconnect(coordinator, graceful=True) is True
        assert mgr.is_registered is False

        # Instantaneous sub-second failover to edge backup
        best = coordinator.get_best_worker_for_task("GPU")
        assert best is not None
        assert best.node_id == "edge_backup"

    def test_simulate_power_off_or_lid_close(self, coordinator):
        mgr = LaptopLeaseManager()
        mgr.register(coordinator, ttl_seconds=600.0)
        assert mgr.is_lease_active() is True

        mgr.simulate_power_off_or_lid_close(coordinator)
        assert mgr.is_lease_active() is False
        assert coordinator.get_best_worker_for_task(CAPABILITY_AGY_CLI) is None


# ==============================================================================
# 6. F14: Git Fast-Forward Merge Protocol (Split-Brain Prevention)
# ==============================================================================

class TestGitFastForwardSync:
    def test_git_repository_verification(self):
        sync = GitFastForwardSync()
        assert sync.is_git_repository(".") is True
        assert sync.is_git_repository("C:\\Windows") is False

    def test_working_tree_cleanliness_check(self):
        sync = GitFastForwardSync()
        is_clean, details = sync.check_working_tree_clean(".")
        assert isinstance(is_clean, bool)
        assert isinstance(details, list)

    def test_safe_fast_forward_sync_prevents_split_brain(self):
        sync = GitFastForwardSync()
        result = sync.safe_fast_forward_sync()
        assert result["success"] is True
        assert result["split_brain_prevented"] is True

    def test_conflict_detection_prevents_sync(self, monkeypatch):
        sync = GitFastForwardSync()
        monkeypatch.setattr(sync, "is_git_repository", lambda repo_path=None: True)

        conflict_runner = DummySubprocessRunner(
            returncode=0,
            stdout="UU file_in_conflict.py\nM modified.py\n",
            stderr="",
        )
        monkeypatch.setattr(subprocess, "run", conflict_runner)

        is_clean, conflicts = sync.check_working_tree_clean(".")
        assert is_clean is False
        assert "UU file_in_conflict.py" in conflicts

        res = sync.safe_fast_forward_sync()
        assert res["success"] is False
        assert res["split_brain_prevented"] is True
        assert "Active merge conflicts detected" in res["reason"]

    def test_divergence_non_fast_forward_rejection(self, monkeypatch):
        sync = GitFastForwardSync()
        monkeypatch.setattr(sync, "is_git_repository", lambda repo_path=None: True)
        monkeypatch.setattr(sync, "check_working_tree_clean", lambda repo_path=None: (True, []))
        monkeypatch.setattr(sync, "can_fast_forward", lambda target_ref, base_ref="HEAD", repo_path=None: (False, "HEAD has diverged"))

        res = sync.safe_fast_forward_sync(remote_ref="origin/vazus-dev")
        assert res["success"] is False
        assert res["split_brain_prevented"] is True
        assert "Non-fast-forward divergence detected" in res["reason"]


# ==============================================================================
# 7. F14: Local REPL Sandbox Tests
# ==============================================================================

class TestLocalReplSandbox:
    def test_repl_basic_execution(self):
        repl = LocalReplSandbox()
        code = "print(21 * 2)"
        res = repl.execute_code(code)
        assert res.success is True
        assert res.exit_code == 0
        assert res.stdout.strip() == "42"
        assert res.execution_time_ms >= 0.0
        assert res.timed_out is False

    def test_repl_complex_calculation_and_json(self):
        repl = LocalReplSandbox()
        code = """
import json
data = {"status": "ok", "squares": [x*x for x in range(5)]}
print(json.dumps(data))
"""
        res = repl.execute_code(code)
        assert res.success is True
        assert '"squares": [0, 1, 4, 9, 16]' in res.stdout

    def test_repl_syntax_error_capture(self):
        repl = LocalReplSandbox()
        bad_code = "def syntax_err(:"
        res = repl.execute_code(bad_code)
        assert res.success is False
        assert res.exit_code != 0
        assert "SyntaxError" in res.stderr

    def test_repl_runtime_exception_capture(self):
        repl = LocalReplSandbox()
        bad_code = "1 / 0"
        res = repl.execute_code(bad_code)
        assert res.success is False
        assert res.exit_code != 0
        assert "ZeroDivisionError" in res.stderr

    def test_repl_timeout_protection(self):
        repl = LocalReplSandbox()
        # Code sleeps for 2 seconds, timeout capped at 0.2 seconds
        sleep_code = "import time; time.sleep(2.0)"
        res = repl.execute_code(sleep_code, timeout=0.2)
        assert res.success is False
        assert res.timed_out is True
        assert "TimeoutExpired" in res.error

    def test_repl_empty_code(self):
        repl = LocalReplSandbox()
        res = repl.execute_code("   \n  ")
        assert res.success is True
        assert res.stdout == ""


# ==============================================================================
# 8. F14: Antigravity CLI Quota Offloader Tests
# ==============================================================================

class TestAgyQuotaOffloader:
    def test_offloader_supported_models(self):
        offloader = AgyQuotaOffloader()
        models = offloader.SUPPORTED_MODELS
        assert "gemini-3.1-pro-high" in models
        assert "claude-3.7-sonnet" in models

    def test_offloader_when_cli_unavailable(self, monkeypatch, tmp_path):
        fake_path = tmp_path / "non_existent_agy.exe"
        offloader = AgyQuotaOffloader(agy_path=fake_path)
        monkeypatch.setattr(offloader, "is_available", lambda: False)
        res = offloader.offload_task("Test prompt", model="gemini-3.1-pro-high")
        assert res["success"] is False
        assert res["quota_offloaded"] is False
        assert "not found" in res["error"]

    def test_offloader_task_dispatch_native(self, monkeypatch, tmp_path):
        fake_binary = tmp_path / "agy.exe"
        fake_binary.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        offloader = AgyQuotaOffloader(agy_path=fake_binary)

        dummy_runner = DummySubprocessRunner(
            returncode=0,
            stdout='{"response": "Offloaded to Gemini 3.1 Pro High", "tokens": 42}',
            stderr="",
        )
        monkeypatch.setattr(subprocess, "run", dummy_runner)

        res = offloader.offload_task("Write quicksort in python")
        assert res["success"] is True
        assert res["quota_offloaded"] is True
        assert res["parsed_json"]["response"] == "Offloaded to Gemini 3.1 Pro High"


# ==============================================================================
# 9. F14: Unified LaptopNode Facade Tests
# ==============================================================================

class TestLaptopNodeFacade:
    def test_laptop_node_lifecycle(self, coordinator):
        laptop = LaptopNode(node_id="laptop_facade_01")
        reg = laptop.connect(coordinator)

        assert reg.node_id == "laptop_facade_01"
        assert reg.tier == TIER_2_LAPTOP
        assert coordinator.nodes["laptop_facade_01"] is not None

        # Verify heartbeat
        assert laptop.heartbeat(coordinator) is True

        # Verify REPL execution
        repl_res = laptop.execute_repl("print('Hello from laptop REPL')")
        assert repl_res.success is True
        assert "Hello from laptop REPL" in repl_res.stdout

        # Verify safe sync
        assert laptop.safe_sync_git(".") is True

        # Verify disconnect
        assert laptop.disconnect(coordinator) is True
        assert coordinator.get_best_worker_for_task(CAPABILITY_AGY_CLI) is None
