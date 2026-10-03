"""
Robust SQLite Connection Pool with WAL2, busy timeouts, and NTFS lock prevention.
"""

import logging
import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Union

logger = logging.getLogger(__name__)


class RobustSQLitePool:
    """
    Thread-safe, WAL-enabled SQLite connection pool designed to prevent WinError 32 on Windows NTFS.
    """

    def __init__(
        self,
        db_path: Union[str, Path],
        busy_timeout_ms: int = 10000,
        mmap_size_bytes: int = 2147483648,  # 2 GB
        autocommit: bool = True,
    ):
        path_str = str(Path(db_path).resolve())
        if os.getenv("VAZUS_TEST_ISOLATION") == "1" and path_str != ":memory:":
            try:
                canonical_resolved = str(Path(r"C:\vazus\services\memory\vazus.db").resolve()).lower()
                target_resolved = path_str.lower()
                if target_resolved == canonical_resolved or target_resolved.replace("\\", "/").endswith(
                    "services/memory/vazus.db"
                ):
                    isolated_env = os.getenv("VAZUS_DB_PATH")
                    if isolated_env:
                        iso_resolved = str(Path(isolated_env).resolve()).lower()
                        if iso_resolved != canonical_resolved and not iso_resolved.replace("\\", "/").endswith(
                            "services/memory/vazus.db"
                        ):
                            path_str = str(Path(isolated_env).resolve())
            except Exception as exc:
                logger.debug("Failed test isolation path resolution: %s", exc)
        self.db_path = path_str
        self.busy_timeout_ms = busy_timeout_ms
        self.mmap_size_bytes = mmap_size_bytes
        self.autocommit = autocommit
        self._local = threading.local()
        self._init_lock = threading.Lock()

        # Ensure parent directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_pragmas()

    def _init_pragmas(self):
        """Initializes database pragmas for high concurrency and resilience."""
        with self._init_lock:
            conn = sqlite3.connect(self.db_path, timeout=self.busy_timeout_ms / 1000.0)
            try:
                conn.execute("PRAGMA journal_mode = WAL;")
                conn.execute("PRAGMA synchronous = NORMAL;")
                conn.execute(f"PRAGMA busy_timeout = {self.busy_timeout_ms};")
                conn.execute(f"PRAGMA mmap_size = {self.mmap_size_bytes};")
                conn.execute("PRAGMA temp_store = MEMORY;")
                conn.execute("PRAGMA cache_size = -64000;")  # 64MB cache
            finally:
                conn.close()

    def get_raw_connection(self) -> sqlite3.Connection:
        """Returns a new configured SQLite connection."""
        conn = sqlite3.connect(self.db_path, timeout=self.busy_timeout_ms / 1000.0)
        conn.execute(f"PRAGMA busy_timeout = {self.busy_timeout_ms};")
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Context manager ensuring connections are cleanly opened, committed, and closed,
        preventing dangling file handles and WinError 32 locks on NTFS.
        """
        conn = self.get_raw_connection()
        try:
            yield conn
            if self.autocommit:
                conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception as exc:
                logger.debug("Failed rolling back SQLite transaction: %s", exc)
            raise
        finally:
            conn.close()

    def execute(self, sql: str, params: tuple = ()) -> list:
        """Executes a query and returns fetched rows."""
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            if cursor.description:
                return cursor.fetchall()
            return []

    def execute_script(self, script: str):
        """Executes a batch SQL script."""
        with self.connection() as conn:
            conn.executescript(script)
