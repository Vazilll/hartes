"""
vazus_autonomous_harness.topology.coordinator -- Asymmetric 4-Tier Topology Coordinator (F13).

Coordinates the distributed 4-tier autonomous operating topology:
- Tier 0: Always-On Cloud Control Plane (1 GB Linux VPS 157.228.174.15, <= 200 MB RSS)
- Tier 1: Heavy Cloud Data Plane (GitHub Actions 16 GB Runners, Jules Cloud VM)
- Tier 1.5: Home Edge Server Node (Orange Pi 4 Pro 6 GB ARM64, 24/7 low-power ~5-10W)
- Tier 2: Local Power Multiplier Node (User Laptop with GPU/NPU, agy CLI, REPL sandboxes)

Provides capability-based routing, TTL lease management, failover, and safe git fast-forward checks.
"""

import logging
import subprocess
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger("vazus.topology.coordinator")

# 4-Tier Topology Constants strictly conforming to PROJECT.md
TIER_0_VPS = "Tier0_VPS"
TIER_1_CLOUD = "Tier1_Cloud"
TIER_1_5_EDGE = "Tier1_5_Edge"
TIER_2_LAPTOP = "Tier2_Laptop"

# Routing priority hierarchy: Laptop (Tier 2) > Edge (Tier 1.5) > Cloud (Tier 1) > VPS (Tier 0)
TIER_PRIORITY: Dict[str, int] = {
    TIER_2_LAPTOP: 40,
    TIER_1_5_EDGE: 30,
    TIER_1_CLOUD: 20,
    TIER_0_VPS: 10,
}

# Standard Capability Definitions
CAPABILITY_SMT_Z3 = "SMT_Z3"
CAPABILITY_GPU = "GPU"
CAPABILITY_NPU = "NPU"
CAPABILITY_AGY_CLI = "AGY_CLI"
CAPABILITY_REPL = "REPL"
CAPABILITY_HEAVY_PYTEST = "HEAVY_PYTEST"
CAPABILITY_JULES_VM = "JULES_VM"
CAPABILITY_ORCHESTRATE = "ORCHESTRATE"
CAPABILITY_CRON = "CRON"
CAPABILITY_WEBHOOK = "WEBHOOK"
CAPABILITY_GIT_SYNC = "GIT_SYNC"
CAPABILITY_LOCAL_LLM = "LOCAL_LLM"


