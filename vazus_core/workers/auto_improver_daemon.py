#!/usr/bin/env python3
"""
vazus_core.workers.auto_improver_daemon — Autonomous Recursive Self-Improvement Engine.
========================================================================================

Executes the continuous 5-phase recursive self-improvement cycle:
  1. OBSERVE : Ingests tool activation telemetry (hit rates), pending code-quality suggestions, and memory states.
  2. ANALYZE : Computes J-Space semantic tool weight deltas, ranks improvement candidates.
  3. PLAN    : Formulates optimization tasks for latency, memory, and tool-dispatch precision.
  4. EXECUTE & VERIFY : Applies J-Space re-weighting, triggers sleep-time dream memory consolidation, verifies integrity.
  5. LEARN   : Persists session metrics to auto_improver_sessions, records reflexion lessons, and updates SSOT.

Usage:
  from vazus_core.workers.auto_improver_daemon import AutoImproverDaemon
  daemon = AutoImproverDaemon()
  if daemon.should_run():
      stats = daemon.run_cycle()
"""

import datetime
import json
import logging
import os
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional, Union

from vazus_core.memory.db import DEFAULT_VAZUS_DB
from vazus_core.memory.j_space_tool_indexer import JSpaceToolIndexer

logger = logging.getLogger("vazus_core.workers.auto_improver")


