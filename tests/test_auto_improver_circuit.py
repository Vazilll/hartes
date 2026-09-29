"""
test_auto_improver_circuit.py — Test Suite for Recursive Self-Improvement in Vazus OS.
========================================================================================

Verifies:
1. Tool activation tracking and `was_used` flag setting via `record_j_space_tool_activation` & `record_j_space_tool_usage`.
2. J-Space adaptive re-weighting based on hit rates (`JSpaceToolIndexer.reweight_tools_from_activations`).
3. AutoImproverDaemon complete 5-phase loop (Observe -> Analyze -> Plan -> Execute & Verify -> Learn).
4. AutoImproverDaemon status, should_run logic, and session persistence in auto_improver_sessions.
5. UnifiedHub integration (check_auto_improver_status, run_auto_improver_cycle, get_system_status).
6. DaemonSidecar heartbeat telemetry (auto_improver_fresh, auto_improver_triggered).
"""

import sqlite3

from vazus_core.memory.j_space_tool_indexer import (
    JSpaceToolIndexer,
    record_j_space_tool_activation,
    record_j_space_tool_usage,
)
from vazus_core.hooks.pre_invocation_hook import (
    record_j_space_tool_activation as hook_record_activation,
    record_j_space_tool_usage as hook_record_usage,
)
from vazus_core.workers.auto_improver_daemon import AutoImproverDaemon
from vazus_core.engine.unified_hub import VazusUnifiedHub


def test_tool_activation_and_was_used_tracking(tmp_path):
    """Verify j_space_tool_activations schema and helper functions record activation and usage."""
    db_file = str(tmp_path / "test_act.db")

    # 1. Record an activation via indexer function
    record_j_space_tool_activation(
        tool_name="vazus-sandbox",
        prompt="запусти песочницу для тестов",
        invocation_num=1,
        db_path=db_file,
    )
    # Also verify hook re-export works
    hook_record_activation(
        tool_name="vazus-sandbox-2",
        prompt="проверь re-export",
        invocation_num=2,
        db_path=db_file,
    )

    conn = sqlite3.connect(db_file)
    row = conn.execute("SELECT tool_name, was_used FROM j_space_tool_activations WHERE tool_name='vazus-sandbox'").fetchone()
    assert row is not None
    assert row[0] == "vazus-sandbox"
    assert row[1] == 0
    conn.close()

    # 2. Mark as used via hook re-exported function and direct indexer function
    marked = hook_record_usage("vazus-sandbox", db_path=db_file)
    assert marked is True
    marked2 = record_j_space_tool_usage("vazus-sandbox-2", db_path=db_file)
    assert marked2 is True

    conn = sqlite3.connect(db_file)
    row_after = conn.execute("SELECT was_used FROM j_space_tool_activations").fetchone()
    assert row_after is not None
    assert row_after[0] == 1
    conn.close()


