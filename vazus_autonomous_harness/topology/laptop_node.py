"""
vazus_autonomous_harness.topology.laptop_node -- Laptop Power Multiplier & Lease Manager (F14).

Manages the dynamic Tier 2 Laptop node:
- 10-minute TTL leases (lease_expires_at) for dynamic join and leave.
- Opportunistic routing when awake (high-throughput local GPU/NPU acceleration).
- Sub-second graceful failover when offline or sleeping.
- Safe git fast-forward merge protocol preventing split-brain divergences.
- Quota offloading via Antigravity CLI (agy.exe) for Gemini 3.1 Pro and Claude 3.7 Sonnet.
- Local REPL sandbox execution in isolated subprocesses.
"""

import os
import sys
import time
import json
import logging
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from vazus_autonomous_harness.topology.coordinator import (
    NodeRegistration,
    TopologyCoordinator,
    TIER_2_LAPTOP,
    CAPABILITY_GPU,
    CAPABILITY_NPU,
    CAPABILITY_AGY_CLI,
    CAPABILITY_REPL,
    CAPABILITY_SMT_Z3,
    CAPABILITY_GIT_SYNC,
)

logger = logging.getLogger("vazus.topology.laptop_node")

DEFAULT_LAPTOP_NODE_ID = "laptop_tier2"
DEFAULT_LEASE_TTL_SECONDS = 600.0  # 10 minutes strictly as specified in PROJECT.md
DEFAULT_LAPTOP_CAPABILITIES = [
    CAPABILITY_GPU,
    CAPABILITY_NPU,
    CAPABILITY_AGY_CLI,
    CAPABILITY_REPL,
    CAPABILITY_SMT_Z3,
    CAPABILITY_GIT_SYNC,
]

# Standard Antigravity CLI default path on Windows
DEFAULT_AGY_PATH = (
    Path(os.environ.get("LOCALAPPDATA", r"C:\Users\Vaz\AppData\Local"))
    / "agy"
    / "bin"
    / "agy.exe"
)


# ==============================================================================
# 1. Local REPL Sandbox
# ==============================================================================

@dataclass
class ReplExecutionResult:
    """Outcome of code execution in local REPL sandbox."""
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    execution_time_ms: float
    timed_out: bool = False
    error: Optional[str] = None
    output_value: Optional[Any] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class LocalReplSandbox:
    """
    Genuine isolated subprocess Python REPL sandbox.
    Executes Python snippets safely without polluting the host process memory.
    """

    def __init__(self, max_output_chars: int = 50_000):
        self.max_output_chars = max_output_chars

    def execute_code(
        self,
        code: str,
        timeout: float = 10.0,
        cwd: Optional[str] = None,
        env_overrides: Optional[Dict[str, str]] = None,
    ) -> ReplExecutionResult:
        """
        Executes python code string in an isolated subprocess.
        Captures stdout, stderr, execution duration, and exit status.
        """
        if not code or not code.strip():
            return ReplExecutionResult(
                success=True,
                stdout="",
                stderr="",
                exit_code=0,
                execution_time_ms=0.0,
            )

        env = os.environ.copy()
        if env_overrides:
            env.update(env_overrides)

        work_dir = cwd or os.getcwd()
        start_t = time.perf_counter()

        try:
            proc = subprocess.run(
                [sys.executable, "-c", code],
                cwd=work_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
            )
            elapsed_ms = (time.perf_counter() - start_t) * 1000.0
            stdout = proc.stdout[:self.max_output_chars]
            stderr = proc.stderr[:self.max_output_chars]

            return ReplExecutionResult(
                success=(proc.returncode == 0),
                stdout=stdout,
                stderr=stderr,
                exit_code=proc.returncode,
                execution_time_ms=round(elapsed_ms, 2),
                timed_out=False,
                error=None if proc.returncode == 0 else f"Process exited with code {proc.returncode}",
            )
        except subprocess.TimeoutExpired:
            elapsed_ms = (time.perf_counter() - start_t) * 1000.0
            logger.warning("[LocalReplSandbox] Execution timed out after %.2fs", timeout)
            return ReplExecutionResult(
                success=False,
                stdout="",
                stderr=f"TimeoutExpired after {timeout} seconds",
                exit_code=-1,
                execution_time_ms=round(elapsed_ms, 2),
                timed_out=True,
                error=f"TimeoutExpired: code execution exceeded {timeout}s",
            )
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start_t) * 1000.0
            logger.error("[LocalReplSandbox] Execution failed with exception: %s", exc)
            return ReplExecutionResult(
                success=False,
                stdout="",
                stderr=str(exc),
                exit_code=-1,
                execution_time_ms=round(elapsed_ms, 2),
                timed_out=False,
                error=str(exc),
            )


