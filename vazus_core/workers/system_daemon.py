"""
vazus_core/system_daemon.py — Production Background Daemon Sidecar & Control Plane.

Manages process lifecycle (start/stop/status/restart), PID file tracking (vazus.pid),
HTTP health check server on port 8765 (/healthz, /status, /version), and background
transcript watcher sidecar integration.
"""

import argparse
import json
import logging
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

if os.name == "nt":
    try:
        import msvcrt
        devnull_fd = None
        for target_fd in (1, 2):
            try:
                h = msvcrt.get_osfhandle(target_fd)
                if h in (-1, -2, 0, 0xFFFFFFFF, 0xFFFFFFFFFFFFFFFF):
                    if devnull_fd is None:
                        devnull_fd = os.open(os.devnull, os.O_RDWR)
                    os.dup2(devnull_fd, target_fd)
            except (OSError, ValueError):
                if devnull_fd is None:
                    devnull_fd = os.open(os.devnull, os.O_RDWR)
                try:
                    os.dup2(devnull_fd, target_fd)
                except OSError as exc:
                    logging.getLogger("system_daemon").debug("os.dup2 fallback failed: %s", exc)
        if devnull_fd is not None:
            try:
                os.close(devnull_fd)
            except OSError as exc:
                logging.getLogger("system_daemon").debug("devnull_fd close failed: %s", exc)
    except Exception as exc:
        logging.getLogger("system_daemon").debug("msvcrt handle init failed: %s", exc)

if sys.stdout is not None:
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stdout, "flush"):
            sys.stdout.flush()
    except (AttributeError, OSError):
        try:
            sys.stdout = open(os.devnull, "w", encoding="utf-8")
        except Exception as exc:
            logging.getLogger("system_daemon").debug("sys.stdout devnull fallback failed: %s", exc)

if sys.stderr is not None:
    try:
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "flush"):
            sys.stderr.flush()
    except (AttributeError, OSError):
        try:
            sys.stderr = open(os.devnull, "w", encoding="utf-8")
        except Exception as exc:
            logging.getLogger("system_daemon").debug("sys.stderr devnull fallback failed: %s", exc)


def safe_print(*args, **kwargs):
    if sys.stdout is not None:
        try:
            print(*args, **kwargs)
            if hasattr(sys.stdout, "flush"):
                sys.stdout.flush()
        except (AttributeError, OSError) as exc:
            logging.getLogger("system_daemon").debug("safe_print note: %s", exc)


# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from vazus_core.memory.db import get_db_connection
from vazus_core.engine.config import settings

# Configure logging safely without sys.stderr StreamHandler dependency
logging.raiseExceptions = False
log_handlers = []
try:
    log_handlers.append(logging.FileHandler(PROJECT_ROOT / "system_daemon.log", encoding="utf-8"))
except Exception:
    log_handlers.append(logging.NullHandler())

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [SystemDaemon] %(message)s",
    handlers=log_handlers
)
logger = logging.getLogger("system_daemon")

DEFAULT_PID_PATH = settings.DAEMON_PID_FILE
DEFAULT_PORT = int(os.getenv("VAZUS_DAEMON_PORT", 8765))


class HealthCheckHandler(BaseHTTPRequestHandler):
    """Zero-dependency HTTP Handler for /healthz, /status, and /version endpoints."""
    daemon_instance: Optional["VazusSystemDaemon"] = None

    def log_message(self, format: str, *args: Any) -> None:
        """Suppresses noisy standard HTTP access logging to stdout (routes to debug logger)."""
        logger.debug(format, *args)

    def do_GET(self):
        if not self.daemon_instance:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Daemon instance not bound"}).encode("utf-8"))
            return

        if self.path == "/healthz":
            status_code, payload = self.daemon_instance.get_health_status()
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode("utf-8"))

        elif self.path == "/status":
            payload = self.daemon_instance.get_detailed_status()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode("utf-8"))

        elif self.path == "/version":
            payload = {"name": "vazus SuperGraph OS", "version": "4.0.0", "milestone": "M1"}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode("utf-8"))

        else:
            self.send_response(404)
            self.end_headers()


