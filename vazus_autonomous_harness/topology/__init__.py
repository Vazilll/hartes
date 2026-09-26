"""
vazus_autonomous_harness.topology -- Asymmetric Multi-Tier Autonomous Topology (Milestone 5).

Exports:
- NodeRegistration: Dataclass representing worker nodes across 4 tiers.
- TopologyCoordinator: 4-tier capability-based routing coordinator (F13).
- LaptopNode: Unified Tier 2 local power multiplier facade (F14).
- LaptopLeaseManager: Dynamic 10-minute TTL lease management.
- GitFastForwardSync: Safe git fast-forward protocol preventing split-brain states.
- LocalReplSandbox: Subprocess-isolated Python REPL sandbox.
- ReplExecutionResult: Dataclass representing local REPL execution results.
- AgyQuotaOffloader: Antigravity CLI quota offloading manager.
"""

from vazus_autonomous_harness.topology.coordinator import (
    NodeRegistration,
    TopologyCoordinator,
    TIER_0_VPS,
    TIER_1_CLOUD,
    TIER_1_5_EDGE,
    TIER_2_LAPTOP,
    TIER_PRIORITY,
    CAPABILITY_SMT_Z3,
    CAPABILITY_GPU,
    CAPABILITY_NPU,
    CAPABILITY_AGY_CLI,
    CAPABILITY_REPL,
    CAPABILITY_HEAVY_PYTEST,
    CAPABILITY_JULES_VM,
    CAPABILITY_ORCHESTRATE,
    CAPABILITY_CRON,
    CAPABILITY_WEBHOOK,
    CAPABILITY_GIT_SYNC,
    CAPABILITY_LOCAL_LLM,
)

from vazus_autonomous_harness.topology.laptop_node import (
    LaptopNode,
    LaptopLeaseManager,
    GitFastForwardSync,
    LocalReplSandbox,
    ReplExecutionResult,
    AgyQuotaOffloader,
    DEFAULT_LEASE_TTL_SECONDS,
    DEFAULT_LAPTOP_NODE_ID,
    DEFAULT_LAPTOP_CAPABILITIES,
)

__all__ = [
    "NodeRegistration",
    "TopologyCoordinator",
    "LaptopNode",
    "LaptopLeaseManager",
    "GitFastForwardSync",
    "LocalReplSandbox",
    "ReplExecutionResult",
    "AgyQuotaOffloader",
    "TIER_0_VPS",
    "TIER_1_CLOUD",
    "TIER_1_5_EDGE",
    "TIER_2_LAPTOP",
    "TIER_PRIORITY",
    "CAPABILITY_SMT_Z3",
    "CAPABILITY_GPU",
    "CAPABILITY_NPU",
    "CAPABILITY_AGY_CLI",
    "CAPABILITY_REPL",
    "CAPABILITY_HEAVY_PYTEST",
    "CAPABILITY_JULES_VM",
    "CAPABILITY_ORCHESTRATE",
    "CAPABILITY_CRON",
    "CAPABILITY_WEBHOOK",
    "CAPABILITY_GIT_SYNC",
    "CAPABILITY_LOCAL_LLM",
    "DEFAULT_LEASE_TTL_SECONDS",
    "DEFAULT_LAPTOP_NODE_ID",
    "DEFAULT_LAPTOP_CAPABILITIES",
]