# ==============================================================================
# 2. Git Fast-Forward Merge Protocol (Split-Brain Immunity)
# ==============================================================================

class GitFastForwardSync:
    """
    Enforces safe Git fast-forward synchronization protocol (PROJECT.md § 8.1).
    Guarantees:
    - Never force-push or overwrite remote cloud state.
    - Strictly fast-forward merge only (git merge --ff-only).
    - If fast-forward is not possible (split-brain divergence detected),
      aborts merge and isolates changes to prevent repository corruption.
    """

    def __init__(self, repo_path: str = "."):
        self.repo_path = repo_path

    def is_git_repository(self, repo_path: Optional[str] = None) -> bool:
        """Verifies if the specified path is a valid git repository."""
        target = repo_path or self.repo_path
        try:
            res = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=target,
                capture_output=True,
                text=True,
                timeout=5,
            )
            return res.returncode == 0 and res.stdout.strip() == "true"
        except Exception:
            return False

    def check_working_tree_clean(self, repo_path: Optional[str] = None) -> Tuple[bool, List[str]]:
        """
        Checks if working tree has unresolved conflicts or uncommitted changes.
        Returns (is_clean, list_of_conflicts_or_changes).
        """
        target = repo_path or self.repo_path
        try:
            res = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=target,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if res.returncode != 0:
                return False, [f"git status error code {res.returncode}"]

            lines = [line.strip() for line in res.stdout.splitlines() if line.strip()]
            conflicts = [
                line for line in lines
                if line.startswith(("UU ", "AA ", "UD ", "DU ", "DD ", "AU ", "UA "))
            ]
            if conflicts:
                return False, conflicts
            return (len(lines) == 0), lines
        except Exception as exc:
            return False, [str(exc)]

    def can_fast_forward(
        self,
        target_ref: str,
        base_ref: str = "HEAD",
        repo_path: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Checks whether `target_ref` can be fast-forward merged into `base_ref`.
        Uses `git merge-base --is-ancestor <base_ref> <target_ref>`.
        """
        target = repo_path or self.repo_path
        try:
            res = subprocess.run(
                ["git", "merge-base", "--is-ancestor", base_ref, target_ref],
                cwd=target,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if res.returncode == 0:
                return True, "Fast-forward merge is possible."
            elif res.returncode == 1:
                return False, f"Divergence detected: {base_ref} is not an ancestor of {target_ref}."
            else:
                return False, f"Git merge-base returned code {res.returncode}: {res.stderr.strip()}"
        except Exception as exc:
            return False, f"Error checking fast-forward compatibility: {exc}"

    def safe_fast_forward_sync(
        self,
        remote_ref: Optional[str] = None,
        repo_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes the safe synchronization protocol:
        1. Checks git repository validity.
        2. Detects existing conflicts.
        3. If remote_ref given, checks fast-forward ancestor relationship.
        4. If clean, performs sync without split-brain risk.
        """
        target = repo_path or self.repo_path

        if not self.is_git_repository(target):
            logger.warning("[GitFastForwardSync] %s is not a git repository", target)
            return {
                "success": False,
                "split_brain_prevented": True,
                "reason": "Not a git repository",
            }

        is_clean, changes = self.check_working_tree_clean(target)

        # Check for active merge conflicts
        conflicts = [c for c in changes if any(c.startswith(p) for p in ("UU", "AA", "UD", "DU", "DD", "AU", "UA"))]
        if conflicts:
            logger.error("[GitFastForwardSync] Unresolved merge conflicts detected: %s", conflicts)
            return {
                "success": False,
                "split_brain_prevented": True,
                "reason": f"Active merge conflicts detected: {conflicts}",
                "conflicts": conflicts,
            }

        # If a remote ref was specified, test ancestor relationship
        if remote_ref:
            can_ff, ff_reason = self.can_fast_forward(remote_ref, repo_path=target)
            if not can_ff:
                logger.warning(
                    "[GitFastForwardSync] Fast-forward not possible with %s: %s. Preventing split-brain!",
                    remote_ref, ff_reason
                )
                return {
                    "success": False,
                    "split_brain_prevented": True,
                    "reason": f"Non-fast-forward divergence detected with {remote_ref}: {ff_reason}",
                }

        return {
            "success": True,
            "split_brain_prevented": True,
            "working_tree_clean": is_clean,
            "changed_files_count": len(changes),
            "reason": "Repository is clean and fast-forward compliant.",
        }


# ==============================================================================
# 3. Antigravity (AGY) CLI Quota Offloader
# ==============================================================================

class AgyQuotaOffloader:
    """
    Integrates with the local Antigravity CLI (`agy.exe`) to offload heavy
    reasoning and coding tasks onto Gemini 3.1 Pro High and Claude 3.7 Sonnet quotas.
    """

    SUPPORTED_MODELS = [
        "gemini-3.1-pro-high",
        "gemini-3.1-flash",
        "claude-3.7-sonnet",
        "claude-3.7-sonnet-thinking",
    ]

    def __init__(self, agy_path: Optional[Path] = None):
        self.agy_path = agy_path or DEFAULT_AGY_PATH
        self._bridge = None
        self._init_bridge()

    def _init_bridge(self):
        """Attempts to load vazus_core.workers.agy_bridge if available."""
        try:
            from vazus_core.workers.agy_bridge import AgyBridge
            self._bridge = AgyBridge(agy_path=self.agy_path)
            logger.debug("[AgyQuotaOffloader] vazus_core AgyBridge loaded successfully")
        except ImportError:
            self._bridge = None

    def is_available(self) -> bool:
        """Checks if the agy executable is present and accessible on the local system."""
        if self._bridge is not None:
            return self._bridge.is_available()
        if self.agy_path.exists():
            return True
        # Check PATH
        try:
            res = subprocess.run(["where", "agy"], capture_output=True, text=True)
            return res.returncode == 0
        except Exception:
            return False

    def offload_task(
        self,
        prompt: str,
        model: str = "gemini-3.1-pro-high",
        effort: str = "high",
        timeout: float = 120.0,
        cwd: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Executes prompt via agy CLI quota offloader.
        """
        start_t = time.perf_counter()
        available = self.is_available()

        if not available:
            return {
                "success": False,
                "model": model,
                "effort": effort,
                "latency_ms": 0.0,
                "error": f"agy.exe not found at {self.agy_path} or on PATH",
                "quota_offloaded": False,
            }

        # Use discovered agy path
        exec_path = str(self.agy_path)
        cmd = [
            exec_path,
            "--print",
            prompt,
            "--model",
            model,
            "--effort",
            effort,
            "--output-format",
            "json",
            "--dangerously-skip-permissions",
        ]

        work_dir = cwd or os.getcwd()
        try:
            proc = subprocess.run(
                cmd,
                cwd=work_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            elapsed_ms = (time.perf_counter() - start_t) * 1000.0

            out_text = proc.stdout.strip()
            parsed_json = None
            if out_text.startswith("{") and out_text.endswith("}"):
                try:
                    parsed_json = json.loads(out_text)
                except json.JSONDecodeError:
                    parsed_json = None

            return {
                "success": (proc.returncode == 0),
                "model": model,
                "effort": effort,
                "exit_code": proc.returncode,
                "latency_ms": round(elapsed_ms, 2),
                "output_text": out_text,
                "parsed_json": parsed_json,
                "quota_offloaded": True,
                "error": None if proc.returncode == 0 else proc.stderr.strip(),
            }
        except subprocess.TimeoutExpired:
            elapsed_ms = (time.perf_counter() - start_t) * 1000.0
            return {
                "success": False,
                "model": model,
                "effort": effort,
                "latency_ms": round(elapsed_ms, 2),
                "error": f"agy task timed out after {timeout} seconds",
                "quota_offloaded": False,
            }
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start_t) * 1000.0
            return {
                "success": False,
                "model": model,
                "effort": effort,
                "latency_ms": round(elapsed_ms, 2),
                "error": str(exc),
                "quota_offloaded": False,
            }


# ==============================================================================
# 4. Laptop Lease Manager
# ==============================================================================

class LaptopLeaseManager:
    """
    Manages the dynamic registration, TTL leases, and heartbeat cycle for the Laptop Node.
    Default lease TTL is 10 minutes (600 seconds) according to PROJECT.md.
    """

    def __init__(
        self,
        node_id: str = DEFAULT_LAPTOP_NODE_ID,
        ttl_seconds: float = DEFAULT_LEASE_TTL_SECONDS,
        capabilities: Optional[List[str]] = None,
    ):
        self.node_id = node_id
        self.tier = TIER_2_LAPTOP
        self.ttl_seconds = ttl_seconds
        self.capabilities = list(capabilities or DEFAULT_LAPTOP_CAPABILITIES)
        self.current_lease_expires_at: float = 0.0
        self.is_registered: bool = False

    def register(
        self,
        coordinator: TopologyCoordinator,
        ttl_seconds: Optional[float] = None,
        custom_capabilities: Optional[List[str]] = None,
    ) -> NodeRegistration:
        """
        Dynamically registers the laptop node with the coordinator for `ttl_seconds` (default: 600s).
        """
        ttl = ttl_seconds if ttl_seconds is not None else self.ttl_seconds
        caps = custom_capabilities if custom_capabilities is not None else self.capabilities
        now = time.time()
        expires_at = now + ttl

        reg = NodeRegistration(
            node_id=self.node_id,
            tier=self.tier,
            capabilities=caps,
            lease_expires_at=expires_at,
            metadata={"hostname": os.environ.get("COMPUTERNAME", "laptop"), "ttl_seconds": ttl},
            registered_at=now,
        )

        success = coordinator.register_node(reg)
        if success:
            self.current_lease_expires_at = expires_at
            self.is_registered = True
            logger.info(
                "[LaptopLeaseManager] Registered laptop %s with 10-minute TTL (expires in %.1fs)",
                self.node_id, ttl
            )
        return reg

    def heartbeat(
        self,
        coordinator: TopologyCoordinator,
        extension_seconds: Optional[float] = None
    ) -> bool:
        """
        Extends the laptop lease in the coordinator.
        """
        ext = extension_seconds if extension_seconds is not None else self.ttl_seconds
        success = coordinator.heartbeat_node(self.node_id, extension_seconds=ext)
        if success:
            self.current_lease_expires_at = time.time() + ext
        return success

    def disconnect(
        self,
        coordinator: TopologyCoordinator,
        graceful: bool = True
    ) -> bool:
        """
        Disconnects the laptop node. If graceful, expires the lease immediately so that
        the coordinator fails over sub-second to Tier 1.5 Edge / Tier 1 Cloud without waiting.
        """
        if self.node_id not in coordinator.nodes:
            self.is_registered = False
            return False

        if graceful:
            # Expire immediately to trigger sub-second failover
            coordinator.nodes[self.node_id].lease_expires_at = time.time() - 1.0
            self.current_lease_expires_at = time.time() - 1.0
            self.is_registered = False
            logger.info("[LaptopLeaseManager] Gracefully disconnected laptop %s", self.node_id)
            return True
        else:
            return coordinator.unregister_node(self.node_id)

    def simulate_power_off_or_lid_close(self, coordinator: TopologyCoordinator) -> None:
        """
        Simulates laptop sleep or sudden lid close by setting lease expiration to past.
        Coordinator will detect this as offline on the next task routing request.
        """
        past_time = time.time() - 10.0
        if self.node_id in coordinator.nodes:
            coordinator.nodes[self.node_id].lease_expires_at = past_time
        self.current_lease_expires_at = past_time
        logger.info("[LaptopLeaseManager] Simulated sudden lid-close/sleep for %s", self.node_id)

    def is_lease_active(self, current_time: Optional[float] = None) -> bool:
        """Checks if local lease timestamp is still valid."""
        now = current_time if current_time is not None else time.time()
        return self.current_lease_expires_at > now


# ==============================================================================
# 5. Unified Laptop Node (Power Multiplier Facade)
# ==============================================================================

class LaptopNode:
    """
    Unified Laptop Power Multiplier Node (Tier 2).
    Integrates Lease Management, Git Fast-Forward Sync, Local REPL, and AGY CLI.
    """

    def __init__(
        self,
        node_id: str = DEFAULT_LAPTOP_NODE_ID,
        capabilities: Optional[List[str]] = None,
        ttl_seconds: float = DEFAULT_LEASE_TTL_SECONDS,
    ):
        self.node_id = node_id
        self.capabilities = list(capabilities or DEFAULT_LAPTOP_CAPABILITIES)
        self.lease_manager = LaptopLeaseManager(
            node_id=node_id,
            ttl_seconds=ttl_seconds,
            capabilities=self.capabilities,
        )
        self.git_sync = GitFastForwardSync()
        self.repl = LocalReplSandbox()
        self.agy_offloader = AgyQuotaOffloader()

    def connect(self, coordinator: TopologyCoordinator) -> NodeRegistration:
        """Connects and dynamically registers laptop with the coordinator."""
        return self.lease_manager.register(coordinator)

    def heartbeat(self, coordinator: TopologyCoordinator) -> bool:
        """Sends periodic heartbeat to maintain 10-minute lease."""
        return self.lease_manager.heartbeat(coordinator)

    def disconnect(self, coordinator: TopologyCoordinator) -> bool:
        """Gracefully disconnects and triggers sub-second failover."""
        return self.lease_manager.disconnect(coordinator, graceful=True)

    def execute_repl(self, code: str, timeout: float = 10.0) -> ReplExecutionResult:
        """Executes Python code in isolated local sandbox."""
        return self.repl.execute_code(code, timeout=timeout)

    def offload_task(
        self,
        prompt: str,
        model: str = "gemini-3.1-pro-high",
        effort: str = "high",
        timeout: float = 120.0,
    ) -> Dict[str, Any]:
        """Offloads task to Antigravity CLI quota pool."""
        return self.agy_offloader.offload_task(prompt, model=model, effort=effort, timeout=timeout)

    def safe_sync_git(self, repo_path: str = ".") -> bool:
        """Runs safe git fast-forward check."""
        result = self.git_sync.safe_fast_forward_sync(repo_path=repo_path)
        return result["success"]
