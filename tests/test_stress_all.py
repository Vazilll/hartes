"""
Empirical Stress Test Harness for Milestone 1:
- vazus_core/system_daemon.py
- vazus_core/daemon_sidecar.py

Executes 4 stress tests:
1. Rapid 3x Start -> Status -> Stop cycle.
2. Concurrent HTTP status requests (10 concurrent requests).
3. Stale PID file recovery.
4. Non-blocking SQLite WAL watcher behavior under database write lock.
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(r"C:\vazus")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import time
import json
import socket
import sqlite3
import tempfile
import threading
import subprocess
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

PYTHON_EXE = r"C:\vazus\.venv\Scripts\python.exe"
PROJECT_ROOT = Path(r"C:\vazus")
PID_FILE = PROJECT_ROOT / "vazus.pid"
PORT = 8765
STATUS_URL = f"http://127.0.0.1:{PORT}/status"
HEALTH_URL = f"http://127.0.0.1:{PORT}/healthz"

results = {
    "test1_rapid_cycles": [],
    "test2_concurrent_http": {},
    "test3_stale_pid": {},
    "test4_wal_watcher": {}
}


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(('127.0.0.1', port)) == 0


def run_cli_command(args: list[str]) -> tuple[int, str, str]:
    cmd = [PYTHON_EXE, "-m", "vazus_core.system_daemon"] + args
    res = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=False)
    stdout = res.stdout.decode("utf-8", errors="replace").strip() if res.stdout else ""
    stderr = res.stderr.decode("utf-8", errors="replace").strip() if res.stderr else ""
    return res.returncode, stdout, stderr


def run_test_1():
    print("\n--- STRESS TEST 1: Rapid 3x Start -> Status -> Stop Cycle ---")
    cycles = []
    for i in range(1, 4):
        print(f"\n[Cycle {i}] Starting daemon...")
        start_t0 = time.time()
        ret, stdout, stderr = run_cli_command(["start"])
        start_duration = time.time() - start_t0
        print(f"[Cycle {i}] Start returncode={ret}, stdout='{stdout}', duration={start_duration:.3f}s")

        # Check PID file & port
        time.sleep(0.5)
        pid_exists = PID_FILE.exists()
        pid_val = PID_FILE.read_text(encoding="utf-8").strip() if pid_exists else None
        port_active = is_port_in_use(PORT)
        print(f"[Cycle {i}] PID file exists={pid_exists} (PID={pid_val}), Port {PORT} active={port_active}")

        # Check HTTP status
        http_ok = False
        http_data = {}
        try:
            with urllib.request.urlopen(STATUS_URL, timeout=2) as resp:
                if resp.status == 200:
                    http_ok = True
                    http_data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            print(f"[Cycle {i}] HTTP request error: {e}")

        # CLI status command
        status_ret, status_out, status_err = run_cli_command(["status"])
        print(f"[Cycle {i}] Status CLI stdout:\n{status_out}")

        # Stop daemon
        print(f"[Cycle {i}] Stopping daemon...")
        stop_t0 = time.time()
        stop_ret, stop_out, stop_err = run_cli_command(["stop"])
        stop_duration = time.time() - stop_t0
        print(f"[Cycle {i}] Stop returncode={stop_ret}, stdout='{stop_out}', duration={stop_duration:.3f}s")

        time.sleep(0.5)
        post_pid_exists = PID_FILE.exists()
        post_port_active = is_port_in_use(PORT)
        print(f"[Cycle {i}] Post-stop PID file exists={post_pid_exists}, Port active={post_port_active}")

        cycle_passed = (
            ret == 0 and
            pid_exists and
            port_active and
            http_ok and
            stop_ret == 0 and
            not post_pid_exists and
            not post_port_active
        )

        cycles.append({
            "cycle": i,
            "passed": cycle_passed,
            "pid": pid_val,
            "start_duration_sec": round(start_duration, 3),
            "stop_duration_sec": round(stop_duration, 3),
            "http_ok": http_ok,
            "post_stop_pid_exists": post_pid_exists,
            "post_stop_port_active": post_port_active
        })

    results["test1_rapid_cycles"] = cycles
    all_passed = all(c["passed"] for c in cycles)
    print(f"\nSTRESS TEST 1 RESULT: {'PASS' if all_passed else 'FAIL'}")


def run_test_2():
    print("\n--- STRESS TEST 2: Concurrent HTTP Status Requests (10 requests) ---")
    print("Starting daemon for concurrent HTTP test...")
    run_cli_command(["start"])
    time.sleep(1.0)

    if not is_port_in_use(PORT):
        print("ERROR: Daemon failed to start for Test 2.")
        results["test2_concurrent_http"] = {"passed": False, "error": "Daemon failed to start"}
        return

    num_requests = 10
    http_results = []
    threads = []

    def make_request(req_id: int):
        t0 = time.time()
        try:
            with urllib.request.urlopen(STATUS_URL, timeout=3) as resp:
                elapsed = time.time() - t0
                status_code = resp.status
                content = json.loads(resp.read().decode("utf-8"))
                http_results.append({
                    "id": req_id,
                    "status_code": status_code,
                    "elapsed_sec": round(elapsed, 4),
                    "pid": content.get("pid"),
                    "service": content.get("service")
                })
        except Exception as e:
            elapsed = time.time() - t0
            http_results.append({
                "id": req_id,
                "status_code": 0,
                "elapsed_sec": round(elapsed, 4),
                "error": str(e)
            })

    for i in range(num_requests):
        t = threading.Thread(target=make_request, args=(i+1,))
        threads.append(t)

    t_start = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    total_time = time.time() - t_start

    print(f"Executed {num_requests} concurrent requests in {total_time:.4f}s")
    success_count = sum(1 for r in http_results if r.get("status_code") == 200)
    print(f"Successful 200 OK responses: {success_count}/{num_requests}")
    for r in http_results:
        print(f"  Req #{r['id']}: status={r.get('status_code')}, elapsed={r.get('elapsed_sec')}s, err={r.get('error', 'None')}")

    # Clean up daemon
    run_cli_command(["stop"])
    time.sleep(0.5)

    test_passed = (success_count == num_requests)
    results["test2_concurrent_http"] = {
        "passed": test_passed,
        "total_requests": num_requests,
        "success_count": success_count,
        "total_time_sec": round(total_time, 4),
        "details": http_results
    }
    print(f"STRESS TEST 2 RESULT: {'PASS' if test_passed else 'FAIL'}")


def run_test_3():
    print("\n--- STRESS TEST 3: Stale PID Recovery ---")
    # Ensure daemon is stopped
    run_cli_command(["stop"])
    time.sleep(0.5)

    # 1. Create a stale PID file with a non-existent PID (e.g. 999999)
    fake_pid = 999999
    PID_FILE.write_text(str(fake_pid), encoding="utf-8")
    print(f"Created fake PID file with PID {fake_pid}")

    # Check status CLI
    print("Executing 'status' command on stale PID file...")
    ret_status, out_status, err_status = run_cli_command(["status"])
    print(f"Status output:\n{out_status}")
    stale_pid_cleaned_after_status = not PID_FILE.exists()
    print(f"Stale PID file cleaned up by status check: {stale_pid_cleaned_after_status}")

    # 2. Re-create stale PID file and test 'start' command recovery
    PID_FILE.write_text(str(fake_pid), encoding="utf-8")
    print(f"Re-created fake PID file with PID {fake_pid}")
    print("Executing 'start' command with existing stale PID file...")
    ret_start, out_start, err_start = run_cli_command(["start"])
    time.sleep(0.5)

    new_pid_exists = PID_FILE.exists()
    new_pid_val = PID_FILE.read_text(encoding="utf-8").strip() if new_pid_exists else None
    print(f"Daemon started output:\n{out_start}")
    print(f"New PID file exists={new_pid_exists}, New PID={new_pid_val} (fake was {fake_pid})")

    start_recovered = new_pid_exists and new_pid_val != str(fake_pid) and is_port_in_use(PORT)

    # Stop daemon
    run_cli_command(["stop"])
    time.sleep(0.5)

    test_passed = stale_pid_cleaned_after_status and start_recovered
    results["test3_stale_pid"] = {
        "passed": test_passed,
        "stale_pid_cleaned_after_status": stale_pid_cleaned_after_status,
        "start_recovered": start_recovered,
        "new_pid": new_pid_val
    }
    print(f"STRESS TEST 3 RESULT: {'PASS' if test_passed else 'FAIL'}")


def run_test_4():
    print("\n--- STRESS TEST 4: Non-blocking WAL Watcher Handling ---")
    # Test TranscriptWatcher behavior under SQLite write lock
    from vazus_core.daemon_sidecar import TranscriptWatcher

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        summaries_db = tmp_path / "conversation_summaries.db"
        conv_dir = tmp_path / "conversations"
        conv_dir.mkdir()
        conv_db = conv_dir / "conv_test_123.db"
        state_file = tmp_path / "daemon_state.json"

        # 1. Initialize schema in summaries DB and conv DB in WAL mode
        print("Setting up test SQLite WAL databases...")
        conn_s = sqlite3.connect(summaries_db)
        conn_s.execute("PRAGMA journal_mode=WAL;")
        conn_s.execute("CREATE TABLE conversation_summaries (conversation_id TEXT PRIMARY KEY, step_count INTEGER, last_modified_time TEXT);")
        conn_s.execute("INSERT INTO conversation_summaries VALUES ('conv_test_123', 1, '2026-08-07T10:00:00Z');")
        conn_s.commit()
        conn_s.close()

        conn_c = sqlite3.connect(conv_db)
        conn_c.execute("PRAGMA journal_mode=WAL;")
        conn_c.execute("CREATE TABLE steps (idx INTEGER PRIMARY KEY, status INTEGER, step_payload BLOB);")
        conn_c.execute("INSERT INTO steps VALUES (0, 0, 'USER: Execute pytest on project');")
        conn_c.commit()
        conn_c.close()

        # 2. Acquire EXCLUSIVE write lock on conv_db using a persistent connection in an uncommitted transaction
        print("Acquiring EXCLUSIVE write lock on conversation DB...")
        lock_conn = sqlite3.connect(conv_db)
        lock_conn.execute("PRAGMA journal_mode=WAL;")
        lock_conn.execute("BEGIN EXCLUSIVE;")
        lock_conn.execute("INSERT INTO steps VALUES (1, 0, 'USER: Second step under lock');")
        # Do NOT commit yet — lock is active!

        # 3. Create TranscriptWatcher and call poll_once() while database is locked
        print("Polling watcher while write lock is held...")
        watcher = TranscriptWatcher(cli_dir=tmp_path, state_file=state_file)

        poll_t0 = time.time()
        events = []
        poll_exception = None
        try:
            events = watcher.poll_once()
        except Exception as e:
            poll_exception = str(e)
        poll_duration = time.time() - poll_t0

        print(f"Watcher poll_once() completed in {poll_duration:.4f}s")
        print(f"Events extracted: {len(events)}, Exception: {poll_exception}")
        for evt in events:
            print(f"  Extracted Event: conv={evt.conversation_id}, step={evt.step_idx}, text='{evt.user_input}'")

        # 4. Release write lock
        lock_conn.rollback()
        lock_conn.close()

        # 5. Evaluate results
        # Read-only URI connection (file:...mode=ro) in WAL mode allows reading uncommitted/committed data without blocking or raising OperationalError ("database is locked")
        wal_non_blocking = (poll_exception is None) and (poll_duration < 2.0)
        events_valid = len(events) >= 1

        test_passed = wal_non_blocking and events_valid
        results["test4_wal_watcher"] = {
            "passed": test_passed,
            "poll_duration_sec": round(poll_duration, 4),
            "events_count": len(events),
            "poll_exception": poll_exception,
            "wal_non_blocking": wal_non_blocking
        }
        print(f"STRESS TEST 4 RESULT: {'PASS' if test_passed else 'FAIL'}")


if __name__ == "__main__":
    run_test_1()
    run_test_2()
    run_test_3()
    run_test_4()

    print("\n================ FINAL RESULTS SUMMARY ================")
    print(json.dumps(results, indent=2))
    
    all_tests_passed = (
        all(c["passed"] for c in results["test1_rapid_cycles"]) and
        results["test2_concurrent_http"].get("passed", False) and
        results["test3_stale_pid"].get("passed", False) and
        results["test4_wal_watcher"].get("passed", False)
    )

    print(f"\nOVERALL VERDICT: {'APPROVE' if all_tests_passed else 'REJECT'}")
    sys.exit(0 if all_tests_passed else 1)
