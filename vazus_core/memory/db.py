"""
vazus_core.db - Unified Thread-Safe Database Access Layer
Provides WAL-enabled, concurrency-safe SQLite connections to prevent database lock errors.
"""

import os
import sqlite3
import logging
import threading
import numpy as np
try:
    import sqlite_vec
except ImportError:
    sqlite_vec = None
from pathlib import Path
from typing import Optional

logger = logging.getLogger("vazus_core.db")

def _default_db_path() -> str:
    """Derives default DB path from environment or relative workspace discovery."""
    env = os.getenv("VAZUS_DB_PATH")
    if env:
        return env
    from vazus_core.paths import DEFAULT_DB_PATH
    return str(DEFAULT_DB_PATH)


DEFAULT_VAZUS_DB: str = _default_db_path()


_INITIALIZED_DBS = set()
_thread_local = threading.local()
_VEC_LOAD_LOCK = threading.Lock()
_SCHEMA_INIT_LOCK = threading.Lock()


class SharedConnectionProxy:
    """Thread-local SQLite connection proxy that prevents C-extension re-loading memory leaks."""
    def __init__(self, conn: sqlite3.Connection, cache_key: Optional[tuple] = None):
        self._conn = conn
        self._cache_key = cache_key
        self._closed = False

    def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            self._conn.execute("PRAGMA wal_checkpoint(PASSIVE);")
        except Exception as e:
            logger.debug("close wal_checkpoint non-fatal: %s", e)
        try:
            self._conn.execute("PRAGMA shrink_memory;")
        except Exception as e:
            logger.debug("close shrink_memory non-fatal: %s", e)
        try:
            self._conn.close()
        except Exception as e:
            logger.debug("close connection non-fatal: %s", e)
        if self._cache_key is not None and hasattr(_thread_local, "connections"):
            _thread_local.connections.pop(self._cache_key, None)

    def force_close(self):
        self.close()

    def __enter__(self):
        return self._conn.__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        return self._conn.__exit__(exc_type, exc_val, exc_tb)

    def __getattr__(self, name):
        return getattr(self._conn, name)


def _migrate_legacy_columns(conn: sqlite3.Connection | SharedConnectionProxy) -> None:
    """Performs schema migration for existing database files missing node_id column."""
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(organic_insights);")
        cols = [r[1] for r in cur.fetchall()]
        cur.close()
        if cols and "node_id" not in cols:
            conn.execute("ALTER TABLE organic_insights ADD COLUMN node_id TEXT;")
            try:
                conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_organic_insights_node_id ON organic_insights(node_id);")
            except Exception as e:
                logger.debug("migrate idx_organic_insights_node_id non-fatal: %s", e)
            conn.commit()
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(subagent_memory_traces);")
        trace_cols = [r[1] for r in cur.fetchall()]
        cur.close()
        if trace_cols and "obsidian_note_path" not in trace_cols:
            conn.execute("ALTER TABLE subagent_memory_traces ADD COLUMN obsidian_note_path TEXT;")
            conn.commit()
    except Exception as e:
        logger.debug("migrate_legacy_columns non-fatal: %s", e)


