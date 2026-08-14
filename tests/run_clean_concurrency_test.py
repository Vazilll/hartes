import os, glob, sys, time, subprocess
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
sys.path.insert(0, r"C:\vazus")
from vazus_core.db import close_all_thread_connections

def kill_leftover_test_processes():
    """Safely terminates ONLY orphaned test runner processes without mutual assassination."""
    try:
        import psutil
        current_pid = os.getpid()
        family_pids = {current_pid}
        try:
            p = psutil.Process(current_pid)
            current_create_time = p.create_time()
            for child in p.children(recursive=True):
                family_pids.add(child.pid)
            parent = p.parent()
            if parent is not None:
                family_pids.add(parent.pid)
        except Exception:
            current_create_time = time.time()

        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
            try:
                pid = proc.info['pid']
                if pid in family_pids:
                    continue
                pname = (proc.info['name'] or '').lower()
                if not pname.startswith('python'):
                    continue
                create_time = proc.info.get('create_time', 0)
                if create_time >= current_create_time - 1.0:
                    continue
                cmdline = " ".join(proc.info['cmdline'] or [])
                if ("stress_concurrency.py" in cmdline or "run_clean_concurrency" in cmdline) and "pytest" not in cmdline:
                    try:
                        ppid = proc.ppid()
                        if ppid in family_pids:
                            continue
                    except Exception:
                        pass
                    proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
    except Exception:
        pass

if __name__ == '__main__':
    import traceback
    ret_code = 1
    try:
        close_all_thread_connections()
        kill_leftover_test_processes()
        time.sleep(0.3)

        db_files = glob.glob(r"C:\vazus\.agents\m3_challenger_2\test_concurrency_wal.db*")
        for f in db_files:
            if not os.path.exists(f):
                continue
            removed = False
            for attempt in range(15):
                try:
                    if os.path.exists(f):
                        os.remove(f)
                    print(f"Removed {f}", flush=True)
                    removed = True
                    break
                except Exception as e:
                    import gc
                    gc.collect()
                    close_all_thread_connections()
                    time.sleep(0.3)
            if not removed and os.path.exists(f):
                print(f"CRITICAL ERROR: Unable to remove locked database file {f} after 15 retries. Aborting test to prevent dirty DB execution.", flush=True)
                sys.exit(1)

        cmd = [sys.executable, "-u", r"C:\vazus\.agents\m3_challenger_2\stress_concurrency.py"]
        res = subprocess.run(cmd)
        ret_code = res.returncode
    except Exception as exc:
        print(f"LAUNCHER EXCEPTION: {exc}", flush=True)
        traceback.print_exc()
    finally:
        close_all_thread_connections()
        kill_leftover_test_processes()
    sys.exit(ret_code)
