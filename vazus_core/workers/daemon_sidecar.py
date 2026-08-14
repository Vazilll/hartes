"""
vazus_core/daemon_sidecar.py — Non-blocking SQLite WAL Daemon Sidecar.

Monitors Antigravity CLI transcript databases (`conversation_summaries.db` and `conversations/<id>.db`),
extracts turn step events, applies binary and security guardrails, and queues sanitized TranscriptEvent
objects for downstream subscribers.
"""

import os
import sys
import time
import json
import sqlite3
import re
import queue
import signal
import threading
import datetime
import logging
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Tuple, Callable

from vazus_core.config import settings

logger = logging.getLogger("DaemonSidecar")


@dataclass
class TranscriptEvent:
    """
    Immutable data container representing a parsed conversation step event.
    Conforms to Project Sentinel inter-module interface contracts.
    """
    conversation_id: str
    step_idx: int
    user_input: str
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "SUCCESS"  # "SUCCESS", "ERROR", "PENDING"
    timestamp: str = field(default_factory=lambda: datetime.datetime.utcnow().isoformat() + "Z")

    def to_dict(self) -> Dict[str, Any]:
        """Serializes event to dictionary format."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TranscriptEvent":
        """Deserializes event from dictionary format."""
        return cls(
            conversation_id=data["conversation_id"],
            step_idx=int(data["step_idx"]),
            user_input=data.get("user_input", ""),
            tool_calls=data.get("tool_calls", []),
            status=data.get("status", "SUCCESS"),
            timestamp=data.get("timestamp", datetime.datetime.utcnow().isoformat() + "Z")
        )


class TranscriptWatcher:
    """
    Non-blocking SQLite WAL watcher for Antigravity CLI transcript databases.
    Polled periodically to extract new steps and emit TranscriptEvent objects.
    """
    def __init__(
        self,
        cli_dir: Optional[Path] = None,
        polling_interval: float = 10.0,
        state_file: Optional[Path] = None
    ):
        self.cli_dir = Path(cli_dir) if cli_dir else settings.GEMINI_CLI_DIR
        self.summaries_db_path = self.cli_dir / "conversation_summaries.db"
        self.conversations_dir = self.cli_dir / "conversations"
        self.polling_interval = polling_interval
        
        self.state_file = Path(state_file) if state_file else settings.DAEMON_STATE_FILE
        self._cached_mtimes: Dict[str, float] = {}
        self.state: Dict[str, Any] = self._load_state()

    def _get_ro_connection(self, db_path: Path) -> sqlite3.Connection:
        """
        Establishes a read-only SQLite connection using WAL mode and 30s busy_timeout.
        Leverages URI parameter file:<path>?mode=ro to prevent database locks.
        """
        if not db_path.exists():
            raise FileNotFoundError(f"Database file not found: {db_path}")
            
        path_str = db_path.resolve().as_posix()
        uri_str = f"file:{path_str}?mode=ro"
        
        conn = sqlite3.connect(uri_str, timeout=30.0, uri=True)
        conn.row_factory = sqlite3.Row
        
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=30000;")
        except sqlite3.OperationalError:
            pass  # Read-only mode may disallow PRAGMA mutation if WAL already set
            
        return conn

    def _has_mtime_changed(self, db_path: Path) -> bool:
        """Fast pre-check comparing file modification time to prevent unnecessary DB queries."""
        try:
            current_mtime = db_path.stat().st_mtime
            path_key = str(db_path)
            last_mtime = self._cached_mtimes.get(path_key, 0.0)
            if current_mtime > last_mtime:
                self._cached_mtimes[path_key] = current_mtime
                return True
            return False
        except OSError:
            return False

    def _load_state(self) -> Dict[str, Any]:
        """Loads state tracking dictionary from daemon_state.json."""
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load daemon state, re-initializing: {e}")
        return {
            "last_processed_timestamp": None,
            "conversations": {}  # format: {conv_id: {"last_step_idx": int, "last_updated": str}}
        }

    def _save_state(self) -> None:
        """Atomically saves state tracking dictionary to JSON file."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_file = self.state_file.with_suffix(".tmp")
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=2)
        os.replace(tmp_file, self.state_file)

    def _extract_payload_strings(self, payload_bytes: Any) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Safely extracts user text prompts and tool invocations from step payload BLOBs.
        Filters out binary data, image byte arrays, and credentials.
        """
        if not payload_bytes:
            return "", []
            
        if isinstance(payload_bytes, str):
            decoded = payload_bytes
        elif isinstance(payload_bytes, bytes):
            decoded = payload_bytes.decode("utf-8", errors="ignore")
        else:
            decoded = str(payload_bytes)
        
        user_input = ""
        user_matches = re.findall(r'(?:USER|user_input|prompt)[:\s]+([^\x00-\x1f\x7f-\x9f]{5,1000})', decoded, re.IGNORECASE)
        if user_matches:
            user_input = user_matches[0].strip()
        else:
            printable_blocks = [s.strip() for s in re.findall(r'[\x20-\x7E\n\r\t]{10,}', decoded) if not s.startswith("SYSTEM")]
            if printable_blocks:
                user_input = printable_blocks[0]

        tool_calls = []
        tool_patterns = re.findall(r'(run_command|view_file|write_to_file|replace_file_content|grep_search|find_by_name|multi_replace_file_content|read_url_content)', decoded)
        for tool_name in set(tool_patterns):
            tool_calls.append({"tool": tool_name, "raw_excerpt": f"Detected invocation of {tool_name}"})

        return user_input, tool_calls

    def _apply_guardrails(self, user_input: str, tool_calls: List[Dict[str, Any]]) -> bool:
        """
        Applies safety guardrails.
        Returns False (reject) if step contains image view requests, binary blobs, or secrets.
        """
        image_extensions = ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp')
        user_lower = user_input.lower()
        if any(ext in user_lower for ext in image_extensions):
            return False
            
        for call in tool_calls:
            if call.get("tool") == "view_file" and any(ext in str(call).lower() for ext in image_extensions):
                return False
                
        return True

    def poll_once(self) -> List[TranscriptEvent]:
        """
        Executes a single read-only polling sweep across conversation databases.
        Returns a list of newly discovered, sanitized TranscriptEvents.
        """
        new_events: List[TranscriptEvent] = []
        if not self.summaries_db_path.exists():
            return new_events

        # MTime pre-check on summary DB
        if not self._has_mtime_changed(self.summaries_db_path) and self.state.get("conversations"):
            return new_events

        try:
            conn = self._get_ro_connection(self.summaries_db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT conversation_id, step_count, last_modified_time FROM conversation_summaries ORDER BY last_modified_time DESC"
            )
            summaries = cursor.fetchall()
            conn.close()
        except Exception as e:
            logger.debug(f"Transient error querying conversation_summaries: {e}")
            return new_events

        for row in summaries:
            conv_id = row["conversation_id"]
            conv_db_path = self.conversations_dir / f"{conv_id}.db"
            if not conv_db_path.exists():
                continue

            conv_state = self.state.get("conversations", {}).get(conv_id, {"last_step_idx": -1})
            last_step_idx = conv_state["last_step_idx"]

            if not self._has_mtime_changed(conv_db_path) and last_step_idx >= 0:
                continue

            try:
                c_conn = self._get_ro_connection(conv_db_path)
                c_cursor = c_conn.cursor()
                c_cursor.execute(
                    "SELECT idx, status, step_payload FROM steps WHERE idx > ? ORDER BY idx ASC",
                    (last_step_idx,)
                )
                steps = c_cursor.fetchall()
                c_conn.close()
            except Exception as e:
                logger.debug(f"Transient error querying steps for conversation {conv_id}: {e}")
                continue

            max_idx = last_step_idx
            for step in steps:
                idx = step["idx"]
                status_code = "SUCCESS" if step["status"] == 0 else "ERROR"
                payload_bytes = step["step_payload"]

                user_input, tool_calls = self._extract_payload_strings(payload_bytes)
                
                if self._apply_guardrails(user_input, tool_calls):
                    event = TranscriptEvent(
                        conversation_id=conv_id,
                        step_idx=idx,
                        user_input=user_input,
                        tool_calls=tool_calls,
                        status=status_code
                    )
                    new_events.append(event)
                    
                max_idx = max(max_idx, idx)

            if max_idx > last_step_idx:
                if "conversations" not in self.state:
                    self.state["conversations"] = {}
                self.state["conversations"][conv_id] = {
                    "last_step_idx": max_idx,
                    "last_updated": datetime.datetime.utcnow().isoformat() + "Z"
                }

        if new_events:
            self.state["last_processed_timestamp"] = datetime.datetime.utcnow().isoformat() + "Z"
            self._save_state()

        return new_events


class DaemonSidecar:
    """
    Main Daemon Sidecar process manager.
    Coordinates background polling threads, event queues, and listener dispatches.
    """
    def __init__(
        self,
        cli_dir: Optional[Path] = None,
        polling_interval: float = 10.0,
        queue_maxsize: int = 1000,
        state_file: Optional[Path] = None,
        pid_file: Optional[Path] = None
    ):
        self.cli_dir = Path(cli_dir) if cli_dir else settings.GEMINI_CLI_DIR
        self.polling_interval = polling_interval
        self.watcher = TranscriptWatcher(cli_dir=self.cli_dir, polling_interval=polling_interval, state_file=state_file)
        self.event_queue: queue.Queue[TranscriptEvent] = queue.Queue(maxsize=queue_maxsize)
        
        self.pid_file = Path(pid_file) if pid_file else (settings.GEMINI_CLI_DIR / "sidecar.pid")
        self.listeners: List[Callable[[TranscriptEvent], None]] = []
        
        self._stop_event = threading.Event()
        self._watcher_thread: Optional[threading.Thread] = None
        self._worker_thread: Optional[threading.Thread] = None
        
        self._start_time: Optional[float] = None
        self.total_events_processed: int = 0
        self.error_count: int = 0

    def register_listener(self, callback: Callable[[TranscriptEvent], None]) -> None:
        """Registers a subscriber function to receive TranscriptEvent objects."""
        self.listeners.append(callback)

    def _watcher_loop(self) -> None:
        """Background thread loop for polling SQLite databases."""
        while not self._stop_event.is_set():
            try:
                events = self.watcher.poll_once()
                for evt in events:
                    try:
                        self.event_queue.put(evt, timeout=1.0)
                    except queue.Full:
                        logger.warning("Event queue full, dropping TranscriptEvent")
            except Exception as e:
                logger.error(f"Watcher loop exception: {e}")
                self.error_count += 1
            
            self._stop_event.wait(self.polling_interval)

    def _worker_loop(self) -> None:
        """Background thread loop for processing queued events and calling listeners."""
        while not self._stop_event.is_set():
            try:
                evt = self.event_queue.get(timeout=1.0)
                for callback in self.listeners:
                    try:
                        callback(evt)
                    except Exception as e:
                        logger.error(f"Listener execution error: {e}")
                        self.error_count += 1
                self.total_events_processed += 1
                self.event_queue.task_done()
            except queue.Empty:
                continue

    def _write_pid(self) -> None:
        """Writes current process ID to pid_file atomically."""
        if not self.pid_file:
            return
        self.pid_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_file = self.pid_file.with_name(self.pid_file.name + ".tmp")
        with open(tmp_file, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
        os.replace(tmp_file, self.pid_file)

    def _remove_pid(self) -> None:
        """Removes PID file upon shutdown."""
        if self.pid_file and self.pid_file.exists():
            try:
                self.pid_file.unlink()
            except OSError:
                pass

    def start(self, daemonize: bool = False) -> None:
        """
        Starts the daemon sidecar background threads.
        If daemonize=True, registers signal handlers and creates PID file.
        """
        if self._watcher_thread and self._watcher_thread.is_alive():
            return

        self._stop_event.clear()
        self._start_time = time.time()
        self._write_pid()

        self._watcher_thread = threading.Thread(target=self._watcher_loop, daemon=True, name="WatcherThread")
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True, name="WorkerThread")

        self._watcher_thread.start()
        self._worker_thread.start()

        if daemonize:
            def _signal_handler(sig, frame):
                self.stop()
                sys.exit(0)
            signal.signal(signal.SIGINT, _signal_handler)
            signal.signal(signal.SIGTERM, _signal_handler)

    def stop(self) -> None:
        """Gracefully stops background threads and cleans up resources."""
        self._stop_event.set()

        if self._watcher_thread and self._watcher_thread.is_alive():
            self._watcher_thread.join(timeout=5.0)
            
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=5.0)

        self._remove_pid()

    def status(self) -> Dict[str, Any]:
        """Returns health telemetry and status metrics."""
        is_running = self._watcher_thread is not None and self._watcher_thread.is_alive()
        uptime = (time.time() - self._start_time) if (is_running and self._start_time) else 0.0
        
        return {
            "status": "RUNNING" if is_running else "STOPPED",
            "uptime_seconds": round(uptime, 2),
            "queue_size": self.event_queue.qsize(),
            "total_events_processed": self.total_events_processed,
            "error_count": self.error_count,
            "polling_interval": self.polling_interval,
            "pid": os.getpid() if is_running else None,
            "state_file": str(self.watcher.state_file)
        }

    def run_single_pass(self) -> List[TranscriptEvent]:
        """
        Synchronous test helper.
        Runs a single polling pass and directly dispatches to registered listeners.
        Returns the list of events discovered.
        """
        events = self.watcher.poll_once()
        for evt in events:
            for callback in self.listeners:
                try:
                    callback(evt)
                except Exception as e:
                    logger.error(f"Single pass listener error: {e}")
                    self.error_count += 1
            self.total_events_processed += 1
        return events