def _init_core_tables(conn: sqlite3.Connection | SharedConnectionProxy) -> None:
    """Creates core entity and graph tables."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS organic_insights (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            node_id TEXT UNIQUE,
            category TEXT,
            insight TEXT,
            timestamp REAL,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TRIGGER IF NOT EXISTS trg_organic_insights_sync_ins
        AFTER INSERT ON organic_insights
        FOR EACH ROW
        BEGIN
            UPDATE organic_insights
            SET created_at = CASE
                    WHEN NEW.created_at IS NOT NULL AND instr(CAST(NEW.created_at AS TEXT), '-') > 0 THEN NEW.created_at
                    WHEN NEW.timestamp IS NOT NULL THEN datetime(NEW.timestamp, 'unixepoch')
                    ELSE datetime('now')
                END,
                timestamp = CASE
                    WHEN NEW.timestamp IS NOT NULL THEN NEW.timestamp
                    WHEN NEW.created_at IS NOT NULL AND instr(CAST(NEW.created_at AS TEXT), '-') > 0 THEN unixepoch(NEW.created_at)
                    ELSE unixepoch()
                END
            WHERE id = NEW.id AND (created_at IS NULL OR timestamp IS NULL OR (NEW.timestamp IS NULL AND instr(CAST(timestamp AS TEXT), '-') > 0));
        END;

        CREATE TRIGGER IF NOT EXISTS trg_organic_insights_sync_upd
        AFTER UPDATE OF created_at, timestamp ON organic_insights
        FOR EACH ROW
        WHEN (NEW.created_at IS NULL AND NEW.timestamp IS NOT NULL) OR (NEW.timestamp IS NULL AND NEW.created_at IS NOT NULL)
        BEGIN
            UPDATE organic_insights
            SET created_at = CASE
                    WHEN NEW.created_at IS NULL AND NEW.timestamp IS NOT NULL THEN datetime(NEW.timestamp, 'unixepoch')
                    ELSE NEW.created_at
                END,
                timestamp = CASE
                    WHEN NEW.timestamp IS NULL AND NEW.created_at IS NOT NULL AND instr(CAST(NEW.created_at AS TEXT), '-') > 0 THEN unixepoch(NEW.created_at)
                    ELSE NEW.timestamp
                END
            WHERE id = NEW.id;
        END;

        CREATE TABLE IF NOT EXISTS kg_nodes (
            id TEXT PRIMARY KEY,
            name TEXT,
            domain TEXT,
            node_type TEXT,
            description TEXT,
            tags TEXT,
            properties TEXT,
            embedding_json TEXT,
            embedding BLOB
        );

        CREATE TABLE IF NOT EXISTS kg_edges (
            source_id TEXT,
            target_id TEXT,
            relation TEXT,
            strength REAL,
            properties TEXT,
            PRIMARY KEY (source_id, target_id, relation)
        );

        CREATE TABLE IF NOT EXISTS subagent_memory_traces (
            trace_id TEXT PRIMARY KEY,
            dialogue_id TEXT,
            agent_name TEXT,
            trace_kind TEXT,
            summary TEXT,
            content TEXT,
            obsidian_note_path TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_subagent_memory_traces_created ON subagent_memory_traces(created_at);
    """)


def _init_vector_tables(conn: sqlite3.Connection | SharedConnectionProxy) -> None:
    """Initializes sqlite-vec virtual tables, triggers, and self-healing mechanisms."""
    # Self-healing check: verify if vec_kg_nodes virtual table is registered and healthy
    try:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
        if "vec_kg_nodes" in tables:
            try:
                conn.execute("SELECT count(*) FROM vec_kg_nodes;").fetchone()
            except sqlite3.OperationalError:
                # Corrupted virtual table: recreate dummy shadow tables to satisfy SQLite DROP TABLE
                for shadow in ["rowids", "info", "chunks"]:
                    conn.execute(f"CREATE TABLE IF NOT EXISTS vec_kg_nodes_{shadow} (id INT);")
                conn.execute("DROP TABLE IF EXISTS vec_kg_nodes;")
                for shadow in ["rowids", "info", "chunks"]:
                    conn.execute(f"DROP TABLE IF EXISTS vec_kg_nodes_{shadow};")
    except Exception:
        pass

    conn.executescript("""
        CREATE VIRTUAL TABLE IF NOT EXISTS vec_kg_nodes USING vec0(
            node_id TEXT KEY,
            embedding float[768]
        );

        CREATE TRIGGER IF NOT EXISTS trg_kg_nodes_insert AFTER INSERT ON kg_nodes
        WHEN NEW.embedding_json IS NOT NULL AND NEW.embedding_json != '[]'
        BEGIN
            DELETE FROM vec_kg_nodes WHERE node_id = NEW.id;
            INSERT INTO vec_kg_nodes(node_id, embedding)
            VALUES(NEW.id, NEW.embedding_json);
        END;

        CREATE TRIGGER IF NOT EXISTS trg_kg_nodes_update AFTER UPDATE OF embedding_json ON kg_nodes
        WHEN NEW.embedding_json IS NOT NULL AND NEW.embedding_json != '[]'
        BEGIN
            DELETE FROM vec_kg_nodes WHERE node_id = OLD.id;
            DELETE FROM vec_kg_nodes WHERE node_id = NEW.id;
            INSERT INTO vec_kg_nodes(node_id, embedding)
            VALUES(NEW.id, NEW.embedding_json);
        END;

        CREATE TRIGGER IF NOT EXISTS trg_kg_nodes_delete AFTER DELETE ON kg_nodes
        BEGIN
            DELETE FROM vec_kg_nodes WHERE node_id = OLD.id;
        END;
    """)

    # Backfill if kg_nodes exists and has unindexed embeddings
    try:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
        if "kg_nodes" in tables:
            conn.execute("""
                INSERT OR IGNORE INTO vec_kg_nodes(node_id, embedding)
                SELECT id, embedding_json FROM kg_nodes
                WHERE embedding_json IS NOT NULL AND embedding_json != '[]'
                  AND id NOT IN (SELECT node_id FROM vec_kg_nodes);
            """)
    except Exception:
        pass




