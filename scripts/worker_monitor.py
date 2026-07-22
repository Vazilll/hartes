#!/usr/bin/env python3
"""
worker_monitor.py v2 — Autonomous Worker Health Monitor with psutil.

Improvements over v1:
  - psutil-based CPU% and RSS memory tracking per worker PID
  - Recursive process-tree kill (prevents zombie orphans)
  - High-CPU hang detection (>95% for >20 cycles → likely infinite loop)
  - Memory limit enforcement (auto-kill if RSS > MAX_WORKER_MEM_MB)
  - Stuck detection refined: uses both progress_age AND psutil cpu_percent
  - Summary includes per-worker resource stats

Usage:
  python scripts/worker_monitor.py [--interval 30] [--once]

The monitor runs in a loop or can be called once (--once) by a scheduler.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

WORKSPACE = Path("C:/vazus/pyenv")
WORKERS_DIR = WORKSPACE / "logs" / "workers"
MONITOR_FILE = WORKERS_DIR / "_monitor.json"
PYTHON = WORKSPACE / ".venv" / "Scripts" / "python.exe"
STALE_SEC = 120        # worker is "stuck" if progress not updated in 2 min
CLEANUP_INTERVAL = 86400  # run cleanup once per day
MAX_WORKER_MEM_MB = 2048  # auto-kill worker if RSS exceeds 2 GB
HIGH_CPU_CYCLES_THRESHOLD = 20  # consecutive monitor cycles at >95% CPU → stuck

CREATE_NO_WINDOW = 0x08000000
_last_cleanup = 0.0
_high_cpu_counters: dict[str, int] = {}  # task_id → consecutive high-CPU cycles

# Try importing psutil; fall back gracefully
try:
    import psutil
    _PSUTIL = True
except ImportError:
    _PSUTIL = False


def read_status(task_dir: Path) -> str:
    sf = task_dir / "status.txt"
    return sf.read_text(encoding="utf-8").strip() if sf.exists() else "unknown"


def read_meta(task_dir: Path) -> dict:
    mf = task_dir / "meta.json"
    if not mf.exists():
        return {}
    try:
        return json.loads(mf.read_text(encoding="utf-8"))
    except Exception:
        return {}


def read_progress_age(task_dir: Path) -> float:
    """Return seconds since progress.txt was last written. 999 if missing."""
    pf = task_dir / "progress.txt"
    if not pf.exists():
        return 999.0
    try:
        return time.time() - pf.stat().st_mtime
    except Exception:
        return 999.0


def get_pid(task_dir: Path) -> int | None:
    pid_file = task_dir / "pid.txt"
    if not pid_file.exists():
        return None
    try:
        return int(pid_file.read_text().strip())
    except Exception:
        return None


def kill_process_tree(pid: int) -> bool:
    """Kill entire process tree rooted at pid. Returns True if any process was killed."""
    if not _PSUTIL:
        # Fallback: taskkill /T kills tree on Windows
        try:
            result = subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                capture_output=True, timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    killed = False
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        # Terminate all children first
        for child in children:
            try:
                child.terminate()
                killed = True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        # Terminate parent
        try:
            parent.terminate()
            killed = True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        # Wait and force-kill survivors
        gone, alive = psutil.wait_procs(children + [parent], timeout=3.0)
        for p in alive:
            try:
                p.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
    return killed


def kill_pid(task_dir: Path) -> bool:
    pid = get_pid(task_dir)
    if pid is None:
        return False
    return kill_process_tree(pid)


def get_process_stats(pid: int) -> dict | None:
    """Get CPU%, RSS MB, and status for a PID. Returns None if process not found."""
    if not _PSUTIL:
        return None
    try:
        p = psutil.Process(pid)
        with p.oneshot():
            cpu = p.cpu_percent(interval=0.1)
            rss_mb = p.memory_info().rss / (1024 * 1024)
            status = p.status()
        return {"cpu_pct": round(cpu, 1), "rss_mb": round(rss_mb, 1), "status": status}
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None


def respawn(meta: dict, task_id: str) -> str | None:
    """Respawn a failed worker with its original args."""
    worker_type = meta.get("type")
    args_dict = meta.get("args", {})
    if not worker_type or not args_dict:
        return None

    scripts_workers = WORKSPACE / "scripts" / "workers"
    worker_scripts = {
        "ldr": scripts_workers / "ldr_worker.py",
        "rlm": scripts_workers / "rlm_worker.py",
        "search": scripts_workers / "hybrid_worker.py",
    }
    if worker_type not in worker_scripts:
        return None

    # Create new task dir with _retry suffix
    new_task_id = f"{task_id}_retry"
    new_task_dir = WORKERS_DIR / new_task_id
    new_task_dir.mkdir(parents=True, exist_ok=True)

    # Write meta
    new_meta = {**meta, "task_id": new_task_id, "spawned_at": time.time(), "retry_of": task_id}
    (new_task_dir / "meta.json").write_text(
        json.dumps(new_meta, ensure_ascii=False), encoding="utf-8"
    )
    (new_task_dir / "status.txt").write_text("pending", encoding="utf-8")

    cli_args = [str(PYTHON), str(worker_scripts[worker_type]), f"--task-id={new_task_id}"]
    for k, v in args_dict.items():
        cli_args.append(f"--{k.replace('_', '-')}={v}")

    subprocess.Popen(
        cli_args,
        cwd=str(WORKSPACE),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=CREATE_NO_WINDOW,
        close_fds=True,
    )
    return new_task_id


def run_monitor_cycle() -> dict:
    """Run one monitoring cycle. Returns summary dict."""
    global _last_cleanup

    if not WORKERS_DIR.exists():
        return {"checked": 0}

    summary = {
        "ts": time.time(),
        "psutil_available": _PSUTIL,
        "running": [],
        "stuck": [],
        "auto_killed": [],
        "auto_restarted": [],
        "resource_stats": {},
        "done": 0,
        "error": 0,
    }

    for task_dir in WORKERS_DIR.iterdir():
        if not task_dir.is_dir() or task_dir.name.startswith("_"):
            continue

        status = read_status(task_dir)
        meta = read_meta(task_dir)
        task_id = task_dir.name

        if status == "done":
            summary["done"] += 1
        elif status == "error":
            summary["error"] += 1
        elif status == "running":
            summary["running"].append(task_id)
            spawned_at = meta.get("spawned_at", time.time())
            age_sec = time.time() - spawned_at
            progress_age = read_progress_age(task_dir)

            # ── psutil resource monitoring ──
            pid = get_pid(task_dir)
            proc_stats = get_process_stats(pid) if pid else None
            if proc_stats:
                summary["resource_stats"][task_id] = proc_stats

                # Memory limit enforcement
                if proc_stats["rss_mb"] > MAX_WORKER_MEM_MB:
                    print(f"[Monitor] KILL {task_id}: RSS {proc_stats['rss_mb']:.0f}MB > {MAX_WORKER_MEM_MB}MB")
                    kill_process_tree(pid)
                    status_file = task_dir / "status.txt"
                    status_file.write_text("error", encoding="utf-8")
                    (task_dir / "result.json").write_text(
                        json.dumps({"type": meta.get("type"), "error": f"OOM: RSS {proc_stats['rss_mb']:.0f}MB > {MAX_WORKER_MEM_MB}MB", "elapsed_sec": round(age_sec)}),
                        encoding="utf-8",
                    )
                    summary["auto_killed"].append(task_id)
                    continue

                # High CPU hang detection
                cpu = proc_stats["cpu_pct"]
                if cpu > 95.0:
                    _high_cpu_counters[task_id] = _high_cpu_counters.get(task_id, 0) + 1
                    if _high_cpu_counters[task_id] >= HIGH_CPU_CYCLES_THRESHOLD:
                        print(f"[Monitor] KILL {task_id}: high CPU {cpu}% for {HIGH_CPU_CYCLES_THRESHOLD}+ cycles")
                        kill_process_tree(pid)
                        status_file = task_dir / "status.txt"
                        status_file.write_text("error", encoding="utf-8")
                        summary["auto_killed"].append(task_id)
                        _high_cpu_counters.pop(task_id, None)
                        continue
                else:
                    _high_cpu_counters.pop(task_id, None)  # reset counter

            # Detect stuck: old worker + progress file not updated
            if age_sec > 300 and progress_age > STALE_SEC:
                stuck_entry = {
                    "task_id": task_id,
                    "age_sec": round(age_sec),
                    "progress_age_sec": round(progress_age),
                }
                if proc_stats:
                    stuck_entry["cpu_pct"] = proc_stats["cpu_pct"]
                    stuck_entry["rss_mb"] = proc_stats["rss_mb"]
                summary["stuck"].append(stuck_entry)

    # Periodic cleanup
    if time.time() - _last_cleanup > CLEANUP_INTERVAL:
        import shutil
        cutoff = time.time() - 7 * 86400
        deleted = 0
        for task_dir in WORKERS_DIR.iterdir():
            if not task_dir.is_dir() or task_dir.name.startswith("_"):
                continue
            mf = task_dir / "meta.json"
            try:
                meta_data = json.loads(mf.read_text()) if mf.exists() else {}
                if meta_data.get("spawned_at", 0) < cutoff:
                    shutil.rmtree(task_dir, ignore_errors=True)
                    deleted += 1
            except Exception:
                pass
        summary["cleanup_deleted"] = deleted
        _last_cleanup = time.time()
        print(f"[Monitor] Cleanup: deleted {deleted} old task dirs")

    # Write monitor file
    WORKERS_DIR.mkdir(parents=True, exist_ok=True)
    MONITOR_FILE.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    return summary


def main():
    p = argparse.ArgumentParser(description="Worker Health Monitor v2 (psutil)")
    p.add_argument("--interval", type=int, default=30, help="Poll interval in seconds")
    p.add_argument("--once", action="store_true", help="Run one cycle and exit")
    args = p.parse_args()

    psutil_note = "(psutil available)" if _PSUTIL else "(psutil NOT available — limited monitoring)"
    print(f"[Monitor] Starting worker health monitor v2 {psutil_note} (interval={args.interval}s)")

    while True:
        try:
            summary = run_monitor_cycle()
            running_count = len(summary.get("running", []))
            stuck_count = len(summary.get("stuck", []))
            killed_count = len(summary.get("auto_killed", []))
            print(
                f"[Monitor] running={running_count} done={summary.get('done', 0)} "
                f"error={summary.get('error', 0)} stuck={stuck_count} killed={killed_count}"
            )
            if stuck_count:
                print(f"[Monitor] STUCK tasks: {summary['stuck']}")
            if summary.get("resource_stats"):
                for tid, stats in summary["resource_stats"].items():
                    print(f"[Monitor]   {tid}: CPU={stats['cpu_pct']}% RAM={stats['rss_mb']:.0f}MB")
        except Exception as e:
            print(f"[Monitor] Error in cycle: {e}")

        if args.once:
            break

        time.sleep(args.interval)


if __name__ == "__main__":
    main()
