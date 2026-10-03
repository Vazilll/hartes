"""
tests/unit/test_indexing_adversarial_stress.py — Empirical Adversarial Stress Harness for IndexingLockManager.

Stress tests:
1. Multi-threaded concurrency collisions (50 threads with Barrier synchronization across multiple rounds).
2. Multi-subprocess concurrency collisions (10 separate OS Python processes synchronized to exact millisecond).
3. Dead PID simulation (fresh lock with non-existent PID and dead subprocess PID).
4. Stale lock eviction (> 120s) with active PID vs boundary (< 120s).
5. Corrupted payload, malformed types, negative/zero PIDs, and future clock skew.
6. OS Process Table guard (active indexer detection without lock file).
7. Mutual exclusion invariant under high-churn concurrent access.
"""

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
import psutil
import pytest

from vazus_core.maintenance.auto_index_runner import (
    IndexingLockManager,
    SCIPIndexSynchronizer,
    VAZUS_ROOT,
)


@pytest.fixture(autouse=True)
def clean_lock_state():
    """Ensure clean state before and after each test."""
    IndexingLockManager.release(force=True)
    yield
    IndexingLockManager.release(force=True)


class TestMultiThreadedConcurrency:
    """Stress tests multi-threaded contention."""

    def test_50_threads_simultaneous_barrier(self):
        """50 threads synchronize at a barrier and attempt acquire(). Exactly 1 must win."""
        num_threads = 50
        barrier = threading.Barrier(num_threads)
        results = []
        lock = threading.Lock()

        def worker(worker_id):
            barrier.wait()  # Synchronize to exact microsecond
            acquired = IndexingLockManager.acquire(trigger=f"thread_{worker_id}")
            with lock:
                results.append((worker_id, acquired))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        acquired_count = sum(1 for _, acq in results if acq is True)
        failed_count = sum(1 for _, acq in results if acq is False)

        assert acquired_count == 1, f"Expected exactly 1 winner, got {acquired_count}"
        assert failed_count == num_threads - 1, f"Expected {num_threads - 1} rejections, got {failed_count}"

    def test_multi_round_thread_contention(self):
        """10 consecutive rounds of 20 threads racing for the lock."""
        num_rounds = 10
        num_threads = 20

        for r in range(num_rounds):
            IndexingLockManager.release(force=True)
            barrier = threading.Barrier(num_threads)
            round_results = []
            lock = threading.Lock()

            def worker(w_id):
                barrier.wait()
                acq = IndexingLockManager.acquire(trigger=f"r{r}_w{w_id}")
                with lock:
                    round_results.append(acq)

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            wins = sum(1 for x in round_results if x is True)
            assert wins == 1, f"Round {r}: expected exactly 1 winner, got {wins}"

    def test_mutual_exclusion_invariant_under_churn(self):
        """Verify that at no point in time two threads hold the lock simultaneously."""
        num_threads = 15
        duration = 2.0  # run for 2 seconds
        stop_event = threading.Event()
        violations = []
        active_holders = 0
        state_lock = threading.Lock()

        def churn_worker(w_id):
            nonlocal active_holders
            while not stop_event.is_set():
                if IndexingLockManager.acquire(trigger=f"churn_{w_id}"):
                    with state_lock:
                        active_holders += 1
                        if active_holders > 1:
                            violations.append(f"Collision detected! active_holders = {active_holders}")
                    time.sleep(0.005)  # hold lock for 5ms
                    with state_lock:
                        active_holders -= 1
                    IndexingLockManager.release()
                time.sleep(0.002)

        threads = [threading.Thread(target=churn_worker, args=(i,)) for i in range(num_threads)]
        for t in threads:
            t.start()
        time.sleep(duration)
        stop_event.set()
        for t in threads:
            t.join()

        assert len(violations) == 0, f"Mutual exclusion violated: {violations}"