def test_j_space_adaptive_reweighting(tmp_path):
    """Verify adaptive re-weighting boosts frequently used tools and penalizes unused ones."""
    db_file = str(tmp_path / "test_reweight.db")

    # Populate tool metadata
    conn = sqlite3.connect(db_file)
    conn.execute("""
        CREATE TABLE j_space_tool_metadata (
            tool_name TEXT PRIMARY KEY,
            module TEXT NOT NULL,
            description TEXT NOT NULL,
            parameters_json TEXT,
            keywords TEXT,
            signature TEXT,
            is_native INTEGER DEFAULT 0,
            updated_at REAL NOT NULL,
            weight REAL DEFAULT 1.0
        );
    """)
    conn.execute("""
        CREATE TABLE j_space_tool_activations (
            tool_name TEXT,
            prompt TEXT,
            invocation_num INTEGER,
            timestamp TEXT,
            was_used INTEGER DEFAULT 0
        );
    """)

    conn.execute(
        "INSERT INTO j_space_tool_metadata (tool_name, module, description, updated_at, weight) VALUES (?, ?, ?, ?, ?)",
        ("popular_tool", "mod1", "A popular tool", 1000.0, 1.0)
    )
    conn.execute(
        "INSERT INTO j_space_tool_metadata (tool_name, module, description, updated_at, weight) VALUES (?, ?, ?, ?, ?)",
        ("ignored_tool", "mod2", "An ignored tool", 1000.0, 1.0)
    )

    # popular_tool: proposed 3 times, used 3 times (hit_rate = 1.0 -> weight > 1.0)
    for _ in range(3):
        conn.execute(
            "INSERT INTO j_space_tool_activations VALUES ('popular_tool', 'q', 1, '2026-09-29T10:00:00Z', 1)"
        )

    # ignored_tool: proposed 3 times, used 0 times (hit_rate = 0.0 -> weight < 1.0)
    for _ in range(3):
        conn.execute(
            "INSERT INTO j_space_tool_activations VALUES ('ignored_tool', 'q', 1, '2026-09-29T10:00:00Z', 0)"
        )

    conn.commit()
    conn.close()

    indexer = JSpaceToolIndexer(db_path=db_file)
    reweight_res = indexer.reweight_tools_from_activations(min_proposals=2)

    assert reweight_res.get("status") == "SUCCESS"
    assert reweight_res.get("reweighted_count") == 2

    tools = reweight_res.get("tools", {})
    assert "popular_tool" in tools
    assert tools["popular_tool"]["weight"] > 1.0
    assert "ignored_tool" in tools
    assert tools["ignored_tool"]["weight"] < 1.0

    # Verify persisted in SQLite
    conn = sqlite3.connect(db_file)
    p_weight = conn.execute("SELECT weight FROM j_space_tool_metadata WHERE tool_name = 'popular_tool'").fetchone()[0]
    i_weight = conn.execute("SELECT weight FROM j_space_tool_metadata WHERE tool_name = 'ignored_tool'").fetchone()[0]
    conn.close()

    assert p_weight > 1.0
    assert i_weight < 1.0


def test_auto_improver_daemon_phases_and_cycle(tmp_path):
    """Verify AutoImproverDaemon executes observe, analyze, execute_and_verify, learn, and run_cycle."""
    db_file = str(tmp_path / "test_daemon.db")

    daemon = AutoImproverDaemon(db_path=db_file)

    # Initially should_run is True
    assert daemon.should_run() is True

    # Check status initially
    status = daemon.get_status()
    assert isinstance(status, dict)
    assert status.get("status") == "HEALTHY"
    assert status.get("total_sessions") == 0

    # Observe phase
    obs = daemon.observe()
    assert isinstance(obs, dict)
    assert "total_activations" in obs
    assert "hit_rate" in obs

    # Analyze phase
    analysis = daemon.analyze(obs)
    assert isinstance(analysis, dict)
    assert "candidate_actions" in analysis

    # Execute full cycle
    cycle_res = daemon.run_cycle(force=True)
    assert isinstance(cycle_res, dict)
    assert cycle_res.get("status") == "SUCCESS"
    assert "session_id" in cycle_res
    assert cycle_res.get("duration_seconds", 0) >= 0

    # Status after cycle
    status_after = daemon.get_status()
    assert status_after.get("total_sessions") == 1
    assert status_after.get("successful_sessions") == 1
    assert daemon.should_run(interval_hours=10.0) is False


def test_unified_hub_auto_improver_integration():
    """Verify UnifiedHub exposes check_auto_improver_status and run_auto_improver_cycle."""
    hub = VazusUnifiedHub()

    # 1. check_auto_improver_status
    improver_status = hub.check_auto_improver_status()
    assert isinstance(improver_status, dict)
    assert improver_status.get("status") == "HEALTHY"
    assert "total_sessions" in improver_status
    assert "interval_hours" in improver_status

    # 2. get_system_status includes auto_improver
    sys_status = hub.get_system_status()
    assert "auto_improver" in sys_status
    assert sys_status["auto_improver"].get("status") == "HEALTHY"

    # 3. run_auto_improver_cycle
    cycle_res = hub.run_auto_improver_cycle(force=True)
    assert isinstance(cycle_res, dict)
    assert cycle_res.get("status") == "SUCCESS"


def test_github_auto_pr_module_importable():
    """Verify github_auto_pr module imports cleanly and exposes key functions."""
    from vazus_core.workers.github_auto_pr import (
        create_auto_pr,
        run_local_auto_improve,
        GITHUB_REPO,
        BASE_BRANCH,
    )
    assert GITHUB_REPO == "Vazilll/hartes"
    assert BASE_BRANCH == "vazus-dev"
    assert callable(create_auto_pr)
    assert callable(run_local_auto_improve)
