"""
vazus_autonomous_harness.daemon.vps_daemon -- Headless VPS Orchestration Daemon (Tier 0).

Operates 24/7 on 1 GB Linux VPS (157.228.174.15) under strict cgroup memory caps
(MemoryMax=200M, MemoryHigh=160M). Provides:
- 30s event loop / tick scheduler
- Node presence and TTL lease registry (Tier 1.5 Edge & Tier 2 Laptop tracking)
- Memory watchdog with automatic garbage collection trigger
- Remote cloud job dispatching (GitHub Actions & Google Jules Cloud VM)
- OpenColab queue inspection and integration
"""

import os
import gc
import json
import time
import logging
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional

import httpx

from vazus_autonomous_harness.daemon.colab_bridge import ColabBridge

logger = logging.getLogger("vazus.daemon.vps_daemon")

DEFAULT_VPS_IP = "157.228.174.15"
DEFAULT_MEMORY_LIMIT_MB = 200.0
DEFAULT_MEMORY_WARNING_MB = 150.0
DEFAULT_NODE_TTL_SECONDS = 90.0
DEFAULT_TICK_INTERVAL_SECONDS = 30.0


@dataclass
class NodeRecord:
    node_id: str
    tier: str  # Tier0_VPS, Tier1_Cloud, Tier1_5_Edge, Tier2_Laptop
    capabilities: List[str]  # SMT_Z3, GPU, NPU, AGY_CLI, REPL
    last_seen: float
    ttl_seconds: float = 90.0
    lease_expires_at: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_alive(self, current_time: float) -> bool:
        return current_time <= self.lease_expires_at

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class VpsDaemon:
    """
    Lightweight Headless VPS Daemon for Tier 0 Cloud Control Plane.
    Strictly <= 200 MB RAM budget on 1 GB VPS 157.228.174.15.
    """

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path
        self.config = self._load_config(config_path)

        self.vps_ip = self.config.get("vps_ip", DEFAULT_VPS_IP)
        self.memory_limit_mb = float(self.config.get("memory_limit_mb", DEFAULT_MEMORY_LIMIT_MB))
        self.memory_warning_mb = float(self.config.get("memory_warning_mb", DEFAULT_MEMORY_WARNING_MB))
        self.node_ttl_sec = float(self.config.get("node_ttl_sec", DEFAULT_NODE_TTL_SECONDS))
        self.github_repo = self.config.get("github_repo", os.getenv("GITHUB_REPOSITORY", "Vazilll/hartes"))
        self.github_token = self.config.get("github_token", os.getenv("GITHUB_TOKEN", ""))
        self.jules_token = self.config.get("jules_token", os.getenv("JULES_API_KEY", ""))

        queue_root = self.config.get("colab_queue_root")
        self.colab_bridge = ColabBridge(queue_root=queue_root)

        self.nodes: Dict[str, NodeRecord] = {}
        self.start_time = time.time()
        self.tick_count = 0
        self.last_tick_time: float = 0.0
        self.dispatched_jobs_history: List[Dict[str, Any]] = []

    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        if not config_path:
            return {}
        p = Path(config_path)
        if not p.exists():
            logger.warning(f"[VpsDaemon] Config path {config_path} does not exist, using defaults.")
            return {}

        try:
            with open(p, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return {}
                if content.startswith("{"):
                    return json.loads(content)
                # Parse key=value environment file
                cfg = {}
                for line in content.splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        cfg[k.strip().lower()] = v.strip().strip('"').strip("'")
                return cfg
        except Exception as e:
            logger.error(f"[VpsDaemon] Error parsing config {config_path}: {e}")
            return {}

    def get_memory_usage_mb(self) -> float:
        """
        Inspects process RSS footprint.
        Tries /proc/self/status on Linux, then psutil if available.
        """
        # 1. Try Linux /proc/self/status (zero overhead, standard on VPS)
        proc_status = Path("/proc/self/status")
        if proc_status.exists():
            try:
                for line in proc_status.read_text(encoding="utf-8").splitlines():
                    if line.startswith("VmRSS:"):
                        parts = line.split()
                        if len(parts) >= 2:
                            kb = float(parts[1])
                            return kb / 1024.0
            except Exception:
                pass

        # 2. Try psutil
        try:
            import psutil
            process = psutil.Process()
            rss_bytes = process.memory_info().rss
            return rss_bytes / (1024.0 * 1024.0)
        except Exception:
            pass

        # 3. Fallback conservative estimate
        return 45.0

    def register_node(
        self,
        node_id: str,
        tier: str,
        capabilities: List[str],
        ttl_seconds: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Registers a worker node (Tier 1.5 Edge or Tier 2 Laptop).
        """
        now = time.time()
        ttl = ttl_seconds if ttl_seconds is not None else self.node_ttl_sec
        record = NodeRecord(
            node_id=node_id,
            tier=tier,
            capabilities=list(capabilities),
            last_seen=now,
            ttl_seconds=ttl,
            lease_expires_at=now + ttl,
            metadata=metadata or {},
        )
        self.nodes[node_id] = record
        logger.info(f"[VpsDaemon] Registered node {node_id} ({tier}) with TTL {ttl}s")
        return True

    def heartbeat_node(self, node_id: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Extends lease of an existing registered node.
        """
        now = time.time()
        if node_id not in self.nodes:
            logger.warning(f"[VpsDaemon] Heartbeat received for unregistered node: {node_id}")
            return False

        record = self.nodes[node_id]
        record.last_seen = now
        record.lease_expires_at = now + record.ttl_seconds
        if metadata:
            record.metadata.update(metadata)
        logger.debug(f"[VpsDaemon] Heartbeat renewed for node {node_id}")
        return True

    def get_active_nodes(self) -> List[Dict[str, Any]]:
        """Returns list of all non-expired registered nodes."""
        now = time.time()
        return [
            node.to_dict()
            for node in self.nodes.values()
            if node.is_alive(now)
        ]

    def prune_expired_nodes(self) -> List[str]:
        """
        Removes dead nodes that have exceeded their lease TTL.
        Returns list of pruned node IDs.
        """
        now = time.time()
        expired = [nid for nid, node in self.nodes.items() if not node.is_alive(now)]
        for nid in expired:
            del self.nodes[nid]
            logger.info(f"[VpsDaemon] Pruned expired node lease: {nid}")
        return expired

    def dispatch_cloud_job(self, workflow_name: str, payload: dict) -> bool:
        """
        Dispatches remote compute job to GitHub Actions or Google Jules Cloud VM.
        Conforms strictly to PROJECT.md interface contract:
            dispatch_cloud_job(self, workflow_name: str, payload: dict) -> bool
        """
        now = time.time()
        iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))

        # 1. Google Jules Cloud VM dispatch
        if workflow_name.lower() in ("jules", "google_jules", "jules_session"):
            return self._dispatch_jules(payload, now, iso)

        # 2. GitHub Actions workflow dispatch
        return self._dispatch_github_actions(workflow_name, payload, now, iso)

    def _dispatch_github_actions(self, workflow_name: str, payload: dict, now: float, iso: str) -> bool:
        """Triggers GitHub Actions workflow_dispatch."""
        repo = payload.get("repo") or self.github_repo
        token_val = payload.get("token") or self.github_token
        ref = payload.get("ref", "main")
        inputs = payload.get("inputs", {})

        wf_file = workflow_name if workflow_name.endswith((".yml", ".yaml")) else f"{workflow_name}.yml"
        url = f"https://api.github.com/repos/{repo}/actions/workflows/{wf_file}/dispatches"
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
        }
        if token_val:
            headers["Authorization"] = f"Bearer {token_val}"

        req_body = {"ref": ref, "inputs": inputs}

        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.post(url, json=req_body, headers=headers)
                success = resp.status_code in (200, 201, 204)
                record = {
                    "target": "github_actions",
                    "workflow": wf_file,
                    "repo": repo,
                    "timestamp": now,
                    "iso_time": iso,
                    "status_code": resp.status_code,
                    "success": success,
                }
                self.dispatched_jobs_history.append(record)
                if success:
                    logger.info(f"[VpsDaemon] Dispatched GitHub Actions workflow {wf_file} ({resp.status_code})")
                    return True
                else:
                    logger.warning(f"[VpsDaemon] GitHub Actions dispatch returned HTTP {resp.status_code}: {resp.text}")
                    return False
        except Exception as e:
            logger.error(f"[VpsDaemon] GitHub Actions dispatch exception: {e}")
            self.dispatched_jobs_history.append({
                "target": "github_actions",
                "workflow": wf_file,
                "timestamp": now,
                "iso_time": iso,
                "success": False,
                "error": str(e),
            })
            return False

    def _dispatch_jules(self, payload: dict, now: float, iso: str) -> bool:
        """Triggers Google Jules Cloud VM session."""
        j_key = payload.get("api_key") or self.jules_token
        source_id = payload.get("source_id", f"sources/github/{self.github_repo}")
        prompt = payload.get("prompt", "Execute autonomous test audit and SMT proof verification")
        title = payload.get("title", "VPS Daemon Jules Sprint")

        url = "https://jules.googleapis.com/v1alpha/sessions"
        headers = {"Content-Type": "application/json"}
        if j_key:
            headers["X-Goog-Api-Key"] = j_key

        req_body = {
            "source_id": source_id,
            "prompt": prompt,
            "title": title,
        }

        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.post(url, json=req_body, headers=headers)
                success = resp.status_code in (200, 201)
                record = {
                    "target": "google_jules",
                    "source_id": source_id,
                    "timestamp": now,
                    "iso_time": iso,
                    "status_code": resp.status_code,
                    "success": success,
                }
                self.dispatched_jobs_history.append(record)
                if success:
                    logger.info(f"[VpsDaemon] Dispatched Jules session ({resp.status_code})")
                    return True
                else:
                    logger.warning(f"[VpsDaemon] Jules dispatch returned HTTP {resp.status_code}: {resp.text}")
                    return False
        except Exception as e:
            logger.error(f"[VpsDaemon] Jules dispatch exception: {e}")
            self.dispatched_jobs_history.append({
                "target": "google_jules",
                "timestamp": now,
                "iso_time": iso,
                "success": False,
                "error": str(e),
            })
            return False

    def tick(self) -> Dict[str, Any]:
        """
        Executes a single 30s event tick.
        Conforms strictly to PROJECT.md interface contract:
            tick(self) -> Dict[str, Any]
        Per contract: runs heartbeat, checks node presence, polls colab queue.
        """
        now = time.time()
        iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))
        self.tick_count += 1
        self.last_tick_time = now

        # 1. Memory Watchdog (Strict <= 200 MB budget)
        rss_mb = self.get_memory_usage_mb()
        gc_triggered = False
        memory_status = "OPTIMAL"

        if rss_mb > self.memory_warning_mb:
            logger.warning(
                f"[VpsDaemon Watchdog] Memory RSS ({rss_mb:.1f} MB) exceeded warning threshold "
                f"({self.memory_warning_mb:.1f} MB). Forcing garbage collection."
            )
            gc.collect()
            gc_triggered = True
            rss_mb = self.get_memory_usage_mb()
            memory_status = "WARNING_HIGH_MEMORY" if rss_mb > self.memory_warning_mb else "RECOVERED"

        if rss_mb > self.memory_limit_mb:
            memory_status = "CRITICAL_EXCEEDS_BUDGET"

        # 2. Node Presence & Lease Pruning
        pruned_nodes = self.prune_expired_nodes()
        active_nodes = self.get_active_nodes()

        # 3. Colab Queue Polling
        pending_colab = self.colab_bridge.list_pending_jobs()
        active_colab = self.colab_bridge.list_active_jobs()
        completed_colab = self.colab_bridge.list_completed_jobs()
        keepalive_info = self.colab_bridge.get_keepalive_status()

        # 4. Asymmetric Topology Routing Advisory
        has_gpu_node = any("GPU" in n["capabilities"] for n in active_nodes)
        has_arm64_smt_node = any("SMT_Z3" in n["capabilities"] for n in active_nodes if "Edge" in n["tier"])

        colab_summary = {
            "pending_count": len(pending_colab),
            "active_count": len(active_colab),
            "completed_count": len(completed_colab),
            "worker_alive": keepalive_info.get("alive", False),
            "keepalive_age_sec": keepalive_info.get("age_seconds", -1.0),
        }

        tick_result = {
            "tick_id": self.tick_count,
            "timestamp": now,
            "iso_time": iso,
            "uptime_seconds": round(now - self.start_time, 2),
            "vps_ip": self.vps_ip,
            "memory": {
                "rss_mb": round(rss_mb, 2),
                "limit_mb": self.memory_limit_mb,
                "warning_mb": self.memory_warning_mb,
                "headroom_mb": round(self.memory_limit_mb - rss_mb, 2),
                "status": memory_status,
                "gc_triggered": gc_triggered,
            },
            "nodes": {
                "active_count": len(active_nodes),
                "pruned_count": len(pruned_nodes),
                "pruned_ids": pruned_nodes,
                "active_nodes": active_nodes,
                "has_gpu_node": has_gpu_node,
                "has_arm64_smt_node": has_arm64_smt_node,
            },
            "colab_queue": colab_summary,
            "dispatched_jobs_count": len(self.dispatched_jobs_history),
        }

        logger.debug(f"[VpsDaemon] Tick #{self.tick_count} complete: RSS={rss_mb:.1f}MB, Nodes={len(active_nodes)}")
        return tick_result

    async def run_loop(
        self,
        interval_seconds: float = DEFAULT_TICK_INTERVAL_SECONDS,
        max_ticks: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Async event loop executing periodic ticks.
        """
        import asyncio

        results = []
        logger.info(f"[VpsDaemon] Starting event loop (interval={interval_seconds}s, max_ticks={max_ticks})")

        while True:
            res = self.tick()
            results.append(res)

            if max_ticks is not None and self.tick_count >= max_ticks:
                logger.info(f"[VpsDaemon] Reached max ticks ({max_ticks}). Stopping loop.")
                break

            await asyncio.sleep(interval_seconds)

        return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Vazus Flywheel VPS Headless Daemon (Tier 0)")
    parser.add_argument("--config", "-c", type=str, default="/etc/vazus/flywheel.env", help="Path to config file")
    parser.add_argument("--interval", "-i", type=float, default=30.0, help="Tick interval in seconds")
    parser.add_argument("--ticks", "-t", type=int, default=None, help="Number of ticks to run (default: infinite)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    daemon = VpsDaemon(config_path=args.config)
    import asyncio
    asyncio.run(daemon.run_loop(interval_seconds=args.interval, max_ticks=args.ticks))


if __name__ == "__main__":
    main()
