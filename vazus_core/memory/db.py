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
from typing import Optional, Dict, Any, List

logger = logging.getLogger("vazus_core.db")

def _default_db_path() -> str:
    """Derives default DB path from environment or relative workspace discovery."""
    env = os.getenv("VAZUS_DB_PATH")
    if env:
        return env
    # Prefer dynamic workspace discovery over hardcoded path
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "services" / "memory" / "vazus.db"
        if candidate.parent.exists():
            return str(candidate)
    return r"C:\vazus\services\memory\vazus.db"


DEFAULT_VAZUS_DB: str = _default_db_path()


_INITIALIZED_DBS = set()
_thread_local = threading.local()
_VEC_LOAD_LOCK = threading.Lock()


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
        except Exception:
            pass
        try:
            self._conn.execute("PRAGMA shrink_memory;")
        except Exception:
            pass
        try:
            self._conn.close()
        except Exception:
            pass
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


def init_db_schemas(conn: sqlite3.Connection | SharedConnectionProxy, db_path: str | Path | None = None) -> None:
    """
    Ensures organic_insights, kg_nodes, kg_edges tables and associated indexes
    are automatically initialized in the database connection.
    """
    if db_path is not None and str(db_path) != ":memory:":
        try:
            path_key = str(Path(db_path).resolve())
            if path_key in _INITIALIZED_DBS:
                return
        except Exception:
            pass

    # Fast check: If organic_insights table already exists on disk, ensure auxiliary tables and indexes exist
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='organic_insights';")
        has_table = cur.fetchone() is not None
        cur.close()
        if has_table:
            # Ensure indexes & FTS virtual table exist
            try:
                conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_organic_insights_node_id ON organic_insights(node_id);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_organic_insights_node_id_cat ON organic_insights(node_id, category);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_kg_nodes_embedding_notnull ON kg_nodes(id) WHERE embedding IS NOT NULL;")
                
                # Check FTS5
                fts_exists = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='organic_insights_fts';").fetchone() is not None
                if not fts_exists:
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
                    conn.execute("INSERT INTO organic_insights_fts(organic_insights_fts) VALUES('rebuild');")
                conn.commit()
            except Exception:
                pass
            if db_path is not None and str(db_path) != ":memory:":
                try:
                    _INITIALIZED_DBS.add(str(Path(db_path).resolve()))
                except Exception:
                    pass
            return
    except Exception:
        pass

    # 1. Schema migration for existing database files missing node_id column
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(organic_insights);")
        cols = [r[1] for r in cur.fetchall()]
        cur.close()
        if cols and "node_id" not in cols:
            conn.execute("ALTER TABLE organic_insights ADD COLUMN node_id TEXT;")
            try:
                conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_organic_insights_node_id ON organic_insights(node_id);")
            except Exception:
                pass
            conn.commit()
    except Exception:
        pass

    # 2. Complete schema initialization
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS organic_insights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id TEXT UNIQUE,
                category TEXT,
                insight TEXT,
                timestamp REAL
            );

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

            CREATE VIRTUAL TABLE IF NOT EXISTS vec_kg_nodes USING vec0(
                node_id TEXT KEY,
                embedding float[768]
            );

            CREATE TRIGGER IF NOT EXISTS trg_kg_nodes_insert AFTER INSERT ON kg_nodes
            WHEN NEW.embedding_json IS NOT NULL AND NEW.embedding_json != '[]'
            BEGIN
                INSERT INTO vec_kg_nodes(node_id, embedding)
                VALUES(NEW.id, NEW.embedding_json);
            END;

            CREATE TRIGGER IF NOT EXISTS trg_kg_nodes_update AFTER UPDATE OF embedding_json ON kg_nodes
            WHEN NEW.embedding_json IS NOT NULL AND NEW.embedding_json != '[]'
            BEGIN
                DELETE FROM vec_kg_nodes WHERE node_id = OLD.id;
                INSERT INTO vec_kg_nodes(node_id, embedding)
                VALUES(NEW.id, NEW.embedding_json);
            END;

            CREATE TRIGGER IF NOT EXISTS trg_kg_nodes_delete AFTER DELETE ON kg_nodes
            BEGIN
                DELETE FROM vec_kg_nodes WHERE node_id = OLD.id;
            END;

            CREATE TABLE IF NOT EXISTS kg_edges (
                source_id TEXT,
                target_id TEXT,
                relation TEXT,
                strength REAL,
                properties TEXT,
                PRIMARY KEY (source_id, target_id, relation)
            );

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
        conn.commit()
    except sqlite3.OperationalError:
        pass
    if db_path is not None and str(db_path) != ":memory:":
        try:
            _INITIALIZED_DBS.add(str(Path(db_path).resolve()))
        except Exception:
            pass


