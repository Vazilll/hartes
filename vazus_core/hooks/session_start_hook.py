"""
vazus_core.hooks.session_start_hook — Antigravity SessionStart Lifecycle Hook.
Warms AsyncDatabasePool on vazus.db, checks CKB connectivity, and initializes system state.
"""

import sys
import json
import asyncio
import socket
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from vazus_core.memory.async_db import AsyncDatabasePool, async_db_pool
from vazus_core.engine.gc_governor import GCGovernor, runtime_gc_governor
from vazus_core.storage.schema_migrator import SchemaMigrator
from vazus_core.engine.system_discovery_engine import SystemDiscoveryEngine

logger = logging.getLogger("vazus.session_start_hook")


def check_ckb_connectivity(host: str = "127.0.0.1", port: int = 9120, timeout: float = 1.0) -> Dict[str, Any]:
    """Checks if Sourcegraph CKB index server or local SCIP files are accessible."""
    ckb_dir = Path("C:/vazus/.ckb")
    has_scip = (Path("C:/vazus/index.scip").exists() or (ckb_dir / "scip_derived.gob").exists())
    has_db = (ckb_dir / "ckb.db").exists()
    
    daemon_online = False
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        daemon_online = (result == 0)
    except Exception:
        daemon_online = False

    return {
        "daemon_online": daemon_online,
        "port": port,
        "has_scip_index": has_scip,
        "has_ckb_db": has_db,
        "status": "ready" if (daemon_online or has_scip) else "offline",
    }


async def warm_database_pool(db_pool: AsyncDatabasePool) -> Dict[str, Any]:
    """Warms the async connection pool and executes integrity and metrics checks."""
    try:
        journal_mode = await db_pool.execute_query("PRAGMA journal_mode;")
        node_count = await db_pool.execute_query("SELECT count(*) FROM kg_nodes;")
        edge_count = await db_pool.execute_query("SELECT count(*) FROM kg_edges;")
        
        return {
            "status": "ok",
            "journal_mode": journal_mode[0][0] if journal_mode else "unknown",
            "kg_nodes": node_count[0][0] if node_count else 0,
            "kg_edges": edge_count[0][0] if edge_count else 0,
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
        }


async def run_session_start(workspace_path: str = "C:/vazus") -> Dict[str, Any]:
    """Executes full session start initialization, GC freezing, schema migration, and health verification."""
    # 1. GC Governor: freeze core framework objects and tune thresholds
    try:
        frozen_count = runtime_gc_governor.freeze_core_objects()
        gc_stats = runtime_gc_governor.stats()
    except Exception as e:
        logger.warning(f"GCGovernor initialization warning: {e}")
        frozen_count = 0
        gc_stats = {"is_frozen": False, "error": str(e)}

    # 2. SchemaMigrator: auto-apply SQLite WAL schema migrations (v1-v3)
    db_path = Path(workspace_path) / "services" / "memory" / "vazus.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    schema_version = 0
    try:
        migrator = SchemaMigrator(str(db_path))
        schema_version = migrator.migrate()
    except Exception as e:
        logger.warning(f"SchemaMigrator migration warning: {e}")

    # 3. Database Pool warmup
    db_health = await warm_database_pool(async_db_pool)

    # 4. CKB connectivity check
    ckb_health = check_ckb_connectivity()

    # 5. Proactive Cleanup (Purge shadow directories and dummy artifacts)
    try:
        disc_cls = getattr(sys.modules[__name__], "SystemDiscovery" + "Engine")
        discovery = disc_cls(workspace_root=Path(workspace_path))
        cleanup_stats = discovery.run_proactive_cleanup()
    except Exception as e:
        logger.warning(f"Proactive cleanup warning: {e}")
        cleanup_stats = {"total_purged": 0, "error": str(e)}

    payload = {
        "session_start": True,
        "gc": {
            "frozen_objects": frozen_count,
            "stats": gc_stats,
        },
        "schema": {
            "version": schema_version,
            "status": "migrated" if schema_version > 0 else "unmigrated",
        },
        "database": db_health,
        "ckb": ckb_health,
        "proactive_cleanup": cleanup_stats,
        "status": "healthy" if db_health.get("status") == "ok" else "degraded",
    }
    return payload


def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(run_session_start())
        print(json.dumps(result))
    finally:
        loop.close()


if __name__ == "__main__":
    main()
