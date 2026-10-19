"""
pytest session configuration & Universal DB Isolation for Vazus SuperGraph OS.
Redirects all database operations during test runs to isolated temporary SQLite databases,
preventing any writes to canonical services/memory/vazus.db.
Ensures zero mutations to canonical vazus.db via pre/post SHA256 checksum verification.
"""

import os
import sys
import shutil
import hashlib
import sqlite3
import pytest
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))
CANONICAL_DB = (WORKSPACE_ROOT / "services" / "memory" / "vazus.db").resolve()

from vazus_core.memory.db import (
    init_db_schemas,
    get_db_connection,
    close_all_thread_connections,
    DEFAULT_VAZUS_DB,
)
import vazus_core.memory.db as db_module


@pytest.fixture(scope="session")
def template_test_db(tmp_path_factory):
    """
    Creates a golden template SQLite database with initialized schemas in a temp directory.
    """
    temp_dir = tmp_path_factory.mktemp("vazus_template_db")
    template_path = temp_dir / "template_vazus.db"

    conn = sqlite3.connect(str(template_path))
    init_db_schemas(conn, db_path=str(template_path))
    conn.commit()
    conn.close()

    return template_path


@pytest.fixture(scope="session", autouse=True)
def vazus_global_test_isolation_guard(tmp_path_factory):
    """
    Session-wide fixture that:
    1. Truncates WAL and records SHA256 checksum of canonical vazus.db.
    2. Sets global test isolation flag.
    3. Redirects DynamicTraceCollector to an isolated session DB.
    4. Asserts byte-identical canonical DB state upon session completion.
    """
    close_all_thread_connections()

    # Create test lock file to prevent stop_hook from persisting concurrent session summaries
    test_lock_file = WORKSPACE_ROOT / ".vazus_test.lock"
    test_lock_file.write_text("1", encoding="utf-8")

    # 1. Pre-test baseline
    pre_sha256 = None
    pre_size = None
    if CANONICAL_DB.exists():
        try:
            conn = sqlite3.connect(str(CANONICAL_DB), timeout=30.0)
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            conn.close()
        except Exception:
            pass
        pre_size = CANONICAL_DB.stat().st_size
        with open(CANONICAL_DB, "rb") as f:
            pre_sha256 = hashlib.sha256(f.read()).hexdigest()

    # 2. Setup session sandbox
    session_sandbox = tmp_path_factory.mktemp("session_db") / "session_vazus.db"
    session_sandbox_str = str(session_sandbox)
    init_conn = sqlite3.connect(session_sandbox_str)
    init_db_schemas(init_conn, db_path=session_sandbox_str)
    init_conn.close()

    old_env = os.environ.get("VAZUS_DB_PATH")
    os.environ["VAZUS_DB_PATH"] = session_sandbox_str
    os.environ["VAZUS_TEST_ISOLATION"] = "1"
    os.environ["VAZUS_TEST_RUNNING"] = "1"
    old_default = db_module.DEFAULT_VAZUS_DB
    db_module.DEFAULT_VAZUS_DB = session_sandbox_str

    # 3. Dynamic Trace Collector in Isolated Temp DB
    telemetry_sandbox = tmp_path_factory.mktemp("session_telemetry") / "telemetry_vazus.db"
    telemetry_sandbox_str = str(telemetry_sandbox)
    collector = None
    activated = False
    try:
        from vazus_core.telemetry.dynamic_trace_collector import DynamicTraceCollector
        import vazus_core.telemetry.dynamic_trace_collector as dtc_mod
        collector = DynamicTraceCollector(db_path=telemetry_sandbox_str)
        dtc_mod._GLOBAL_COLLECTOR = collector
        activated = collector.start()
    except Exception:
        pass

    try:
        yield {
            "session_db": session_sandbox_str,
            "canonical_db": str(CANONICAL_DB),
            "pre_sha256": pre_sha256,
        }
    finally:
        if activated and collector is not None:
            try:
                collector.stop()
            except Exception:
                pass
        close_all_thread_connections()

        # Restore environment
        if old_env is not None:
            os.environ["VAZUS_DB_PATH"] = old_env
        else:
            os.environ.pop("VAZUS_DB_PATH", None)
        os.environ.pop("VAZUS_TEST_ISOLATION", None)
        os.environ.pop("VAZUS_TEST_RUNNING", None)
        db_module.DEFAULT_VAZUS_DB = old_default

        # 4. Post-test byte-identical invariant verification
        try:
            if CANONICAL_DB.exists() and pre_sha256 is not None:
                try:
                    conn = sqlite3.connect(str(CANONICAL_DB), timeout=30.0)
                    conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
                    conn.close()
                except Exception:
                    pass
                post_size = CANONICAL_DB.stat().st_size
                with open(CANONICAL_DB, "rb") as f:
                    post_sha256 = hashlib.sha256(f.read()).hexdigest()

                assert pre_sha256 == post_sha256, (
                    f"INTEGRITY VIOLATION: Canonical vazus.db was mutated during pytest execution!\n"
                    f"Pre SHA256:  {pre_sha256} ({pre_size:,} bytes)\n"
                    f"Post SHA256: {post_sha256} ({post_size:,} bytes)"
                )
        finally:
            if test_lock_file.exists():
                try:
                    test_lock_file.unlink()
                except Exception:
                    pass