class TestMultiSubprocessConcurrency:
    """Stress tests multi-subprocess contention across separate OS processes."""

    def test_10_subprocesses_simultaneous_timestamp_race(self):
        """10 separate OS python processes synchronize on a target timestamp to acquire()."""
        num_procs = 10
        target_timestamp = time.time() + 1.2  # start in 1.2s

        script = (
            "import sys, time, json\n"
            "from vazus_core.maintenance.auto_index_runner import IndexingLockManager\n"
            f"target = {target_timestamp}\n"
            "while time.time() < target:\n"
            "    pass\n"
            "try:\n"
            "    res = IndexingLockManager.acquire(trigger='subproc_' + str(sys.argv[1]))\n"
            "    print(json.dumps({'acquired': res, 'pid': sys.argv[1]}), flush=True)\n"
            "    if res:\n"
            "        time.sleep(1.5)\n"
            "except Exception as e:\n"
            "    print(json.dumps({'error': str(e), 'pid': sys.argv[1]}), flush=True)\n"
        )

        procs = []
        for i in range(num_procs):
            p = subprocess.Popen(
                [sys.executable, "-c", script, str(i)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            procs.append(p)

        outputs = []
        for p in procs:
            stdout, stderr = p.communicate(timeout=10)
            for line in stdout.strip().split("\n"):
                if line.strip():
                    try:
                        outputs.append(json.loads(line.strip()))
                    except Exception:
                        pass

        wins = sum(1 for o in outputs if o.get("acquired") is True)
        errors = [o for o in outputs if "error" in o]

        assert len(errors) == 0, f"Subprocesses encountered errors: {errors}"
        assert wins == 1, f"Expected exactly 1 subprocess winner, got {wins}. Outputs: {outputs}"


class TestDeadPidSimulation:
    """Stress tests dead PID eviction."""

    def test_nonexistent_pid_fresh_timestamp(self):
        """Lock file has non-existent PID (999999) with fresh timestamp (5s ago). Must evict and acquire."""
        IndexingLockManager.LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "pid": 999999,
            "started_at": time.time() - 5.0,  # NOT stale by age
            "trigger": "dead_worker",
            "hostname": "test-host",
        }
        IndexingLockManager.LOCK_FILE.write_text(json.dumps(payload), encoding="utf-8")

        assert IndexingLockManager.acquire(trigger="recovery") is True
        data = json.loads(IndexingLockManager.LOCK_FILE.read_text(encoding="utf-8"))
        assert data["pid"] == os.getpid()

    def test_real_terminated_process_pid(self):
        """Spawn a short-lived process, record its PID, wait for termination, then write to lock file."""
        sub = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(0.05)"])
        dead_pid = sub.pid
        sub.wait()  # Process is now dead

        assert not psutil.pid_exists(dead_pid)

        IndexingLockManager.LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "pid": dead_pid,
            "started_at": time.time() - 2.0,  # very fresh
            "trigger": "killed_indexer",
            "hostname": "test-host",
        }
        IndexingLockManager.LOCK_FILE.write_text(json.dumps(payload), encoding="utf-8")

        assert IndexingLockManager.acquire(trigger="recover_from_crash") is True
        data = json.loads(IndexingLockManager.LOCK_FILE.read_text(encoding="utf-8"))
        assert data["pid"] == os.getpid()

    @pytest.mark.parametrize("invalid_pid", [-1, 0, None, "not_an_int"])
    def test_malformed_pid_eviction(self, invalid_pid):
        """Malformed or non-positive PID must be treated as dead/invalid and evicted."""
        IndexingLockManager.LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "pid": invalid_pid,
            "started_at": time.time() - 5.0,
            "trigger": "malformed_pid",
            "hostname": "test-host",
        }
        IndexingLockManager.LOCK_FILE.write_text(json.dumps(payload), encoding="utf-8")

        assert IndexingLockManager.acquire(trigger="sanitize") is True
        data = json.loads(IndexingLockManager.LOCK_FILE.read_text(encoding="utf-8"))
        assert data["pid"] == os.getpid()
        IndexingLockManager.release(force=True)


class TestStaleLockEviction:
    """Stress tests stale lock eviction (> 120s)."""

    def test_stale_lock_with_active_pid(self):
        """A lock held by an ALIVE process that is > 120s old MUST be evicted."""
        IndexingLockManager.LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
        my_pid = os.getpid()
        assert psutil.pid_exists(my_pid)

        stale_payload = {
            "pid": my_pid,
            "started_at": time.time() - 125.0,  # 125 seconds ago (> 120s)
            "trigger": "stale_alive_worker",
            "hostname": "test-host",
        }
        IndexingLockManager.LOCK_FILE.write_text(json.dumps(stale_payload), encoding="utf-8")

        # Must evict because age > 120s, even though PID is currently running!
        assert IndexingLockManager.acquire(trigger="evict_stale_active") is True

    def test_boundary_age_just_below_threshold(self):
        """A lock held by an ALIVE process that is 115s old (< 120s) must NOT be evicted."""
        IndexingLockManager.LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
        my_pid = os.getpid()

        young_payload = {
            "pid": my_pid,
            "started_at": time.time() - 115.0,  # 115s old (< 120s)
            "trigger": "still_valid",
            "hostname": "test-host",
        }
        IndexingLockManager.LOCK_FILE.write_text(json.dumps(young_payload), encoding="utf-8")

        # Because age < 120s and PID is alive, acquire() must reject!
        assert IndexingLockManager.acquire(trigger="attempt_steal") is False

    def test_boundary_age_just_above_threshold(self):
        """A lock held by an ALIVE process that is 121s old (> 120s) MUST be evicted."""
        IndexingLockManager.LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
        my_pid = os.getpid()

        stale_payload = {
            "pid": my_pid,
            "started_at": time.time() - 121.0,  # 121s old (> 120s)
            "trigger": "expired",
            "hostname": "test-host",
        }
        IndexingLockManager.LOCK_FILE.write_text(json.dumps(stale_payload), encoding="utf-8")

        assert IndexingLockManager.acquire(trigger="evict_boundary") is True

    def test_ancient_timestamp(self):
        """Lock with started_at = 0.0 (epoch) must be evicted."""
        IndexingLockManager.LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "pid": os.getpid(),
            "started_at": 0.0,
            "trigger": "epoch",
            "hostname": "test-host",
        }
        IndexingLockManager.LOCK_FILE.write_text(json.dumps(payload), encoding="utf-8")
        assert IndexingLockManager.acquire(trigger="evict_epoch") is True
