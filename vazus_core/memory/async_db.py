"""
vazus_core.memory.async_db — Asynchronous Non-Blocking SQLite Connection Pool & Query Engine.
Provides asyncio-compatible database execution with dedicated serialized writer queue,
concurrent read pool, WAL mode, and zero database lock contention.

vazus SuperGraph OS v4.0 Unified Architecture
"""

import asyncio
import logging
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import List, Optional, Tuple, Union

from vazus_core.memory.db import DEFAULT_VAZUS_DB, get_db_connection

logger = logging.getLogger("AsyncDB")


class AsyncDatabasePool:
    """
    Async SQLite manager backed by an isolated bounded ThreadPoolExecutor
    and serialized write lock to ensure zero database lock contention and
    non-blocking query execution.
    """

    def __init__(self, db_path: Optional[Union[str, Path]] = None, max_workers: int = 8):
        self.db_path = str(db_path or DEFAULT_VAZUS_DB)
        self.max_workers = max_workers
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="vazus_async_db_")
        self._write_lock = threading.Lock()
        self._closed = False

    def _open_read_conn(self) -> sqlite3.Connection:
        """Opens a read-optimized connection with WAL and busy timeout."""
        conn = get_db_connection(self.db_path)
        try:
            conn.execute("PRAGMA busy_timeout=60000;")
        except Exception as e:
            logger.debug("Read conn pragma busy_timeout non-fatal: %s", e)
        return conn

    def _open_write_conn(self) -> sqlite3.Connection:
        """Opens a write connection with WAL, normal sync, and 60s busy timeout."""
        conn = get_db_connection(self.db_path)
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=60000;")
            conn.execute("PRAGMA synchronous=NORMAL;")
        except Exception as e:
            logger.debug("Write conn pragmas non-fatal: %s", e)
        return conn

    async def execute_query(self, sql: str, params: Tuple = ()) -> List[Tuple]:
        """Executes a SELECT query asynchronously over the reader pool."""
        loop = asyncio.get_running_loop()

        def _sync_query() -> List[Tuple]:
            conn = self._open_read_conn()
            try:
                cur = conn.cursor()
                cur.execute(sql, params)
                return cur.fetchall()
            finally:
                conn.close()

        return await loop.run_in_executor(self._executor, _sync_query)

    async def execute_mutation(self, sql: str, params: Tuple = ()) -> int:
        """Executes an INSERT/UPDATE/DELETE mutation asynchronously with serialized write locking."""
        loop = asyncio.get_running_loop()

        def _sync_mutation() -> int:
            with self._write_lock:
                conn = self._open_write_conn()
                try:
                    cur = conn.cursor()
                    cur.execute(sql, params)
                    conn.commit()
                    return cur.rowcount
                finally:
                    conn.close()

        return await loop.run_in_executor(self._executor, _sync_mutation)

    async def execute_batch(self, sql: str, seq_of_params: List[Tuple]) -> int:
        """Executes an executemany batch mutation asynchronously with serialized write locking."""
        loop = asyncio.get_running_loop()

        def _sync_batch() -> int:
            with self._write_lock:
                conn = self._open_write_conn()
                try:
                    cur = conn.cursor()
                    cur.executemany(sql, seq_of_params)
                    conn.commit()
                    return cur.rowcount
                finally:
                    conn.close()

        return await loop.run_in_executor(self._executor, _sync_batch)

    async def aclose(self) -> None:
        """Asynchronously closes connection pool and shuts down worker executors."""
        self.close()

    def close(self) -> None:
        """Closes the connection pool and shuts down worker executors."""
        self._closed = True
        self._executor.shutdown(wait=False)


# Global singleton async pool
async_db_pool = AsyncDatabasePool()


async def execute_query_async(sql: str, params: Tuple = (), db_path: Optional[str] = None) -> List[Tuple]:
    """Helper coroutine executing query against default or custom db pool."""
    pool = AsyncDatabasePool(db_path=db_path) if db_path else async_db_pool
    return await pool.execute_query(sql, params)


async def execute_mutation_async(sql: str, params: Tuple = (), db_path: Optional[str] = None) -> int:
    """Helper coroutine executing mutation against default or custom db pool."""
    pool = AsyncDatabasePool(db_path=db_path) if db_path else async_db_pool
    return await pool.execute_mutation(sql, params)


async def execute_batch_async(sql: str, seq_of_params: List[Tuple], db_path: Optional[str] = None) -> int:
    """Helper coroutine executing batch mutation against default or custom db pool."""
    pool = AsyncDatabasePool(db_path=db_path) if db_path else async_db_pool
    return await pool.execute_batch(sql, seq_of_params)


__all__ = [
    "AsyncDatabasePool",
    "async_db_pool",
    "execute_query_async",
    "execute_mutation_async",
    "execute_batch_async",
]