@pytest.fixture(autouse=True)
def isolate_vazus_test_db(tmp_path, template_test_db, monkeypatch):
    """
    Autouse fixture that runs for EVERY test function:
    1. Copies template DB to a fresh tmp_path for the test.
    2. Sets VAZUS_DB_PATH environment variable.
    3. Monkeypatches DEFAULT_VAZUS_DB and DB_PATH across all modules.
    4. Ensures zero test writes touch services/memory/vazus.db.
    """
    test_db_path = str(tmp_path / "isolated_vazus.db")
    shutil.copyfile(str(template_test_db), test_db_path)

    # 1. Environment variables
    monkeypatch.setenv("VAZUS_DB_PATH", test_db_path)
    monkeypatch.setenv("VAZUS_TEST_ISOLATION", "1")
    monkeypatch.setenv("VAZUS_TEST_MODE", "1")

    # 2. Monkeypatch core memory db module
    monkeypatch.setattr(db_module, "DEFAULT_VAZUS_DB", test_db_path)

    # Eagerly import scanner modules to ensure sys.modules contains them
    try:
        import services.health_agent.ble_mi_scale_scanner
    except Exception:
        pass
    try:
        import vazus_core.ble_mi_scale_scanner
    except Exception:
        pass

    # 3. Monkeypatch subsystem DB_PATHs
    modules_to_patch = [
        ("vazus_core.integrations.tinkoff_finance_manager", "DB_PATH"),
        ("services.finance_agent.tinkoff_finance_manager", "DB_PATH"),
        ("vazus_core.integrations.mirea_student_manager", "DB_PATH"),
        ("vazus_core.mirea_student_manager", "DB_PATH"),
        ("vazus_core.nutrition_tracker", "DB_PATH"),
        ("services.health_agent.nutrition_tracker", "DB_PATH"),
        ("vazus_core.memory.mem0_memory_engine", "DB_PATH"),
        ("vazus_core.integrations.cognitive_tutor_engine", "DEFAULT_DB_PATH"),
        ("vazus_core.memory.zettelkasten_exporter", "DEFAULT_DB_PATH"),
        ("vazus_core.zettelkasten_exporter", "DEFAULT_DB_PATH"),
        ("vazus_core.engine.supergraph_linker", "DEFAULT_DB_PATH"),
        ("vazus_core.missions.verifiable_ledger", "DEFAULT_DB_PATH"),
        ("vazus_core.telemetry.dynamic_trace_collector", "DEFAULT_VAZUS_DB"),
        ("vazus_core.memory.dialogue_persister", "DEFAULT_DB_PATH"),
        ("vazus_core.memory.unified_memory_gateway", "DEFAULT_DB_PATH"),
        ("vazus_core.memory.whitelist_manager", "DEFAULT_DB_PATH"),
        ("vazus_core.integrations.google_super_sync_engine", "DB_PATH"),
        ("vazus_core.integrations.kgb_analytical_extractor", "DEFAULT_DB_PATH"),
        ("vazus_core.integrations.google_sync_hub", "DB_PATH"),
        ("vazus_core.integrations.notebook_synthesis_engine", "DB_PATH"),
        ("vazus_core.integrations.repo_indexer", "DEFAULT_DB_PATH"),
        ("vazus_core.verification.anti_false_confidence", "DB_PATH"),
        ("vazus_core.workers.agent_handoff", "TARGET_DB_PATHS"),
        ("services.finance_agent.finance_engine", "DB_PATH"),
        ("services.finance_agent.freelance_npd_engine", "DB_PATH"),
        ("services.health_agent.ble_mi_scale_scanner", "DB_PATH"),
        ("vazus_core.ble_mi_scale_scanner", "DB_PATH"),
        ("vazus_core.integrations.ble_mi_scale_scanner", "DB_PATH"),
        ("services.health_agent.google_fit_sync", "DB_PATH"),
        ("services.health_agent.grpc_health_servicer", "DB_PATH"),
        ("services.health_agent.health_telemetry_pipeline", "DB_PATH"),
        ("services.health_agent.langgraph_health_workflow", "DB_PATH"),
        ("services.health_agent.telegram_health_bot", "DB_PATH"),
        ("services.vision.vazus_vision_daemon", "DB_PATH"),
        ("vazus_core.organic_memory_bridge", "DB_PATH"),
        ("vazus_core.memory.organic_memory_bridge", "DB_PATH"),
        ("vazus_core.analysis.proactive_suggestion_engine", "VAZUS_DB"),
        ("vazus_core.evolution.synaptic_evolver", "db_path"),
        ("vazus_core.integrations.socratic_partner", "DB_PATH"),
        ("vazus_core.memory.agent_memory_bank", "db_path"),
        ("vazus_core.memory.knowledge_engine", "DB_PATH"),
        ("vazus_core.integrations.vault_graph_canvas", "db_path"),
        ("vazus_core.memory.j_space_vector_index", "DEFAULT_DB_PATH"),
        ("vazus_core.memory.dream_consolidator", "DEFAULT_VAZUS_DB"),
        ("vazus_core.memory.mem0_memory_engine", "DB_PATH"),
        ("vazus_core.engine.supergraph_master_orchestrator", "DB_PATH"),
    ]
    for mod_name, attr_name in modules_to_patch:
        if mod_name in sys.modules:
            mod = sys.modules[mod_name]
            if hasattr(mod, attr_name):
                curr_val = getattr(mod, attr_name)
                if isinstance(curr_val, list):
                    patch_val = [Path(test_db_path)]
                elif isinstance(curr_val, str):
                    patch_val = test_db_path
                else:
                    patch_val = Path(test_db_path)
                monkeypatch.setattr(mod, attr_name, patch_val)

    yield test_db_path

    # Teardown: ensure no subprocesses leak
    try:
        import psutil
        current_proc = psutil.Process()
        for child in current_proc.children(recursive=True):
            cmd = " ".join(child.cmdline() or [])
            if any(k in cmd for k in ["ble_mi_scale", "health_telemetry"]):
                try:
                    child.kill()
                except Exception:
                    pass
    except Exception:
        pass
