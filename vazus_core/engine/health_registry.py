"""
vazus_core.engine.health_registry — Centralized Subsystem Health & Degradation Monitor.
========================================================================================

Eliminates silent degradation and invisible failure modes.
Provides continuous telemetry on whether subsystems (Z3 SMT, Go IPC, Win32 Sandbox,
Embeddings, Graphify, Memory Gateway) are ONLINE, DEGRADED, or OFFLINE.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

logger = logging.getLogger("vazus_core.health_registry")


@dataclass
class SubsystemStatus:
    name: str
    category: str
    status: str  # "ONLINE", "DEGRADED", "OFFLINE"
    message: str = "Operating normally"
    last_check: float = field(default_factory=time.time)
    fallback_count: int = 0


class SubsystemHealthRegistry:
    """
    Singleton telemetry tracker for all OS subsystems and hardware accelerators.
    """

    _instance: Optional["SubsystemHealthRegistry"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._registry = {}
            cls._instance._init_default_checks()
        return cls._instance

    def _init_default_checks(self):
        """Registers default core subsystems."""
        defaults = [
            ("win32_job_sandbox", "Security / Sandbox", "ONLINE"),
            ("sqlite_wal_pool", "Storage / DB", "ONLINE"),
            ("smt_z3_solver", "Verification / SMT", "ONLINE"),
            ("go_symbol_pool", "IPC / Graph", "ONLINE"),
            ("shared_memory_bus", "IPC / Memory", "ONLINE"),
            ("unified_memory_gateway", "Memory / Knowledge", "ONLINE"),
            ("dynamic_mcp_gateway", "Context / Gateway", "ONLINE"),
            ("graphify_engine", "AST / Topology", "ONLINE"),
            ("entropy_scrubber", "Security / Scrub", "ONLINE"),
        ]
        for name, cat, st in defaults:
            self._registry[name] = SubsystemStatus(name=name, category=cat, status=st)

    def record_degradation(self, subsystem_name: str, reason: str):
        """Logs an explicit warning and flags a subsystem as degraded."""
        logger.warning(f"[HEALTH DEGRADATION ALERT] Subsystem '{subsystem_name}' degraded: {reason}")
        if subsystem_name in self._registry:
            sub = self._registry[subsystem_name]
            sub.status = "DEGRADED"
            sub.message = reason
            sub.fallback_count += 1
            sub.last_check = time.time()
        else:
            self._registry[subsystem_name] = SubsystemStatus(
                name=subsystem_name, category="Runtime", status="DEGRADED", message=reason, fallback_count=1
            )

    def record_online(self, subsystem_name: str, message: str = "Operational"):
        """Marks a subsystem as healthy and fully operational."""
        if subsystem_name in self._registry:
            sub = self._registry[subsystem_name]
            sub.status = "ONLINE"
            sub.message = message
            sub.last_check = time.time()

    def get_health_report(self) -> Dict[str, Any]:
        """Returns structured health snapshot of all registered subsystems."""
        online_cnt = sum(1 for s in self._registry.values() if s.status == "ONLINE")
        degraded_cnt = sum(1 for s in self._registry.values() if s.status == "DEGRADED")
        offline_cnt = sum(1 for s in self._registry.values() if s.status == "OFFLINE")

        return {
            "total_subsystems": len(self._registry),
            "online": online_cnt,
            "degraded": degraded_cnt,
            "offline": offline_cnt,
            "health_score_pct": round((online_cnt / max(1, len(self._registry))) * 100, 1),
            "details": {
                name: {"category": s.category, "status": s.status, "message": s.message, "fallbacks": s.fallback_count}
                for name, s in self._registry.items()
            },
        }


# Global singleton instance
health_registry = SubsystemHealthRegistry()