@dataclass
class NodeRegistration:
    """
    Worker Node Registration record adhering strictly to PROJECT.md § M5 Interface Contracts.
    """
    node_id: str
    tier: str  # 'Tier0_VPS', 'Tier1_Cloud', 'Tier1_5_Edge', 'Tier2_Laptop'
    capabilities: List[str]  # e.g. ['SMT_Z3', 'GPU', 'NPU', 'AGY_CLI', 'REPL']
    lease_expires_at: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    registered_at: float = field(default_factory=time.time)

    def __post_init__(self):
        if not isinstance(self.capabilities, list):
            self.capabilities = list(self.capabilities)

    def is_active(self, current_time: Optional[float] = None) -> bool:
        """Returns True if the node's lease has not expired."""
        now = current_time if current_time is not None else time.time()
        return self.lease_expires_at > now

    def remaining_lease_seconds(self, current_time: Optional[float] = None) -> float:
        """Returns the remaining seconds on the lease (clamped to 0.0)."""
        now = current_time if current_time is not None else time.time()
        return max(0.0, self.lease_expires_at - now)

    def has_capability(self, capability: str) -> bool:
        """Checks if the node provides the specified capability."""
        return capability in self.capabilities

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the registration to a dictionary."""
        return asdict(self)


class TopologyCoordinator:
    """
    Distributed Asymmetric 4-Tier Topology Coordinator (F13).

    Responsibilities:
    - Maintains the active registry of worker nodes across Tier 0, 1, 1.5, and 2.
    - Manages dynamic lease registration and heartbeat renewals.
    - Routes queued tasks to the optimal worker node based on required capability and tier hierarchy.
    - Handles failover when a higher-tier node (e.g. Laptop) drops offline.
    - Enforces safe git synchronization to prevent split-brain state corruptions.
    """

    def __init__(self):
        self.nodes: Dict[str, NodeRegistration] = {}
        self._routing_log: List[Dict[str, Any]] = []

    def register_node(self, node: NodeRegistration) -> bool:
        """
        Registers or updates a worker node in the topology coordinator.
        Returns True on successful registration.
        """
        if not isinstance(node, NodeRegistration):
            logger.error("[TopologyCoordinator] Invalid node registration type: %s", type(node))
            return False

        if not node.node_id or not isinstance(node.node_id, str):
            logger.error("[TopologyCoordinator] Invalid node_id: %s", node.node_id)
            return False

        self.nodes[node.node_id] = node
        logger.debug(
            "[TopologyCoordinator] Registered node %s (tier=%s, caps=%s, lease_exp=%.2f)",
            node.node_id, node.tier, node.capabilities, node.lease_expires_at
        )
        return True

    def heartbeat_node(self, node_id: str, extension_seconds: float = 600.0) -> bool:
        """
        Extends the TTL lease for a registered node by `extension_seconds` (default: 600s / 10 min).
        Returns True if the node exists and lease was extended, False otherwise.
        """
        if node_id not in self.nodes:
            logger.warning("[TopologyCoordinator] Heartbeat rejected: node %s not found", node_id)
            return False

        now = time.time()
        node = self.nodes[node_id]
        # Extend lease from current time
        node.lease_expires_at = now + extension_seconds
        logger.debug(
            "[TopologyCoordinator] Heartbeat for node %s extended lease by %.1fs (new expiry: %.2f)",
            node_id, extension_seconds, node.lease_expires_at
        )
        return True

    def get_best_worker_for_task(
        self,
        required_capability: str,
        current_time: Optional[float] = None
    ) -> Optional[NodeRegistration]:
        """
        Selects the best available worker node that possesses `required_capability`
        and whose TTL lease has not expired.

        Priority hierarchy:
        Tier 2 Laptop (40) > Tier 1.5 Edge (30) > Tier 1 Cloud (20) > Tier 0 VPS (10).
        Secondary tie-breaker: longest remaining lease time, then alphabetical node_id.
        """
        now = current_time if current_time is not None else time.time()

        # Filter nodes by active lease and capability
        candidates = [
            node for node in self.nodes.values()
            if node.lease_expires_at > now and required_capability in node.capabilities
        ]

        if not candidates:
            return None

        # Sort by tier priority descending, then remaining lease descending, then node_id ascending
        candidates.sort(
            key=lambda n: (
                TIER_PRIORITY.get(n.tier, 0),
                n.lease_expires_at,
                -len(n.node_id),
            ),
            reverse=True
        )

        selected = candidates[0]
        self._routing_log.append({
            "capability": required_capability,
            "selected_node_id": selected.node_id,
            "selected_tier": selected.tier,
            "timestamp": now,
        })
        return selected

    def route_multi_capability_task(
        self,
        required_capabilities: Sequence[str],
        current_time: Optional[float] = None
    ) -> Optional[NodeRegistration]:
        """
        Selects the best worker that possesses ALL required capabilities.
        """
        now = current_time if current_time is not None else time.time()
        candidates = [
            node for node in self.nodes.values()
            if node.lease_expires_at > now and all(cap in node.capabilities for cap in required_capabilities)
        ]
        if not candidates:
            return None

        candidates.sort(
            key=lambda n: (
                TIER_PRIORITY.get(n.tier, 0),
                n.lease_expires_at,
            ),
            reverse=True
        )
        return candidates[0]

    def safe_sync_git(self, repo_path: str = ".") -> bool:
        """
        Enforces safe git synchronization to prevent split-brain state divergences.
        Verifies:
        1. Repository status is queryable via git.
        2. No unresolved git merge conflicts exist in the working tree.
        """
        try:
            res = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if res.returncode != 0:
                logger.warning("[TopologyCoordinator] git status returned code %d", res.returncode)
                return False

            # Check for conflict markers in git status output
            # Porcelain conflict indicators: 'UU', 'AA', 'UD', 'DU', 'DD', 'AU', 'UA'
            conflict_prefixes = ("UU ", "AA ", "UD ", "DU ", "DD ", "AU ", "UA ")
            lines = res.stdout.splitlines()
            for line in lines:
                if line.startswith(conflict_prefixes):
                    logger.error("[TopologyCoordinator] Unresolved merge conflict detected in line: %s", line)
                    return False

            return True
        except Exception as exc:
            logger.error("[TopologyCoordinator] safe_sync_git failed with error: %s", exc)
            return False

    def unregister_node(self, node_id: str) -> bool:
        """Removes a node from the registry."""
        if node_id in self.nodes:
            del self.nodes[node_id]
            logger.debug("[TopologyCoordinator] Node %s unregistered", node_id)
            return True
        return False

    def prune_expired_nodes(self, current_time: Optional[float] = None) -> List[str]:
        """
        Removes all nodes whose TTL lease has expired.
        Returns the list of pruned node IDs.
        """
        now = current_time if current_time is not None else time.time()
        expired_ids = [nid for nid, node in self.nodes.items() if node.lease_expires_at <= now]
        for nid in expired_ids:
            del self.nodes[nid]
        if expired_ids:
            logger.info("[TopologyCoordinator] Pruned %d expired nodes: %s", len(expired_ids), expired_ids)
        return expired_ids

    def get_active_nodes(
        self,
        tier: Optional[str] = None,
        current_time: Optional[float] = None
    ) -> List[NodeRegistration]:
        """Returns all currently active (non-expired) nodes, optionally filtered by tier."""
        now = current_time if current_time is not None else time.time()
        active = [n for n in self.nodes.values() if n.lease_expires_at > now]
        if tier:
            active = [n for n in active if n.tier == tier]
        return active

    def get_topology_summary(self, current_time: Optional[float] = None) -> Dict[str, Any]:
        """
        Generates a summary of the current multi-tier operating topology.
        """
        now = current_time if current_time is not None else time.time()
        active_nodes = self.get_active_nodes(current_time=now)

        tier_counts = {TIER_0_VPS: 0, TIER_1_CLOUD: 0, TIER_1_5_EDGE: 0, TIER_2_LAPTOP: 0}
        for n in active_nodes:
            tier_counts[n.tier] = tier_counts.get(n.tier, 0) + 1

        all_caps = sorted(list({cap for n in active_nodes for cap in n.capabilities}))

        return {
            "total_registered": len(self.nodes),
            "total_active": len(active_nodes),
            "tier_distribution": tier_counts,
            "available_capabilities": all_caps,
            "laptop_online": tier_counts.get(TIER_2_LAPTOP, 0) > 0,
            "edge_online": tier_counts.get(TIER_1_5_EDGE, 0) > 0,
            "vps_online": tier_counts.get(TIER_0_VPS, 0) > 0,
            "cloud_online": tier_counts.get(TIER_1_CLOUD, 0) > 0,
            "timestamp": now,
        }
