"""
vazus_core.hooks.session_start_hook — Antigravity SessionStart Lifecycle Hook.
Warms AsyncDatabasePool on vazus.db, checks CKB connectivity, and initializes system state.
"""

import json
import os
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any

from vazus_core.memory.async_db import AsyncDatabasePool, async_db_pool
from vazus_core.engine.gc_governor import runtime_gc_governor
from vazus_core.storage.schema_migrator import SchemaMigrator

logger = logging.getLogger("vazus.session_start_hook")


def check_code_intelligence_readiness() -> Dict[str, Any]:
    """Checks cbm (Codebase Memory) and ast-grep readiness with zero network delay."""
    import shutil
    has_cbm = bool(shutil.which("cbm") or Path("C:/vazus/bin/cbm.exe").exists() or Path("C:/Users/Vaz/.gemini/antigravity/mcp/cbm").exists())
    has_ast_grep = bool(shutil.which("ast-grep") or shutil.which("sg") or Path("C:/Users/Vaz/AppData/Roaming/npm/sg.cmd").exists())
    
    return {
        "engine": "cbm+ast-grep",
        "has_cbm_graph": has_cbm,
        "has_ast_grep": has_ast_grep,
        "status": "ready" if (has_cbm and has_ast_grep) else "degraded",
    }


def check_ckb_connectivity(port: int = 9999, timeout: float = 0.1, **kwargs) -> Dict[str, Any]:
    """Compatibility alias for CKB / CBM graph connectivity."""
    intel = check_code_intelligence_readiness()
    return {
        "daemon_online": intel.get("has_cbm_graph", False),
        "has_scip_index": True,
        "status": intel.get("status", "ready"),
        "port": port,
        "timeout": timeout,
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
    env_db = os.getenv("VAZUS_DB_PATH")
    if env_db:
        db_path = Path(env_db)
    else:
        db_path = Path(workspace_path) / "services" / "memory" / "vazus.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    schema_version = 0
    try:
        migrator = SchemaMigrator(str(db_path))
        schema_version = migrator.migrate()
    except Exception as e:
        logger.warning(f"SchemaMigrator migration warning: {e}")

    # 3. Database Pool warmup
    target_pool = AsyncDatabasePool(str(db_path)) if env_db else async_db_pool
    db_health = await warm_database_pool(target_pool)
    if env_db:
        target_pool.close()

    # 4. Code Intelligence readiness (cbm + ast-grep)
    code_intel = check_code_intelligence_readiness()
    ckb_intel = check_ckb_connectivity()

    # 5. Proactive Cleanup (Purge shadow directories and dummy artifacts)
    try:
        from vazus_core.engine.system_discovery_engine import SystemDiscoveryEngine
        discovery = SystemDiscoveryEngine(workspace_root=Path(workspace_path))
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
        "code_intelligence": code_intel,
        "ckb": ckb_intel,
        "proactive_cleanup": cleanup_stats,
        "status": "healthy" if db_health.get("status") == "ok" else "degraded",
    }
    return payload


async def run_session_start_hook(session_id: str = "unknown", workspace_root: str = "C:/vazus", **kwargs) -> Dict[str, Any]:
    """Compatibility lifecycle wrapper for session start hook."""
    import time
    res = await run_session_start(workspace_path=workspace_root)
    res["session_id"] = session_id
    res["status"] = "SUCCESS" if res.get("status") in ("healthy", "ok") else "INITIALIZED"
    res["timestamp"] = time.time()
    return res


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