def _init_schema_indexes(conn: sqlite3.Connection | SharedConnectionProxy) -> None:
    """Creates performance and domain indexes."""
    conn.executescript("""
        CREATE INDEX IF NOT EXISTS idx_kg_nodes_domain ON kg_nodes(domain);
        CREATE INDEX IF NOT EXISTS idx_kg_nodes_type ON kg_nodes(node_type);
        CREATE INDEX IF NOT EXISTS idx_kg_nodes_name ON kg_nodes(name);
        CREATE INDEX IF NOT EXISTS idx_kg_nodes_embedding_notnull ON kg_nodes(id) WHERE embedding IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_kg_edges_source ON kg_edges(source_id);
        CREATE INDEX IF NOT EXISTS idx_kg_edges_target ON kg_edges(target_id);
        CREATE INDEX IF NOT EXISTS idx_kg_edges_rel ON kg_edges(relation);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_organic_insights_node_id ON organic_insights(node_id);
        CREATE INDEX IF NOT EXISTS idx_organic_insights_cat ON organic_insights(category);
        CREATE INDEX IF NOT EXISTS idx_organic_insights_ts ON organic_insights(timestamp);
        CREATE INDEX IF NOT EXISTS idx_organic_insights_node_id_cat ON organic_insights(node_id, category);
    """)


def _init_fts5_triggers(conn: sqlite3.Connection | SharedConnectionProxy) -> None:
    """Initializes FTS5 full-text search virtual tables and synchronization triggers."""
    conn.executescript("""
        CREATE VIRTUAL TABLE IF NOT EXISTS organic_insights_fts USING fts5(
            insight,
            category,
            content='organic_insights',
            content_rowid='id',
            tokenize='porter unicode61'
        );

        CREATE TRIGGER IF NOT EXISTS trg_fts_insert AFTER INSERT ON organic_insights BEGIN
            INSERT INTO organic_insights_fts(rowid, insight, category)
            VALUES (new.id, new.insight, new.category);
        END;

        CREATE TRIGGER IF NOT EXISTS trg_fts_delete AFTER DELETE ON organic_insights BEGIN
            INSERT INTO organic_insights_fts(organic_insights_fts, rowid, insight, category)
            VALUES ('delete', old.id, old.insight, old.category);
        END;

        CREATE TRIGGER IF NOT EXISTS trg_fts_update AFTER UPDATE ON organic_insights BEGIN
            INSERT INTO organic_insights_fts(organic_insights_fts, rowid, insight, category)
            VALUES ('delete', old.id, old.insight, old.category);
            INSERT INTO organic_insights_fts(rowid, insight, category)
            VALUES (new.id, new.insight, new.category);
        END;
    """)


def init_db_schemas(conn: sqlite3.Connection | SharedConnectionProxy, db_path: str | Path | None = None) -> None:
    """
    Ensures organic_insights, kg_nodes, kg_edges tables and associated indexes
    are automatically initialized in the database connection. Thread-safe.
    """
    path_key = None
    if db_path is not None and str(db_path) != ":memory:":
        try:
            path_key = str(Path(db_path).resolve())
        except Exception as e:
            logger.debug("init_db_schemas resolve path key non-fatal: %s", e)

    with _SCHEMA_INIT_LOCK:
        if path_key and path_key in _INITIALIZED_DBS:
            return

        _migrate_legacy_columns(conn)

        try:
            _init_core_tables(conn)
            _init_vector_tables(conn)
            _init_schema_indexes(conn)
            _init_fts5_triggers(conn)
            conn.commit()
        except sqlite3.OperationalError as e:
            logger.debug("init_db_schemas operational non-fatal: %s", e)

        if path_key:
            _INITIALIZED_DBS.add(path_key)


def _configure_sqlite_pragmas(conn: sqlite3.Connection, timeout: float) -> None:
    """Configures high-concurrency WAL mode and memory PRAGMAs."""
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        busy_ms = int(timeout * 1000)
        conn.execute(f"PRAGMA busy_timeout={busy_ms};")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA cache_size=-32000;")   # 32MB page cache
        conn.execute("PRAGMA mmap_size=268435456;") # 256MB memory-mapped I/O
        conn.execute("PRAGMA temp_store=MEMORY;")   # temp tables in RAM
        conn.execute("PRAGMA wal_autocheckpoint=1000;")
        conn.execute("PRAGMA optimize;")
    except sqlite3.OperationalError as e:
        logger.debug("PRAGMA configuration non-fatal: %s", e)


def _load_sqlite_vec_extension(conn: sqlite3.Connection) -> None:
    """Loads sqlite-vec extension if available."""
    if sqlite_vec is not None:
        with _VEC_LOAD_LOCK:
            try:
                conn.enable_load_extension(True)
                sqlite_vec.load(conn)
                conn.enable_load_extension(False)
            except Exception as e:
                logger.warning(f"Failed to load sqlite-vec: {e}")


