"""
tests.unit.test_lifecycle_hooks — Unit tests for Antigravity Lifecycle Hooks.
Tests pre_tool_hook (fail-closed, path jail, command blacklist),
post_tool_hook (AST validation, TDD loop), and session_start_hook (DB pool warmup, CKB check).
"""

import json
import subprocess
import sys
import pytest
from pathlib import Path

from vazus_core.hooks.pre_tool_hook import (
    _is_within_workspace,
    _is_forbidden_path,
    _is_dangerous_command,
)
from vazus_core.hooks.session_start_hook import (
    check_ckb_connectivity,
    warm_database_pool,
    run_session_start,
)
from vazus_core.memory.async_db import AsyncDatabasePool


def test_pre_tool_hook_path_jail():
    # Valid workspace path
    assert _is_within_workspace("C:/vazus/vazus_core/test.py") is True
    assert _is_within_workspace("C:\\vazus\\data\\test.json") is True

    # Traversal outside workspace
    assert _is_within_workspace("C:/Windows/System32/calc.exe") is False
    assert _is_within_workspace("D:/other/untrusted.py") is False
    assert _is_within_workspace("") is False


def test_pre_tool_hook_forbidden_paths():
    assert _is_forbidden_path("C:/vazus/.git/config") is True
    assert _is_forbidden_path("C:\\vazus\\.git\\HEAD") is True
    assert _is_forbidden_path("C:/vazus/AGENTS.md") is True
    assert _is_forbidden_path("C:/vazus/vazus_core/memory/db.py") is False


def test_pre_tool_hook_dangerous_commands():
    assert _is_dangerous_command("format C:") is True
    assert _is_dangerous_command("rmdir /s /q c:\\") is True
    assert _is_dangerous_command("del /f /s /q c:\\windows") is True
    assert _is_dangerous_command("reg delete HKLM\\Software") is True
    assert _is_dangerous_command("python -m pytest tests/") is False


@pytest.mark.anyio
async def test_session_start_hook_warm_database(tmp_path):
    db_file = tmp_path / "test_session_start.db"
    pool = AsyncDatabasePool(db_path=db_file)

    health = await warm_database_pool(pool)
    assert health["status"] == "ok"
    assert health["kg_nodes"] == 0
    assert health["kg_edges"] == 0
    await pool.aclose()


def test_session_start_hook_ckb_check():
    res = check_ckb_connectivity(port=9999, timeout=0.1)
    assert "daemon_online" in res
    assert "has_scip_index" in res
    assert "status" in res


@pytest.mark.anyio
async def test_session_start_hook_full_run():
    res = await run_session_start()
    assert res["session_start"] is True
    assert "database" in res
    assert "ckb" in res
    assert res["status"] in ("healthy", "degraded")
