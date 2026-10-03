"""
tests/unit/test_indexing_lock_manager.py — Verification of Indexing Concurrency Lock & RAM Leak Prevention.
Tests IndexingLockManager, process-table checks, stale eviction, post_tool_hook decoupling, and limits.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
import psutil
import pytest

from vazus_core.maintenance.auto_index_runner import (
    IndexingLockManager,
    SCIPIndexSynchronizer,
    AutoIndexRunner,
    run_maintenance,
    VAZUS_ROOT,
)


@pytest.fixture(autouse=True)
def clean_lock_state():
    """Ensures indexing.lock is clean before and after each test."""
    IndexingLockManager.release(force=True)
    dirty_file = VAZUS_ROOT / ".ckb" / "index_dirty"
    if dirty_file.exists():
        dirty_file.unlink(missing_ok=True)
    yield
    IndexingLockManager.release(force=True)
    if dirty_file.exists():
        dirty_file.unlink(missing_ok=True)


def test_lock_acquire_and_release():
    """Verifies atomic acquisition, payload structure, and clean release."""
    acquired = IndexingLockManager.acquire(trigger="test_unit")
    assert acquired is True
    assert IndexingLockManager.LOCK_FILE.exists()

    data = json.loads(IndexingLockManager.LOCK_FILE.read_text(encoding="utf-8"))
    assert data["pid"] == os.getpid()
    assert data["trigger"] == "test_unit"
    assert "started_at" in data
    assert "hostname" in data

    IndexingLockManager.release()
    assert not IndexingLockManager.LOCK_FILE.exists()


def test_lock_prevents_duplicate_acquisition():
    """Verifies that an active lock rejects concurrent acquisition."""
    assert IndexingLockManager.acquire(trigger="first") is True
    # Second acquisition attempt in same process or by another agent
    # Note: IndexingLockManager checks if current lock is active
    assert IndexingLockManager.acquire(trigger="second") is False
    IndexingLockManager.release()


def test_stale_lock_eviction():
    """Verifies that stale locks (> 120s) are evicted automatically."""
    IndexingLockManager.LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    stale_payload = {
        "pid": 999999,
        "started_at": time.time() - 300.0,  # 300s old
        "trigger": "stale_test",
        "hostname": "test-host",
    }
    IndexingLockManager.LOCK_FILE.write_text(json.dumps(stale_payload), encoding="utf-8")

    # Acquire should evict the stale lock and succeed
    assert IndexingLockManager.acquire(trigger="new_pass") is True
    data = json.loads(IndexingLockManager.LOCK_FILE.read_text(encoding="utf-8"))
    assert data["pid"] == os.getpid()
    assert data["trigger"] == "new_pass"
    IndexingLockManager.release()


def test_dead_pid_lock_eviction():
    """Verifies that a lock held by a dead PID is evicted even if young."""
    IndexingLockManager.LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    dead_payload = {
        "pid": 999999,  # non-existent PID
        "started_at": time.time() - 10.0,
        "trigger": "dead_proc",
        "hostname": "test-host",
    }
    IndexingLockManager.LOCK_FILE.write_text(json.dumps(dead_payload), encoding="utf-8")

    assert IndexingLockManager.acquire(trigger="recovery") is True
    IndexingLockManager.release()


def test_corrupted_lock_file_recovery():
    """Verifies that a corrupted or malformed lock file is safely evicted."""
    IndexingLockManager.LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    IndexingLockManager.LOCK_FILE.write_text("NOT_VALID_JSON{{{", encoding="utf-8")

    assert IndexingLockManager.acquire(trigger="corrupt_recovery") is True
    assert IndexingLockManager.LOCK_FILE.exists()
    IndexingLockManager.release()


def test_run_maintenance_decoupled_default():
    """Verifies that run_maintenance defaults to trigger_indexer=False and marks dirty."""
    res = run_maintenance(paths=["vazus_core/maintenance/auto_index_runner.py"])
    assert res["status"] == "OK"
    assert res["reindexed"] is False
    assert res["indexer_details"]["reason"] == "TRIGGER_INDEXER_FALSE"

    syncer = SCIPIndexSynchronizer()
    assert syncer.dirty_marker.exists()
    syncer.clear_dirty()


def test_trigger_scip_reindex_locked_behavior():
    """Verifies that trigger_scip_reindex returns SKIPPED/LOCKED if lock is already held."""
    assert IndexingLockManager.acquire(trigger="external") is True
    syncer = SCIPIndexSynchronizer()
    res = syncer.trigger_scip_reindex(background=False)
    assert res["status"] == "SKIPPED"
    assert res["reason"] == "LOCKED"
    IndexingLockManager.release()


def test_recycled_pid_lock_eviction():
    """Verifies that a lock held by a recycled system PID (e.g. svchost.exe) is evicted."""
    # Find an active non-indexer system process
    proc = next((p for p in psutil.process_iter(['pid', 'name']) if (p.info['name'] or '').lower() in ['svchost.exe', 'explorer.exe']), None)
    if proc:
        IndexingLockManager.LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "pid": proc.pid,
            "started_at": time.time() - 30.0,  # 30s ago (not stale by time)
            "trigger": "recycled_test",
            "hostname": "test-host",
        }
        IndexingLockManager.LOCK_FILE.write_text(json.dumps(payload), encoding="utf-8")

        # Because PID belongs to svchost/explorer, is_pid_indexer is False -> evicts and acquires
        acquired = IndexingLockManager.acquire(trigger="recycled_recovery")
        assert acquired is True, "Failed to evict lock held by recycled non-indexer PID"
        IndexingLockManager.release(force=True)


def test_shell_exclusion_in_indexer_detection():
    """Verifies that is_indexer_process_running excludes shell processes (powershell, cmd, bash)."""
    running, r_pid, r_desc = IndexingLockManager.is_indexer_process_running()
    if running:
        # If any process is running, ensure it's not a shell
        assert "powershell" not in r_desc.lower()
        assert "cmd" not in r_desc.lower()
        assert "bash" not in r_desc.lower()


def test_dirty_marker_preserved_on_indexing_failure():
    """Verifies that clear_dirty() is NOT called when indexing times out or fails."""
    syncer = SCIPIndexSynchronizer()
    syncer.mark_dirty()
    assert syncer.dirty_marker.exists()

    # Trigger with an extremely tiny timeout to trigger watchdog termination
    syncer.trigger_scip_reindex(background=False, timeout=0.00001)

    # Dirty marker must STILL exist because indexing did not succeed cleanly
    assert syncer.dirty_marker.exists()
    syncer.clear_dirty()


def test_terminate_proc_tree_synchronous():
    """Verifies that _terminate_proc_tree synchronously waits for process death."""
    sub = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(10)"])
    assert psutil.pid_exists(sub.pid)
    SCIPIndexSynchronizer._terminate_proc_tree(sub.pid, timeout=3.0)
    assert not psutil.pid_exists(sub.pid)