class VazusSystemDaemon:
    """
    Main Process Manager & Control Plane for vazus System Daemon.
    """
    def __init__(self, pid_path: Optional[Path] = None, port: int = DEFAULT_PORT):
        self.pid_path = Path(pid_path) if pid_path else DEFAULT_PID_PATH
        self.port = port
        self.start_time = time.time()
        self._running = False
        self._http_server: Optional[ThreadingHTTPServer] = None
        self._http_thread: Optional[threading.Thread] = None
        self._worker_thread: Optional[threading.Thread] = None
        self._sidecar_instance: Optional[Any] = None

    # --- PID Management ---
    def write_pid(self) -> None:
        self.pid_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_pid_path = self.pid_path.with_name(self.pid_path.name + ".tmp")
        with open(tmp_pid_path, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
        os.replace(tmp_pid_path, self.pid_path)
        logger.info(f"Wrote PID {os.getpid()} to {self.pid_path}")

    def read_pid(self) -> Optional[int]:
        if not self.pid_path.exists():
            return None
        try:
            with open(self.pid_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                return int(content) if content else None
        except Exception as exc:
            logger.debug("read_pid error: %s", exc)
            return None

    def remove_pid(self, force: bool = False) -> None:
        if self.pid_path.exists():
            try:
                pid = self.read_pid()
                if force or (pid is not None and pid == os.getpid()):
                    self.pid_path.unlink()
                    logger.info(f"Removed PID file {self.pid_path}")
                elif pid is not None:
                    running, _ = self.is_running()
                    if not running:
                        self.pid_path.unlink()
                        logger.info(f"Removed stale PID file {self.pid_path} (PID {pid} is not running)")
                    else:
                        logger.info(f"Skipping PID file removal: PID file contains active PID {pid}, current process PID is {os.getpid()}")
                else:
                    logger.info(f"Skipping PID file removal: PID file contains None, current process PID is {os.getpid()}")
            except Exception as e:
                logger.error(f"Failed to remove PID file: {e}")

    def is_running(self) -> Tuple[bool, Optional[int]]:
        pid = self.read_pid()
        if pid is None or pid <= 0:
            return False, None

        if pid == os.getpid():
            return True, pid

        # Check process liveness and command line
        try:
            import psutil
            proc = psutil.Process(pid)
            if proc.is_running():
                try:
                    cmdline_str = " ".join(proc.cmdline()).lower()
                    if "system_daemon" in cmdline_str or "vazus_core" in cmdline_str:
                        return True, pid
                except (psutil.AccessDenied, psutil.ZombieProcess) as exc:
                    logger.debug("psutil access note: %s", exc)
                    return True, pid
        except ImportError:
            if os.name == "nt":
                import ctypes
                kernel32 = ctypes.windll.kernel32
                PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
                STILL_ACTIVE = 259
                handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
                if handle:
                    exit_code = ctypes.c_ulong()
                    success = kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
                    kernel32.CloseHandle(handle)
                    if success and exit_code.value == STILL_ACTIVE:
                        return True, pid
            else:
                try:
                    os.kill(pid, 0)
                    return True, pid
                except OSError as exc:
                    logger.debug("os.kill liveness note: %s", exc)
        except Exception as exc:
            logger.debug("is_running check note: %s", exc)

        return False, None

    # --- Health & Status Hooks ---
    def check_db_health(self) -> bool:
        try:
            conn = get_db_connection(read_only=True)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM organic_insights")
            cursor.fetchone()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"DB Health check failed: {e}")
            return False

    def get_health_status(self) -> Tuple[int, Dict[str, Any]]:
        db_healthy = self.check_db_health()
        status_code = 200 if db_healthy else 503
        payload = {
            "status": "ok" if db_healthy else "degraded",
            "service": "vazus_system_daemon",
            "version": "4.0.0",
            "pid": os.getpid(),
            "uptime_seconds": round(time.time() - self.start_time, 2),
            "db_status": "connected" if db_healthy else "error",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        return status_code, payload

    def get_detailed_status(self) -> Dict[str, Any]:
        _, health_payload = self.get_health_status()
        health_payload["pid_file"] = str(self.pid_path)
        health_payload["http_port"] = self.port
        health_payload["mode"] = "foreground" if self._running else "background"
        if self._sidecar_instance:
            health_payload["sidecar"] = self._sidecar_instance.status()
        return health_payload

    def _is_port_bound(self, port: int) -> bool:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.2)
                return s.connect_ex(("127.0.0.1", port)) == 0
        except Exception as exc:
            logger.debug("Port check note: %s", exc)
            return False

    # --- HTTP Server ---
    def start_http_server(self) -> None:
        daemon_ref = self
        class DynamicHealthCheckHandler(HealthCheckHandler):
            daemon_instance = daemon_ref

        ThreadingHTTPServer.allow_reuse_address = True
        server = None
        last_exception = None
        for attempt in range(15):
            try:
                server = ThreadingHTTPServer(("127.0.0.1", self.port), DynamicHealthCheckHandler)
                break
            except OSError as e:
                last_exception = e
                logger.warning(f"Failed to bind HTTP server to 127.0.0.1:{self.port} (attempt {attempt + 1}/15): {e}")
                time.sleep(0.5)

        if server is None:
            if last_exception:
                raise last_exception
            raise OSError(f"Could not bind HTTP server to 127.0.0.1:{self.port} after 15 retries")

        self._http_server = server
        self._http_thread = threading.Thread(target=self._http_server.serve_forever, daemon=True)
        self._http_thread.start()
        logger.info(f"HTTP Health Check Server active on http://127.0.0.1:{self.port}")

    def stop_http_server(self) -> None:
        if self._http_server:
            self._http_server.shutdown()
            self._http_server.server_close()
            logger.info("HTTP Health Check Server stopped.")

    # --- Worker Loop ---
    def _background_worker_loop(self) -> None:
        logger.info("Background worker loop initialized.")
        try:
            from vazus_core.workers.daemon_sidecar import DaemonSidecar
            sidecar_pid = settings.GEMINI_CLI_DIR / "sidecar.pid"
            self._sidecar_instance = DaemonSidecar(pid_file=sidecar_pid)

            def _on_transcript_event(evt):
                logger.info(f"Sidecar TranscriptEvent: conv={evt.conversation_id}, step={evt.step_idx}, status={evt.status}")

            self._sidecar_instance.register_listener(_on_transcript_event)
            self._sidecar_instance.start(daemonize=False)

            while self._running:
                time.sleep(1)
        except ImportError:
            logger.warning("DaemonSidecar module not found, fallback worker loop running.")
            while self._running:
                time.sleep(5)
        except Exception as e:
            logger.error(f"Worker loop error: {e}")

    # --- Lifecycle Actions ---
    def _check_and_clean_existing_daemon(self) -> None:
        running, existing_pid = self.is_running()
        if running:
            port_pids = self._find_daemon_pids_on_port(self.port)
            if existing_pid not in port_pids or not self._is_port_bound(self.port):
                logger.warning(f"Recycling stale PID file {existing_pid}; port {self.port} held by {port_pids}")
                if existing_pid:
                    self._kill_process(existing_pid)
                for opid in port_pids:
                    self._kill_process(opid)
                self.remove_pid(force=True)
            else:
                safe_print(f"⚠️ System Daemon already running under PID {existing_pid}")
                sys.exit(0)

        orphaned = self._find_daemon_pids_on_port(self.port)
        for opid in orphaned:
            if opid != os.getpid():
                safe_print(f"🛑 Cleaning orphaned daemon process on port {self.port} [PID: {opid}]...")
                self._kill_process(opid)

    def _launch_daemon_subprocess(self) -> subprocess.Popen:
        cmd = [sys.executable, "-m", "vazus_core.system_daemon", "start", "--foreground"]
        if os.name == "nt":
            CREATE_BREAKAWAY_FROM_JOB = 0x01000000
            CREATE_NO_WINDOW = 0x08000000
            DETACHED_PROCESS = 0x00000008
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
            try:
                return subprocess.Popen(
                    cmd,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=flags | CREATE_BREAKAWAY_FROM_JOB,
                    close_fds=True
                )
            except (OSError, PermissionError) as exc:
                logger.debug("Breakaway spawn fallback: %s", exc)
                return subprocess.Popen(
                    cmd,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=flags,
                    close_fds=True
                )
        return subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True
        )

    def _wait_for_pid_file(self, proc: subprocess.Popen) -> bool:
        for _ in range(150):
            exit_code = proc.poll()
            if exit_code is not None:
                self.remove_pid(force=True)
                safe_print(f"❌ Failed to start background daemon: Child process exited unexpectedly with code {exit_code}")
                sys.exit(1)

            if self.pid_path.exists():
                try:
                    content = self.pid_path.read_text(encoding="utf-8").strip()
                    if content and content.isdigit():
                        return True
                except Exception as exc:
                    logger.debug("PID file read wait note: %s", exc)
            time.sleep(0.1)
        return False

    def _spawn_background_daemon_process(self) -> None:
        if self.pid_path.exists():
            running, _ = self.is_running()
            if not running:
                self.remove_pid(force=True)

        proc = self._launch_daemon_subprocess()
        success = self._wait_for_pid_file(proc)

        if not success:
            exit_code = proc.poll()
            if exit_code is None:
                try:
                    proc.kill()
                except Exception as exc:
                    logger.debug("Background proc kill note: %s", exc)
            self.remove_pid(force=True)
            if exit_code is not None:
                safe_print(f"❌ Failed to start background daemon: Child process exited with code {exit_code}")
            else:
                safe_print("❌ Failed to start background daemon: Timed out waiting for PID file creation")
            sys.exit(1)

        safe_print(f"🚀 Started vazus System Daemon background process [PID: {proc.pid}]")
        sys.exit(0)

    def _run_foreground_daemon(self) -> None:
        self.write_pid()
        self._running = True

        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            self.stop()
            sys.exit(0)

        try:
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
        except (ValueError, AttributeError) as exc:
            logger.debug("Signal handler note in foreground runner: %s", exc)

        try:
            self.start_http_server()
            self._worker_thread = threading.Thread(target=self._background_worker_loop, daemon=True)
            self._worker_thread.start()

            safe_print(f"✅ vazus System Daemon running in foreground [PID: {os.getpid()}] on http://127.0.0.1:{self.port}")
            while self._running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()
        except Exception as e:
            logger.exception(f"Unhandled daemon main loop exception: {e}")
            self.stop()
            self.remove_pid()
            sys.exit(1)
        finally:
            self.remove_pid()
            logger.info(f"Daemon process [PID: {os.getpid()}] main loop exited.")

    def start(self, foreground: bool = False) -> None:
        self._check_and_clean_existing_daemon()
        if not foreground:
            self._spawn_background_daemon_process()
        else:
            self._run_foreground_daemon()

    def _find_daemon_pids_on_port(self, port: int) -> list[int]:
        pids = set()
        try:
            import psutil
            connections = psutil.net_connections(kind="inet")
            for conn in connections:
                if conn.laddr and conn.laddr.port == port and conn.pid and conn.pid > 0:
                    pids.add(conn.pid)
        except Exception as e:
            logger.debug(f"psutil top-level net_connections error: {e}")

        if os.name == "nt":
            try:
                res = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, errors="replace")
                if res.returncode == 0:
                    import re
                    port_pattern = rf":{port}\b.*?\s+(\d+)\s*$"
                    for line in res.stdout.splitlines():
                        match = re.search(port_pattern, line)
                        if match:
                            found_pid = int(match.group(1))
                            if found_pid > 0 and found_pid != os.getpid():
                                pids.add(found_pid)
            except Exception as e:
                logger.debug(f"netstat execution error: {e}")

        return list(pids)

    def _kill_process(self, pid: int) -> None:
        if pid <= 0 or pid == os.getpid():
            return
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
            import ctypes
            kernel32 = ctypes.windll.kernel32
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            STILL_ACTIVE = 259
            for _ in range(30):
                handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
                if not handle:
                    break
                exit_code = ctypes.c_ulong()
                success = kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
                kernel32.CloseHandle(handle)
                if not (success and exit_code.value == STILL_ACTIVE):
                    break
                time.sleep(0.1)
        else:
            try:
                os.kill(pid, signal.SIGTERM)
                for _ in range(30):
                    try:
                        os.kill(pid, 0)
                        time.sleep(0.1)
                    except OSError:
                        break
            except OSError as exc:
                logger.debug("os.kill term note: %s", exc)

    def stop(self) -> None:
        running, pid = self.is_running()
        port_pids = self._find_daemon_pids_on_port(self.port)

        if not running and not self._running and not port_pids and not self._is_port_bound(self.port):
            safe_print("⚠️ System Daemon is not running.")
            self.remove_pid(force=True)
            return

        self._running = False
        if self._sidecar_instance:
            try:
                self._sidecar_instance.stop()
            except Exception as e:
                logger.error(f"Error stopping sidecar: {e}")

        self.stop_http_server()

        pids_to_kill = set()
        if pid and pid != os.getpid():
            pids_to_kill.add(pid)
        for opid in port_pids:
            if opid != os.getpid():
                pids_to_kill.add(opid)

        for target_pid in pids_to_kill:
            safe_print(f"🛑 Terminating Daemon Process [PID: {target_pid}]...")
            self._kill_process(target_pid)

        for _ in range(30):
            if not self._is_port_bound(self.port):
                break
            time.sleep(0.1)

        self.remove_pid(force=True)
        safe_print("✅ System Daemon stopped successfully.")

    def run_single_pass(self) -> Dict[str, Any]:
        """Executes a single test pass without persistent loop (for unit tests)."""
        logger.info("Executing single pass daemon check...")
        db_healthy = self.check_db_health()
        res = {
            "single_pass": True,
            "db_healthy": db_healthy,
            "timestamp": time.time()
        }
        try:
            from vazus_core.workers.daemon_sidecar import DaemonSidecar
            sidecar = DaemonSidecar()
            events = sidecar.run_single_pass()
            res["sidecar_events"] = len(events)
            res["sidecar_status"] = sidecar.status()
        except Exception as e:
            logger.debug("Sidecar single pass note: %s", e)
            res["sidecar_error"] = str(e)
        return res