def _resolve_target_db_path(db_path: str | Path | None = None, read_only: bool = False) -> str:
    """Resolves active database path with test isolation sandboxing."""
    if db_path is None:
        db_path = os.getenv("VAZUS_DB_PATH", DEFAULT_VAZUS_DB)
    path_str = str(db_path)
    if os.getenv("VAZUS_TEST_ISOLATION") == "1" and path_str != ":memory:":
        try:
            canonical_resolved = str(Path(r"C:\vazus\services\memory\vazus.db").resolve()).lower()
            target_resolved = str(Path(path_str).resolve()).lower()
            if target_resolved == canonical_resolved or target_resolved.replace("\\", "/").endswith("services/memory/vazus.db"):
                isolated_env = os.getenv("VAZUS_DB_PATH")
                if isolated_env:
                    path_str = str(Path(isolated_env).resolve())
        except Exception as e:
            logger.debug("test isolation redirect non-fatal: %s", e)
    return path_str


def _get_cached_thread_connection(path_str: str, read_only: bool) -> Optional[SharedConnectionProxy]:
    """Retrieves an active cached thread-local connection proxy if healthy."""
    if not hasattr(_thread_local, "connections"):
        _thread_local.connections = {}
    try:
        abs_path = str(Path(path_str).resolve())
        cache_key = (abs_path, read_only)
        if cache_key in _thread_local.connections:
            proxy = _thread_local.connections[cache_key]
            if not getattr(proxy, "_closed", False):
                try:
                    proxy._conn.execute("SELECT 1")
                    return proxy
                except Exception as e:
                    logger.debug("cached connection test failed: %s", e)
            _thread_local.connections.pop(cache_key, None)
    except Exception as e:
        logger.debug("cache lookup non-fatal: %s", e)
    return None


def get_db_connection(
    db_path: str | Path | None = None,
    timeout: float = 60.0,
    read_only: bool = False,
    use_cache: bool = True
) -> sqlite3.Connection | SharedConnectionProxy:
    """
    Creates or retrieves a WAL-enabled SQLite connection with busy_timeout.
    Automatically initializes missing schemas (organic_insights, kg_nodes, kg_edges).
    """
    path_str = _resolve_target_db_path(db_path, read_only=read_only)

    if use_cache and path_str != ":memory:":
        cached = _get_cached_thread_connection(path_str, read_only)
        if cached is not None:
            return cached

    if not read_only and path_str != ":memory:" and not path_str.startswith("file:"):
        Path(path_str).resolve().parent.mkdir(parents=True, exist_ok=True)

    if read_only:
        uri_path = f"file:{Path(path_str).as_posix()}?mode=ro"
        raw_conn = sqlite3.connect(uri_path, timeout=timeout, uri=True)
    else:
        raw_conn = sqlite3.connect(path_str, timeout=timeout)
    raw_conn.row_factory = sqlite3.Row

    _configure_sqlite_pragmas(raw_conn, timeout)
    _load_sqlite_vec_extension(raw_conn)

    if not read_only:
        init_db_schemas(raw_conn, db_path=path_str)

    if use_cache and path_str != ":memory:":
        try:
            abs_path = str(Path(path_str).resolve())
            cache_key = (abs_path, read_only)
            proxy = SharedConnectionProxy(raw_conn, cache_key=cache_key)
            if not hasattr(_thread_local, "connections"):
                _thread_local.connections = {}
            _thread_local.connections[cache_key] = proxy
            return proxy
        except Exception as e:
            logger.debug("caching connection proxy non-fatal: %s", e)

    return SharedConnectionProxy(raw_conn)


def close_all_thread_connections() -> None:
    """Closes and clears all thread-local cached connection handles in the current thread."""
    global _INITIALIZED_DBS
    _INITIALIZED_DBS.clear()
    if hasattr(_thread_local, "connections"):
        connections = list(_thread_local.connections.values())
        _thread_local.connections.clear()
        for proxy in connections:
            try:
                proxy.force_close()
            except Exception as e:
                logger.debug("close_all_thread_connections non-fatal: %s", e)


def pack_vector_f32(vec: list) -> bytes:
    """Packs list of floats into raw binary float32 BLOB (3,072 bytes for 768D vector)."""
    return np.array(vec, dtype=np.float32).tobytes()


def unpack_vector_f32(blob: bytes) -> list:
    """Unpacks raw binary float32 BLOB back to list of floats."""
    if not blob:
        return []
    return np.frombuffer(blob, dtype=np.float32).tolist()