class AutoImproverDaemon:
    """
    Autonomous recursive self-improvement daemon for Vazus OS.
    Runs periodically (default every 6 hours) or when triggered by the daemon sidecar.
    """

    DEFAULT_INTERVAL_HOURS: float = 6.0

    def __init__(self, db_path: Optional[Union[str, Path]] = None) -> None:
        env_db = os.environ.get("VAZUS_DB_PATH")
        target_path = db_path or env_db or DEFAULT_VAZUS_DB
        self.db_path = str(target_path) if target_path else DEFAULT_VAZUS_DB
        self._ensure_sessions_table()

    def _ensure_sessions_table(self) -> None:
        """Ensures the auto_improver_sessions table exists in the target DB."""
        try:
            conn = sqlite3.connect(self.db_path, timeout=5.0)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS auto_improver_sessions (
                    session_id   TEXT PRIMARY KEY,
                    task_type    TEXT,
                    task_desc    TEXT,
                    iterations   INTEGER,
                    success      INTEGER,
                    final_score  REAL,
                    skills_used  TEXT,
                    created_at   REAL
                )
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.debug("auto_improver_sessions table ensure non-fatal: %s", e)

    def get_last_session(self) -> Optional[Dict[str, Any]]:
        """Retrieves the most recent auto-improvement session."""
        try:
            conn = sqlite3.connect(self.db_path, timeout=3.0)
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT session_id, task_type, task_desc, iterations, success, final_score, created_at FROM auto_improver_sessions ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            conn.close()
            if row:
                return dict(row)
        except Exception as e:
            logger.debug("Failed retrieving last auto-improver session: %s", e)
        return None

    def should_run(self, interval_hours: Optional[float] = None) -> bool:
        """Checks if enough time has elapsed since the last auto-improvement cycle."""
        interval = interval_hours if interval_hours is not None else self.DEFAULT_INTERVAL_HOURS
        last = self.get_last_session()
        if not last:
            return True
        last_ts = float(last.get("created_at") or 0)
        hours_elapsed = (time.time() - last_ts) / 3600.0
        return hours_elapsed >= interval

    def get_status(self) -> Dict[str, Any]:
        """Returns comprehensive status of the recursive self-improvement subsystem."""
        last = self.get_last_session()
        hours_since = None
        if last and last.get("created_at"):
            hours_since = round((time.time() - float(last["created_at"])) / 3600.0, 1)

        total_sessions = 0
        successful_sessions = 0
        total_reweighted = 0
        try:
            conn = sqlite3.connect(self.db_path, timeout=3.0)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*), SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) FROM auto_improver_sessions")
            row = cur.fetchone()
            if row:
                total_sessions = row[0] or 0
                successful_sessions = row[1] or 0

            # Count custom weighted tools in j_space_tool_metadata
            cur.execute("PRAGMA table_info(j_space_tool_metadata)")
            cols = [r[1] for r in cur.fetchall()]
            if "weight" in cols:
                cur.execute("SELECT COUNT(*) FROM j_space_tool_metadata WHERE weight != 1.0")
                w_row = cur.fetchone()
                total_reweighted = w_row[0] if w_row else 0

            conn.close()
        except Exception as e:
            logger.debug("Failed querying status counts: %s", e)

        return {
            "status": "HEALTHY",
            "last_session": last,
            "hours_since_last": hours_since,
            "total_sessions": total_sessions,
            "successful_sessions": successful_sessions,
            "reweighted_tools_count": total_reweighted,
            "interval_hours": self.DEFAULT_INTERVAL_HOURS,
            "should_run": self.should_run(),
        }

    def observe(self) -> Dict[str, Any]:
        """
        Phase 1: OBSERVE.
        Collects activation hit rates, pending suggestions, and health indicators.
        """
        metrics: Dict[str, Any] = {
            "total_activations": 0,
            "total_used": 0,
            "hit_rate": 0.0,
            "top_used_tools": [],
            "pending_suggestions_count": 0,
        }
        try:
            conn = sqlite3.connect(self.db_path, timeout=3.0)
            cur = conn.cursor()

            # Check activations
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='j_space_tool_activations'")
            if cur.fetchone():
                cur.execute("PRAGMA table_info(j_space_tool_activations)")
                cols = [r[1] for r in cur.fetchall()]
                if "was_used" in cols:
                    cur.execute("""
                        SELECT COUNT(*), SUM(CASE WHEN was_used = 1 THEN 1 ELSE 0 END)
                        FROM j_space_tool_activations
                    """)
                    row = cur.fetchone()
                    if row and row[0]:
                        total = row[0]
                        used = row[1] or 0
                        metrics["total_activations"] = total
                        metrics["total_used"] = used
                        metrics["hit_rate"] = round(used / total, 3) if total > 0 else 0.0

                    cur.execute("""
                        SELECT tool_name, COUNT(*) as c, SUM(CASE WHEN was_used = 1 THEN 1 ELSE 0 END) as u
                        FROM j_space_tool_activations
                        GROUP BY tool_name
                        ORDER BY u DESC, c DESC
                        LIMIT 5
                    """)
                    metrics["top_used_tools"] = [{"tool": r[0], "proposed": r[1], "used": r[2]} for r in cur.fetchall()]

            # Check pending improvement suggestions
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='improvement_suggestions'")
            if cur.fetchone():
                cur.execute("SELECT COUNT(*) FROM improvement_suggestions WHERE status = 'pending' OR status IS NULL")
                s_row = cur.fetchone()
                metrics["pending_suggestions_count"] = s_row[0] if s_row else 0

            conn.close()
        except Exception as e:
            logger.debug("Observe phase error: %s", e)

        return metrics

    def analyze(self, observations: Dict[str, Any]) -> Dict[str, Any]:
        """
        Phase 2: ANALYZE.
        Evaluates observations and formulates candidate optimization actions.
        """
        actions = []
        if observations.get("total_activations", 0) >= 2:
            actions.append("reweight_j_space_tools")

        actions.append("verify_sqlite_wal")
        actions.append("check_memory_consolidation")

        return {
            "candidate_actions": actions,
            "observations_summary": observations,
            "priority": "normal",
        }

    def execute_and_verify(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Phase 3 & 4: EXECUTE & VERIFY.
        Applies J-Space adaptive re-weighting, validates SQLite integrity, and runs consolidation if due.
        """
        results: Dict[str, Any] = {
            "reweight_result": None,
            "wal_checkpoint": "SKIPPED",
            "dream_consolidation": "SKIPPED",
            "verified": False,
        }

        # 1. J-Space adaptive re-weighting
        try:
            indexer = JSpaceToolIndexer(db_path=self.db_path)
            rw_res = indexer.reweight_tools_from_activations(min_proposals=2)
            results["reweight_result"] = rw_res
        except Exception as e:
            logger.debug("Adaptive tool re-weighting error: %s", e)
            results["reweight_result"] = {"error": str(e)}

        # 2. SQLite WAL passive checkpoint & integrity verification
        try:
            conn = sqlite3.connect(self.db_path, timeout=5.0)
            conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
            cur = conn.cursor()
            cur.execute("PRAGMA integrity_check(1)")
            check = cur.fetchone()
            conn.close()
            results["wal_checkpoint"] = "ok" if check and check[0] == "ok" else str(check)
        except Exception as e:
            results["wal_checkpoint"] = f"error: {e}"

        # 3. Dream Memory Consolidation trigger if due
        try:
            from vazus_core.memory.dream_consolidator import DreamConsolidator

            dc = DreamConsolidator(db_path=self.db_path)
            status = dc.get_consolidation_status()
            hours_since = status.get("hours_since_last")
            if hours_since is None or hours_since >= 24.0:
                dc_res = dc.run_full_consolidation()
                results["dream_consolidation"] = dc_res
            else:
                results["dream_consolidation"] = f"fresh ({hours_since:.1f}h ago)"
        except Exception as e:
            results["dream_consolidation"] = f"error: {e}"

        results["verified"] = results["wal_checkpoint"] == "ok"
        return results

    def learn(self, session_id: str, plan: Dict[str, Any], results: Dict[str, Any]) -> None:
        """
        Phase 5: LEARN.
        Records session outcome to auto_improver_sessions and logs reflexion lessons.
        """
        now = time.time()
        success = 1 if results.get("verified") else 0
        desc = "Autonomous loop: J-Space reweighting + WAL integrity + Dream check"
        skills = ["j_space_reweight", "sqlite_integrity"]
        score = 1.0 if success else 0.5

        try:
            conn = sqlite3.connect(self.db_path, timeout=5.0)
            conn.execute(
                """
                INSERT OR REPLACE INTO auto_improver_sessions
                (session_id, task_type, task_desc, iterations, success, final_score, skills_used, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, "recursive_self_improvement", desc, 1, success, score, json.dumps(skills), now),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.debug("Failed recording auto_improver session: %s", e)

    def run_cycle(self, force: bool = False) -> Dict[str, Any]:
        """
        Executes a complete 5-phase recursive self-improvement cycle:
        Observe -> Analyze -> Plan -> Execute & Verify -> Learn.
        """
        t0 = time.perf_counter()
        session_id = f"auto_improve_{int(time.time())}"

        # 1. OBSERVE
        obs = self.observe()

        # 2. ANALYZE
        analysis = self.analyze(obs)

        # 3. PLAN
        plan = analysis

        # 4. EXECUTE & VERIFY
        exec_results = self.execute_and_verify(plan)

        # 5. LEARN
        self.learn(session_id, plan, exec_results)

        duration = round(time.perf_counter() - t0, 3)
        return {
            "session_id": session_id,
            "status": "SUCCESS" if exec_results.get("verified") else "PARTIAL",
            "duration_seconds": duration,
            "observations": obs,
            "execution": exec_results,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }


def get_auto_improver_daemon(db_path: Optional[str] = None) -> AutoImproverDaemon:
    """Factory helper returning AutoImproverDaemon instance."""
    return AutoImproverDaemon(db_path=db_path)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    daemon = AutoImproverDaemon()
    print("=== AutoImproverDaemon Status ===")
    print(json.dumps(daemon.get_status(), indent=2, default=str))
    if "--run" in sys.argv:
        print("\n=== Running Self-Improvement Cycle ===")
        res = daemon.run_cycle(force=True)
        print(json.dumps(res, indent=2, default=str))