def main():
    parser = argparse.ArgumentParser(description="vazus SuperGraph OS Unified System Daemon Control Plane")
    parser.add_argument("command", nargs="?", choices=["start", "stop", "status", "restart"], help="Daemon command")
    parser.add_argument("--foreground", action="store_true", help="Run daemon in foreground mode")
    parser.add_argument("--single-pass", action="store_true", help="Execute single-pass check and exit")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="HTTP health check port (default: 8765)")
    args = parser.parse_args()

    daemon = VazusSystemDaemon(port=args.port)

    if args.single_pass:
        res = daemon.run_single_pass()
        safe_print(json.dumps(res, indent=2))
        return

    cmd = args.command or ("start" if args.foreground else "status")

    if cmd == "start":
        daemon.start(foreground=args.foreground)
    elif cmd == "stop":
        daemon.stop()
    elif cmd == "status":
        running, pid = daemon.is_running()
        if running:
            safe_print(f"✅ System Daemon is RUNNING [PID: {pid}]")
            try:
                import urllib.request
                with urllib.request.urlopen(f"http://127.0.0.1:{args.port}/status", timeout=2) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    safe_print(json.dumps(data, indent=2))
            except Exception as e:
                safe_print(f"⚠️ Health check ping failed: {e}")
        else:
            daemon.remove_pid(force=True)
            safe_print("🛑 System Daemon is STOPPED")
    elif cmd == "restart":
        daemon.stop()
        time.sleep(1)
        daemon.start(foreground=args.foreground)


if __name__ == "__main__":
    main()
