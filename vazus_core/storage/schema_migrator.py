"""
Atomic Schema Migration Manager for SQLite databases using PRAGMA user_version DAG.
"""

import hashlib
import sqlite3
from pathlib import Path
from typing import List, Optional


class SchemaMigration:
    def __init__(self, version: int, description: str, up_sql: str, down_sql: str = ""):
        self.version = version
        self.description = description
        self.up_sql = up_sql
        self.down_sql = down_sql
        self.checksum = hashlib.sha256(up_sql.strip().encode("utf-8")).hexdigest()[:16]


class SchemaMigrator:
    """
    Manages atomic forward and rollback database migrations with PRAGMA user_version.
    """

    CORE_MIGRATIONS: List[SchemaMigration] = [
        SchemaMigration(
            version=1,
            description="Initialize Knowledge Graph and Memory Tables",
            up_sql="""
            CREATE TABLE IF NOT EXISTS kg_nodes (
                id TEXT PRIMARY KEY,
                node_type TEXT NOT NULL,
                name TEXT NOT NULL,
                content TEXT,
                metadata JSON,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS kg_edges (
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                relation TEXT NOT NULL,
                weight REAL DEFAULT 1.0,
                PRIMARY KEY (source_id, target_id, relation)
            );
            """,
            down_sql="DROP TABLE IF EXISTS kg_edges; DROP TABLE IF EXISTS kg_nodes;",
        ),
        SchemaMigration(
            version=2,
            description="Initialize Saga Undo Log and Verifiable Ledger",
            up_sql="""
            CREATE TABLE IF NOT EXISTS saga_undo_log (
                saga_id TEXT NOT NULL,
                step_index INTEGER NOT NULL,
                action_type TEXT NOT NULL,
                undo_payload TEXT NOT NULL,
                timestamp REAL NOT NULL,
                PRIMARY KEY (saga_id, step_index)
            );
            CREATE TABLE IF NOT EXISTS verifiable_ledger_v2 (
                record_id TEXT PRIMARY KEY,
                step_number INTEGER NOT NULL,
                action_type TEXT NOT NULL,
                state_hash TEXT NOT NULL,
                previous_hash TEXT NOT NULL,
                signature TEXT NOT NULL,
                timestamp REAL NOT NULL
            );
            """,
            down_sql="DROP TABLE IF EXISTS saga_undo_log; DROP TABLE IF EXISTS verifiable_ledger_v2;",
        ),
        SchemaMigration(
            version=3,
            description="Initialize Circuit Breaker and Tool Telemetry",
            up_sql="""
            CREATE TABLE IF NOT EXISTS circuit_breaker_state (
                service_name TEXT PRIMARY KEY,
                failure_count INTEGER DEFAULT 0,
                last_failure_time REAL DEFAULT 0,
                state TEXT DEFAULT 'CLOSED',
                cooldown_seconds REAL DEFAULT 60.0
            );
            CREATE TABLE IF NOT EXISTS tool_invocation_telemetry (
                invocation_id TEXT PRIMARY KEY,
                tool_name TEXT NOT NULL,
                execution_time_ms REAL NOT NULL,
                tokens_used INTEGER DEFAULT 0,
                status TEXT NOT NULL,
                timestamp REAL NOT NULL
            );
            """,
            down_sql="DROP TABLE IF EXISTS circuit_breaker_state; DROP TABLE IF EXISTS tool_invocation_telemetry;",
        ),
    ]

    def __init__(self, db_path: str, migrations: Optional[List[SchemaMigration]] = None):
        self.db_path = str(Path(db_path).resolve())
        self.migrations = migrations or self.CORE_MIGRATIONS

    def get_current_version(self) -> int:
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            cur.execute("PRAGMA user_version;")
            row = cur.fetchone()
            v = int(row[0]) if row else 0
            if v == 0:
                cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('kg_nodes', 'mem0_facts');")
                if cur.fetchone():
                    v = max(m.version for m in self.migrations)
                    cur.execute(f"PRAGMA user_version = {v};")
                    conn.commit()
            return v
        finally:
            conn.close()

    def migrate(self, target_version: Optional[int] = None) -> int:
        """Applies pending migrations up to target_version (or latest)."""
        current = self.get_current_version()
        target = target_version if target_version is not None else max(m.version for m in self.migrations)

        conn = sqlite3.connect(self.db_path)
        try:
            for migration in sorted(self.migrations, key=lambda m: m.version):
                if current < migration.version <= target:
                    with conn:
                        conn.executescript(migration.up_sql)
                        conn.execute(f"PRAGMA user_version = {migration.version};")
                    current = migration.version
            return current
        finally:
            conn.close()

    def rollback(self, target_version: int) -> int:
        """Rolls back migrations down to target_version."""
        current = self.get_current_version()
        if target_version >= current:
            return current

        conn = sqlite3.connect(self.db_path)
        try:
            for migration in sorted(self.migrations, key=lambda m: m.version, reverse=True):
                if current >= migration.version > target_version:
                    if migration.down_sql:
                        with conn:
                            conn.executescript(migration.down_sql)
                            conn.execute(f"PRAGMA user_version = {migration.version - 1};")
                    current = migration.version - 1
            return current
        finally:
            conn.close()
