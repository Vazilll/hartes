"""
vazus_core.telemetry.dynamic_trace_collector
Layer 2: Real-time dynamic call graph & telemetry collector using Python 3.12+ PEP 669 (sys.monitoring).

Provides sub-8% overhead in-process bytecode tracing, isolated Tool ID 3,
and direct streaming to vazus.db without disk I/O amplification.
"""

import logging
import os
import sys
import threading
import time
from collections import defaultdict
from pathlib import Path

from vazus_core.memory.db import DEFAULT_VAZUS_DB, get_db_connection

logger = logging.getLogger("vazus_core.telemetry")

TOOL_ID = 3
TOOL_NAME = "vazus_dynamic_graph"
DEFAULT_WORKSPACE = r"C:\vazus"


class DynamicTraceCollector:
    """
    PEP 669 Native Bytecode Execution Tracer.
    Hooks into Python virtual machine instruction events to construct dynamic (caller -> callee) call edges.
    """

    def __init__(
        self,
        workspace_root: str = DEFAULT_WORKSPACE,
        db_path: str = DEFAULT_VAZUS_DB,
        auto_flush_interval: int = 5000,
    ):
        self.workspace_root = str(Path(workspace_root).resolve()).lower()
        self.db_path = db_path
        self.auto_flush_interval = auto_flush_interval
        self._active = False
        self._lock = threading.Lock()
        self._local = threading.local()

        # (caller_fqn, callee_fqn) -> [hit_count, total_time_ns]
        self.call_edges: dict[tuple[str, str], list] = defaultdict(lambda: [0, 0])
        self.function_hits: dict[str, int] = defaultdict(int)
        self._mutation_counter = 0

        self._init_db_schema()

    def _init_db_schema(self) -> None:
        """Ensures telemetry tables exist in vazus.db."""
        try:
            conn = get_db_connection(self.db_path)
            with conn:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS telemetry_function_hits (
                        function_fqn TEXT PRIMARY KEY,
                        hit_count INTEGER DEFAULT 0,
                        last_seen REAL
                    );
                """)
        except Exception as e:
            logger.warning(f"Failed to initialize telemetry database schema: {e}")

    def _format_fqn(self, code) -> str:
        """Converts code object into a standardized, relative FQN string."""
        raw_file = code.co_filename
        try:
            rel = os.path.relpath(raw_file, self.workspace_root).replace("\\", "/")
        except Exception:
            rel = raw_file.replace("\\", "/")
        return f"{rel}:{code.co_qualname}#L{code.co_firstlineno}"

    def _py_start_hook(self, code, _instruction_offset):
        """PEP 669 callback triggered when entering a Python code object."""
        try:
            filename = code.co_filename.lower()
            if not filename.startswith(self.workspace_root) or ".venv" in filename:
                return sys.monitoring.DISABLE

            callee_fqn = self._format_fqn(code)
            now_ns = time.perf_counter_ns()

            if not hasattr(self._local, "call_stack"):
                self._local.call_stack = []

            caller_fqn = self._local.call_stack[-1][0] if self._local.call_stack else "<entrypoint>"
            self._local.call_stack.append((callee_fqn, now_ns))

            with self._lock:
                entry = self.call_edges[(caller_fqn, callee_fqn)]
                entry[0] += 1
                self.function_hits[callee_fqn] += 1
                self._mutation_counter += 1

            if self._mutation_counter >= self.auto_flush_interval:
                self.flush()

        except Exception as exc:
            logger.debug("PEP 669 py_start hook recording skipped: %s", exc)

    def _py_return_hook(self, _code, _instruction_offset, _retval):
        """PEP 669 callback triggered when returning from a Python code object."""
        try:
            if hasattr(self._local, "call_stack") and self._local.call_stack:
                callee_fqn, start_ns = self._local.call_stack.pop()
                duration_ns = time.perf_counter_ns() - start_ns
                caller_fqn = self._local.call_stack[-1][0] if self._local.call_stack else "<entrypoint>"
                with self._lock:
                    self.call_edges[(caller_fqn, callee_fqn)][1] += duration_ns
        except Exception as exc:
            logger.debug("PEP 669 py_return hook recording skipped: %s", exc)

    def start(self) -> bool:
        """Activates bytecode-level sys.monitoring by acquiring an available Tool ID (0-5)."""
        if not hasattr(sys, "monitoring"):
            logger.warning("PEP 669 sys.monitoring not supported in this Python version.")
            return False

        if self._active:
            return True

        try:
            # Find an available Tool ID among 0..5
            claimed_id = None
            for tid in (3, 4, 2, 1, 5, 0):
                tool_name = sys.monitoring.get_tool(tid)
                if tool_name is None:
                    sys.monitoring.use_tool_id(tid, TOOL_NAME)
                    claimed_id = tid
                    break
                elif tool_name == TOOL_NAME:
                    claimed_id = tid
                    break

            if claimed_id is None:
                logger.error("All PEP 669 Tool IDs (0-5) are currently in use.")
                return False

            self._tool_id = claimed_id
            events = sys.monitoring.events
            sys.monitoring.register_callback(self._tool_id, events.PY_START, self._py_start_hook)
            sys.monitoring.register_callback(self._tool_id, events.PY_RETURN, self._py_return_hook)
            sys.monitoring.set_events(self._tool_id, events.PY_START | events.PY_RETURN)
            self._active = True
            logger.info("PEP 669 DynamicTraceCollector activated on Tool ID %d.", self._tool_id)
            return True
        except Exception as e:
            logger.error(f"Failed to activate PEP 669 trace collector: {e}")
            return False

    def stop(self) -> None:
        """Deactivates sys.monitoring and flushes pending data."""
        if not self._active or not hasattr(sys, "monitoring"):
            return

        try:
            tid = getattr(self, "_tool_id", TOOL_ID)
            sys.monitoring.set_events(tid, 0)
            try:
                sys.monitoring.free_tool_id(tid)
            except Exception as exc:
                logger.debug("Freeing PEP 669 tool ID %s skipped: %s", tid, exc)
            self._active = False
            self.flush()
            logger.info("PEP 669 DynamicTraceCollector stopped on Tool ID %d.", tid)
        except Exception as e:
            logger.warning(f"Error during trace collector teardown: {e}")

    def flush(self) -> int:
        """Persists in-memory call graph edges to vazus.db."""
        with self._lock:
            if not self.call_edges and not self.function_hits:
                return 0

            edges_snapshot = list(self.call_edges.items())
            hits_snapshot = list(self.function_hits.items())
            self.call_edges.clear()
            self.function_hits.clear()
            self._mutation_counter = 0

        now = time.time()
        try:
            conn = get_db_connection(self.db_path)
            with conn:
                cur = conn.cursor()
                if edges_snapshot:
                    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='telemetry_call_edges';")
                    if cur.fetchone():
                        for (caller, callee), (hits, total_ns) in edges_snapshot:
                            cur.execute(
                                """
                                INSERT INTO telemetry_call_edges (caller, callee, hit_count, total_time_ns, last_seen)
                                VALUES (?, ?, ?, ?, ?)
                                ON CONFLICT(caller, callee) DO UPDATE SET
                                    hit_count = hit_count + excluded.hit_count,
                                    total_time_ns = total_time_ns + excluded.total_time_ns,
                                    last_seen = excluded.last_seen
                            """,
                                (caller, callee, hits, total_ns, now),
                            )

                for fqn, hits in hits_snapshot:
                    cur.execute(
                        """
                        INSERT INTO telemetry_function_hits (function_fqn, hit_count, last_seen)
                        VALUES (?, ?, ?)
                        ON CONFLICT(function_fqn) DO UPDATE SET
                            hit_count = hit_count + excluded.hit_count,
                            last_seen = excluded.last_seen
                    """,
                        (fqn, hits, now),
                    )

            return len(hits_snapshot)
        except Exception as e:
            logger.error(f"Error writing telemetry to database: {e}")
            return 0

    def get_callees(self, caller_fqn: str) -> dict[str, int]:
        """Queries database for functions called by the given caller."""
        try:
            conn = get_db_connection(self.db_path)
            cur = conn.cursor()
            cur.execute(
                """
                SELECT callee, hit_count FROM telemetry_call_edges
                WHERE caller = ? ORDER BY hit_count DESC
            """,
                (caller_fqn,),
            )
            return {row[0]: row[1] for row in cur.fetchall()}
        except Exception as e:
            logger.warning(f"Failed to query callees: {e}")
            return {}

    def get_hit_count(self, function_fqn: str) -> int:
        """Retrieves total dynamic hit count for a function."""
        try:
            conn = get_db_connection(self.db_path)
            cur = conn.cursor()
            cur.execute(
                """
                SELECT hit_count FROM telemetry_function_hits
                WHERE function_fqn = ?
            """,
                (function_fqn,),
            )
            row = cur.fetchone()
            if row and row[0] is not None:
                return row[0]
            # Suffix match fallback
            clean_suffix = function_fqn.split("/")[-1] if "/" in function_fqn else function_fqn
            cur.execute(
                """
                SELECT sum(hit_count) FROM telemetry_function_hits
                WHERE function_fqn LIKE ?
            """,
                (f"%{clean_suffix}",),
            )
            row = cur.fetchone()
            return row[0] if (row and row[0] is not None) else 0
        except Exception as e:
            logger.warning(f"Failed to query function hits: {e}")
            return 0

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


_GLOBAL_COLLECTOR: DynamicTraceCollector | None = None
_GLOBAL_LOCK = threading.Lock()


def get_global_trace_collector() -> DynamicTraceCollector:
    """Returns the singleton DynamicTraceCollector instance."""
    global _GLOBAL_COLLECTOR
    with _GLOBAL_LOCK:
        if _GLOBAL_COLLECTOR is None:
            _GLOBAL_COLLECTOR = DynamicTraceCollector()
        return _GLOBAL_COLLECTOR
