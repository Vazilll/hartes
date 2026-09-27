"""
vazus_autonomous_harness.daemon.autonomous_flywheel — Always-On Autonomous Execution Flywheel.

Replaces static / manual test execution with a continuous background loop that:
1. Collects live system health and verifies SMT Z3 constraints every cycle.
2. Synchronizes status and structured directives to Google Drive (`G:\\My Drive\\HartesFlywheel`).
3. Actively monitors and processes Gemini Spark directives (`spark_inbox`).
4. Generates RFC resolutions and solutions via `AgyPlanner` (using local agy.exe on IDE quota).
5. Writes completed resolutions to `spark_outbox` for Gemini Spark in Google Cloud.
6. Inspects Colab GPU queue and VPS node topology.
7. Protects against thrashing and deadlocks via `AntiThrashingCircuitBreaker`.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import signal
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from llm.agy_planner import AgyPlanner
from vazus_autonomous_harness.daemon.vps_daemon import VpsDaemon
from vazus_autonomous_harness.engine.anti_thrashing import (
    AntiThrashingCircuitBreaker,
    TaskAttempt,
)
from vazus_autonomous_harness.telemetry.cloud_bridge import (
    CloudTelemetryBridge,
    DEFAULT_DRIVE_ROOT,
    LOCAL_FALLBACK_ROOT,
    SystemHealthReport,
)

logger = logging.getLogger("hartes.flywheel.daemon")


@dataclass
class CycleResult:
    cycle: int
    timestamp: float
    iso_time: str
    health_status: str
    z3_gate_ok: bool
    spark_directives_pending: int
    spark_directives_processed: int
    colab_jobs_pending: int
    active_nodes_count: int
    memory_rss_mb: float
    duration_s: float
    details: Dict[str, Any] = field(default_factory=dict)


class AutonomousFlywheelDaemon:
    """
    Always-on background daemon powering the autonomous self-improvement flywheel.
    Runs continuously, coordinating local compute, Google Drive, Gemini Spark, and Colab.
    """

    def __init__(
        self,
        interval_seconds: float = 30.0,
        drive_root: Optional[Path] = None,
        model: str = "flash-fast",
        max_cycles: Optional[int] = None,
    ):
        self.interval_seconds = interval_seconds
        self.max_cycles = max_cycles
        self.drive_root = drive_root or (
            DEFAULT_DRIVE_ROOT if DEFAULT_DRIVE_ROOT.parent.exists() else LOCAL_FALLBACK_ROOT
        )
        self.model = model

        # Subsystems
        self.telemetry = CloudTelemetryBridge(drive_root=self.drive_root)
        self.vps_daemon = VpsDaemon()
        self.planner = AgyPlanner(model=self.model, timeout_seconds=120.0)
        self.circuit_breaker = AntiThrashingCircuitBreaker()

        # Queues
        self.inbox_dir = self.drive_root / "spark_inbox"
        self.outbox_dir = self.drive_root / "spark_outbox"
        self._ensure_queues()

        # State
        self.running = False
        self.cycle_count = 0
        self.start_time = 0.0
        self.history: List[CycleResult] = []

    def _ensure_queues(self) -> None:
        self.inbox_dir.mkdir(parents=True, exist_ok=True)
        self.outbox_dir.mkdir(parents=True, exist_ok=True)

    def run_cycle(self) -> CycleResult:
        """
        Executes a single autonomous iteration:
        1. Collect telemetry & verify SMT Z3
        2. Sync status to Google Drive (SYSTEM_HEALTH.json, SYSTEM_STATUS.md)
        3. Poll and process spark_inbox
        4. Poll colab queue
        5. Check VPS daemon tick and memory
        """
        t0 = time.perf_counter()
        self.cycle_count += 1
        now = time.time()
        iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))

        logger.info("── Autonomous Cycle #%d [%s] ──", self.cycle_count, iso)

        # Step 1: Health check & SMT Z3 guard
        health = self.telemetry.collect_health()

        # Step 2: Push telemetry sync to Drive
        self.telemetry.sync_to_cloud(health)

        # Step 3: Process pending Spark directives
        processed_count = 0
        inbox_dirs = [self.inbox_dir]
        local_inbox = self.telemetry.local_root / "spark_inbox"
        if local_inbox != self.inbox_dir:
            inbox_dirs.append(local_inbox)

        pending_directives = []
        for d in inbox_dirs:
            if d.exists():
                pending_directives.extend(list(d.glob("*.json")))

        # Process at most 1 directive per cycle to guarantee fast loop completion
        for directive_file in pending_directives[:1]:
            try:
                with open(directive_file, "r", encoding="utf-8") as f:
                    directive = json.load(f)

                directive_id = directive.get("directive_id", directive_file.stem)
                logger.info(
                    "Processing Spark directive: %s (Title: %s)",
                    directive_id,
                    directive.get("title"),
                )

                # Solve directive via AgyPlanner
                prompt = (
                    "[INSTRUCTION]: You are the Autonomous Remediation Engine of Vazus OS.\n"
                    "Output ONLY concise markdown text and python code remediation.\n"
                    "Do NOT execute terminal commands or invoke any tools.\n\n"
                    f"Direct Action Directive from Gemini Spark:\n"
                    f"Title: {directive.get('title')}\n"
                    f"Context: {directive.get('context')}\n"
                    f"Suggested Action: {directive.get('suggested_action')}\n"
                    f"Trace: {directive.get('trace')}\n\n"
                    "Provide a concrete remediation plan and code patch."
                )

                plan = self.planner.plan(prompt, history=[])
                resolution = {
                    "directive_id": directive_id,
                    "resolved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "status": "RESOLVED",
                    "model_used": plan.get("model"),
                    "remediation_plan": plan.get("response"),
                    "target_notebook_id": directive.get("target_notebook_id"),
                }

                # Save solution to spark_outbox
                out_path = self.outbox_dir / f"resolution_{directive_id}.json"
                with open(out_path, "w", encoding="utf-8") as out_f:
                    json.dump(resolution, out_f, indent=2, ensure_ascii=False)

                # Also sync resolution to local outbox if different
                local_outbox = self.telemetry.local_root / "spark_outbox"
                if local_outbox != self.outbox_dir:
                    local_outbox.mkdir(parents=True, exist_ok=True)
                    with open(local_outbox / f"resolution_{directive_id}.json", "w", encoding="utf-8") as out_f:
                        json.dump(resolution, out_f, indent=2, ensure_ascii=False)

                # Remove from inbox (claim complete)
                directive_file.unlink(missing_ok=True)
                processed_count += 1
                logger.info("Successfully resolved Spark directive %s -> %s", directive_id, out_path.name)
                
                attempt = TaskAttempt(
                    task_id=directive_id,
                    cycle_number=self.cycle_count,
                    score=100.0,  # resolved = full score
                    code_hash=hashlib.md5(plan.get('response', '').encode()).hexdigest(),
                    error_message=None,
                    missing_prerequisite=None,
                )
                self.circuit_breaker.record_attempt(attempt)
            except Exception as exc:
                logger.error("Error processing Spark directive %s: %s", directive_file, exc)
                # Archive failed directive to prevent infinite retry blocking
                err_path = self.outbox_dir / f"quarantined_{directive_file.name}"
                try:
                    directive_file.rename(err_path)
                except Exception:
                    directive_file.unlink(missing_ok=True)
                    
                attempt = TaskAttempt(
                    task_id=directive_id if 'directive_id' in locals() else directive_file.stem,
                    cycle_number=self.cycle_count,
                    score=0.0,
                    code_hash='error',
                    error_message=str(exc),
                    missing_prerequisite=None,
                )
                tripped = self.circuit_breaker.record_attempt(attempt)
                if tripped:
                    logger.warning("Circuit breaker TRIPPED for %s — escalating to Jules", directive_file.name)
                    safe_directive = directive if 'directive' in locals() else {}
                    self._escalate_to_jules(safe_directive, str(exc))

                # Record reflexion for future pre-flight filtering
                try:
                    from vazus_autonomous_harness.memory.reflexion_engine import ContinuousReflexionGenerator
                    from vazus_autonomous_harness.memory.episodic_store import EpisodicMemoryStore
                    import traceback
                    generator = ContinuousReflexionGenerator()
                    safe_directive = directive if 'directive' in locals() else {}
                    record = generator.from_exception(
                        task_id=safe_directive.get('directive_id', directive_file.stem),
                        candidate_code=json.dumps(safe_directive, ensure_ascii=False)[:500],
                        exc=exc,
                        traceback_str=traceback.format_exc(),
                    )
                    mem_store = EpisodicMemoryStore()
                    mem_store.record_failure(record)
                except Exception:
                    pass  # reflexion is best-effort

        # Step 4: VPS Daemon Tick (memory & colab queue)
        vps_tick = self.vps_daemon.tick()
        active_nodes = vps_tick.get("nodes", {}).get("active_count", 0)
        colab_summary = vps_tick.get("colab", {})
        colab_pending = colab_summary.get("pending_count", 0)
        rss_mb = vps_tick.get("memory", {}).get("rss_mb", 0.0)

        elapsed = time.perf_counter() - t0

        result = CycleResult(
            cycle=self.cycle_count,
            timestamp=now,
            iso_time=iso,
            health_status=health.status,
            z3_gate_ok=health.z3_hard_gate_ok,
            spark_directives_pending=len(pending_directives),
            spark_directives_processed=processed_count,
            colab_jobs_pending=colab_pending,
            active_nodes_count=active_nodes,
            memory_rss_mb=rss_mb,
            duration_s=round(elapsed, 2),
            details={
                "z3_latency_ms": health.z3_latency_ms,
                "total_skills": health.total_skills,
            },
        )
        self.history.append(result)

        # Persist daemon status heartbeat
        self._write_heartbeat(result)

        logger.info(
            "Cycle #%d completed in %.2fs: status=%s, z3_gate=%s, spark_processed=%d, mem=%.1fMB",
            self.cycle_count,
            elapsed,
            health.status,
            health.z3_hard_gate_ok,
            processed_count,
            rss_mb,
        )
        return result

    def _write_heartbeat(self, result: CycleResult) -> None:
        """Writes latest heartbeat to disk and Google Drive."""
        heartbeat_data = {
            "daemon": "AutonomousFlywheelDaemon",
            "cycle": result.cycle,
            "status": "RUNNING",
            "uptime_seconds": round(time.time() - self.start_time, 1),
            "last_cycle": asdict(result),
        }
        for target in [self.drive_root, self.telemetry.local_root]:
            target.mkdir(parents=True, exist_ok=True)
            hb_file = target / "DAEMON_HEARTBEAT.json"
            try:
                with open(hb_file, "w", encoding="utf-8") as f:
                    json.dump(heartbeat_data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.warning("Could not write heartbeat to %s: %s", hb_file, e)

    def start(self) -> None:
        """Starts the infinite continuous autonomous execution loop."""
        self.running = True
        self.start_time = time.time()
        logger.info(
            "Starting Autonomous Flywheel Daemon (interval=%.1fs, drive=%s, model=%s)",
            self.interval_seconds,
            self.drive_root,
            self.model,
        )

        try:
            while self.running:
                self.run_cycle()

                if self.max_cycles and self.cycle_count >= self.max_cycles:
                    logger.info("Reached maximum configured cycles (%d). Stopping.", self.max_cycles)
                    break

                time.sleep(self.interval_seconds)
        except (KeyboardInterrupt, SystemExit):
            logger.info("Termination signal received. Shutting down daemon gracefully.")
        finally:
            self.running = False
            self._write_shutdown_status()

    def stop(self) -> None:
        """Signals the daemon to stop after the current cycle."""
        self.running = False

    def _write_shutdown_status(self) -> None:
        data = {
            "daemon": "AutonomousFlywheelDaemon",
            "status": "STOPPED",
            "total_cycles": self.cycle_count,
            "stopped_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        for target in [self.drive_root, self.telemetry.local_root]:
            try:
                with open(target / "DAEMON_HEARTBEAT.json", "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            except Exception:
                pass

    def _escalate_to_jules(self, directive: dict, error_msg: str) -> None:
        """Escalates a repeatedly failing directive to Google Jules for async cloud remediation."""
        api_key = os.environ.get("JULES_API_KEY")
        if not api_key:
            logger.warning("JULES_API_KEY not set — skipping Jules escalation.")
            return
        try:
            import httpx
            prompt = (
                f"Anti-thrashing circuit breaker tripped. Autonomous remediation failed repeatedly.\n"
                f"Directive: {directive.get('title', 'unknown')}\n"
                f"Context: {directive.get('context', '')}\n"
                f"Last Error: {error_msg}\n\n"
                f"Analyze the root cause and create a fix with tests."
            )
            payload = {
                "prompt": prompt,
                "title": f"[Hartes Escalation] {directive.get('title', 'unknown')}",
                "requirePlanApproval": False,
            }
            # Check if source context is available
            source_id = directive.get("jules_source_id")
            if source_id:
                payload["sourceContext"] = {
                    "source": source_id,
                    "githubRepoContext": {"startingBranch": "vazus-dev"},
                }
            resp = httpx.post(
                "https://jules.googleapis.com/v1alpha/sessions",
                json=payload,
                headers={"Content-Type": "application/json", "X-Goog-Api-Key": api_key},
                timeout=30.0,
            )
            if resp.status_code < 300:
                session_data = resp.json()
                session_id = session_data.get("id") or session_data.get("name", "").split("/")[-1]
                logger.info("Jules session created: %s", session_id)
                # Write escalation record to outbox
                esc_path = self.outbox_dir / f"escalation_{directive.get('directive_id', 'unknown')}.json"
                with open(esc_path, "w", encoding="utf-8") as ef:
                    json.dump({"jules_session_id": session_id, "directive": directive, "error": error_msg}, ef, indent=2)
            else:
                logger.error("Jules API error %d: %s", resp.status_code, resp.text[:200])
        except Exception as e:
            logger.error("Jules escalation failed: %s", e)


def run_daemon_cli(interval: float = 30.0, model: str = "flash-lite", max_cycles: Optional[int] = None) -> None:
    daemon = AutonomousFlywheelDaemon(interval_seconds=interval, model=model, max_cycles=max_cycles)
    daemon.start()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    interval = float(sys.argv[1]) if len(sys.argv) > 1 else 30.0
    run_daemon_cli(interval=interval)