def get_db_connection(
    db_path: str | Path | None = None,
    timeout: float = 60.0,
    read_only: bool = False,
    use_cache: bool = True
) -> sqlite3.Connection | SharedConnectionProxy:
    """
    Creates or retrieves a WAL-enabled SQLite connection with busy_timeout.
    Automatically initializes missing schemas (organic_insights, kg_nodes, kg_edges).
    Prevents 'sqlite3.OperationalError: database is locked' in multi-subagent scenarios.
    Uses thread-local connection caching when use_cache=True to prevent C-extension reloading leaks.
    """
    if db_path is None:
        db_path = os.getenv("VAZUS_DB_PATH", DEFAULT_VAZUS_DB)
    
    path_str = str(db_path)

    # Use thread-local caching for non-memory databases when use_cache is True
    if use_cache and path_str != ":memory:":
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
                    except Exception:
                        pass
                _thread_local.connections.pop(cache_key, None)
        except Exception:
            pass

    # Ensure parent directory exists for writable database file
    if not read_only and path_str != ":memory:" and not path_str.startswith("file:"):
        Path(path_str).resolve().parent.mkdir(parents=True, exist_ok=True)

    # Enable URI mode if read_only requested
    if read_only:
        uri_path = f"file:{path_str}?mode=ro"
        raw_conn = sqlite3.connect(uri_path, timeout=timeout, uri=True)
    else:
        raw_conn = sqlite3.connect(path_str, timeout=timeout)
        
    raw_conn.row_factory = sqlite3.Row
    
    # Configure concurrency PRAGMAs
    try:
        raw_conn.execute("PRAGMA journal_mode=WAL;")
        busy_ms = int(timeout * 1000)
        raw_conn.execute(f"PRAGMA busy_timeout={busy_ms};")
        raw_conn.execute("PRAGMA synchronous=NORMAL;")
        raw_conn.execute("PRAGMA cache_size=-32000;")   # 32MB page cache
        raw_conn.execute("PRAGMA mmap_size=268435456;") # 256MB memory-mapped I/O
        raw_conn.execute("PRAGMA temp_store=MEMORY;")   # temp tables in RAM
        raw_conn.execute("PRAGMA wal_autocheckpoint=1000;")
        raw_conn.execute("PRAGMA optimize;")
    except sqlite3.OperationalError:
        pass
        
    # Load sqlite-vec extension
    if sqlite_vec is not None:
        with _VEC_LOAD_LOCK:
            try:
                raw_conn.enable_load_extension(True)
                sqlite_vec.load(raw_conn)
                raw_conn.enable_load_extension(False)
            except Exception as e:
                logger.warning(f"Failed to load sqlite-vec: {e}")
        
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
        except Exception:
            pass

    return SharedConnectionProxy(raw_conn)


def close_all_thread_connections() -> None:  # noqa: ANN201
    """
    Closes and clears all thread-local cached connection handles in the current thread.
    Use before deleting database files or during thread cleanup.
    """
    global _INITIALIZED_DBS
    _INITIALIZED_DBS.clear()
    if hasattr(_thread_local, "connections"):
        connections = list(_thread_local.connections.values())
        _thread_local.connections.clear()
        for proxy in connections:
            try:
                proxy.force_close()
            except Exception:
                pass



def pack_vector_f32(vec: list) -> bytes:
    """Packs list of floats into raw binary float32 BLOB (3,072 bytes for 768D vector)."""
    return np.array(vec, dtype=np.float32).tobytes()


def unpack_vector_f32(blob: bytes) -> list:
    """Unpacks raw binary float32 BLOB back to list of floats."""
    if not blob:
        return []
    return np.frombuffer(blob, dtype=np.float32).tolist()

