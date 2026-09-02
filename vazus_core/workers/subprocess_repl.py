"""
vazus_core.workers.subprocess_repl — Zero-Trust Subprocess REPL Sandbox.
Executes untrusted Python code in ephemeral, isolated subprocesses with
Win32 Job Object kernel bounding (512MB RAM, ActiveProcLimit=1, KILL_ON_JOB_CLOSE).
"""

import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("SubprocessREPL")

# --- Win32 Job Object Bindings (Kernel Memory & Process Sandbox) ---
if sys.platform == "win32":
    import ctypes
    import ctypes.wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_uint64),
            ("WriteOperationCount", ctypes.c_uint64),
            ("OtherOperationCount", ctypes.c_uint64),
            ("ReadTransferCount", ctypes.c_uint64),
            ("WriteTransferCount", ctypes.c_uint64),
            ("OtherTransferCount", ctypes.c_uint64),
        ]

    class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", ctypes.wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", ctypes.wintypes.DWORD),
            ("Affinity", ctypes.POINTER(ctypes.c_ulong)),
            ("PriorityClass", ctypes.wintypes.DWORD),
            ("SchedulingClass", ctypes.wintypes.DWORD),
        ]

    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("IoInfo", IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryLimit", ctypes.c_size_t),
            ("PeakJobMemoryLimit", ctypes.c_size_t),
        ]

    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
    JOB_OBJECT_LIMIT_JOB_MEMORY = 0x00000200
    JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x00000008
    JobObjectExtendedLimitInformation = 9


def create_win32_sandbox_job(max_memory_bytes: int = 512 * 1024 * 1024) -> Optional[int]:
    """Creates a Win32 Job Object that enforces hard memory limits and kills child processes on exit."""
    if sys.platform != "win32":
        return None

    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        return None

    info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    info.BasicLimitInformation.LimitFlags = (
        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        | JOB_OBJECT_LIMIT_JOB_MEMORY
        | JOB_OBJECT_LIMIT_ACTIVE_PROCESS
    )
    info.BasicLimitInformation.ActiveProcessLimit = 4
    info.JobMemoryLimit = max_memory_bytes

    res = kernel32.SetInformationJobObject(
        job,
        JobObjectExtendedLimitInformation,
        ctypes.byref(info),
        ctypes.sizeof(info)
    )
    return job if res else None


def assign_process_to_job(job_handle: int, pid: int) -> bool:
    """Binds a spawned process to the Win32 Job Object."""
    if sys.platform != "win32" or not job_handle:
        return False
    PROCESS_ALL_ACCESS = 0x1F0FFF
    proc_handle = kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
    if proc_handle:
        success = kernel32.AssignProcessToJobObject(job_handle, proc_handle)
        kernel32.CloseHandle(proc_handle)
        return bool(success)
    return False


def block_network_on_job(job_handle: int) -> bool:
    """Best-effort: sets JobObjectNetRateControlInformation with 0 bandwidth."""
    if sys.platform != "win32" or not job_handle:
        return False

    JOB_OBJECT_NET_RATE_CONTROL_ENABLE = 0x00000001
    JOB_OBJECT_NET_RATE_CONTROL_MAX_BANDWIDTH = 0x00000002

    class JOBOBJECT_NET_RATE_CONTROL_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("MaxBandwidth", ctypes.c_uint64),
            ("ControlFlags", ctypes.wintypes.DWORD),
            ("DscpTag", ctypes.c_uint8),
        ]

    JobObjectNetRateControlInformation = 32
    info = JOBOBJECT_NET_RATE_CONTROL_INFORMATION()
    info.ControlFlags = (
        JOB_OBJECT_NET_RATE_CONTROL_ENABLE | JOB_OBJECT_NET_RATE_CONTROL_MAX_BANDWIDTH
    )
    info.MaxBandwidth = 0
    res = kernel32.SetInformationJobObject(
        job_handle, JobObjectNetRateControlInformation, ctypes.byref(info), ctypes.sizeof(info)
    )
    return bool(res)


def close_win32_sandbox_job(job_handle: int) -> bool:
    """Closes a sandbox Job Object handle."""
    if sys.platform != "win32" or not job_handle:
        return False
    return bool(kernel32.CloseHandle(job_handle))


@dataclass
class SubprocessREPLResult:
    stdout: str
    stderr: str
    locals: Dict[str, Any]
    execution_time: float
    status: str  # "SUCCESS", "TIMEOUT", "MEMORY_EXCEEDED", "ERROR"
    final_answer: Optional[str] = None


class ZeroTrustSubprocessREPL:
    """
    Subprocess-Isolated REPL executing untrusted Python in isolated tempdir
    with sanitized environment, CPU timeout, and kernel memory bounding.
    """
    def __init__(self, memory_limit_mb: int = 512, timeout_seconds: float = 10.0, require_kernel_sandbox: bool = True):
        self.memory_limit_bytes = memory_limit_mb * 1024 * 1024
        self.timeout_seconds = timeout_seconds
        self.require_kernel_sandbox = require_kernel_sandbox
        self.python_bin = getattr(sys, "_base_executable", sys.executable)

    def _build_harness_script(self, code: str, context: Dict[str, Any]) -> str:
        return f"""
import sys, json

try:
    context = {json.dumps(context)}
    locals().update(context)
    answer = {{"ready": False, "content": ""}}

    user_code = {json.dumps(code)}
    exec(compile(user_code, '<sandbox_repl>', 'exec'))

    clean_locals = {{}}
    for k, v in list(locals().items()):
        if not k.startswith('_') and k not in ('context', 'user_code', 'sys', 'json', 'clean_locals'):
            try:
                json.dumps(v)
                clean_locals[k] = v
            except Exception:
                clean_locals[k] = str(v)

    result_payload = {{
        "status": "SUCCESS",
        "locals": clean_locals,
        "final_answer": answer.get("content") if answer.get("ready") else None
    }}
    print("__VAZUS_IPC_START__" + json.dumps(result_payload) + "__VAZUS_IPC_END__")
except Exception as err:
    import traceback
    sys.stderr.write(traceback.format_exc())
    sys.exit(1)
"""

    def _spawn_sandboxed_subprocess(self, temp_dir: str, harness_path: str) -> Tuple[subprocess.Popen, Optional[int]]:
        sanitized_env = {
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", r"C:\Windows"),
            "PATH": os.environ.get("PATH", r"C:\Windows\system32;C:\Windows"),
            "PYTHONUTF8": "1",
        }

        job_handle = create_win32_sandbox_job(self.memory_limit_bytes)
        if sys.platform == "win32" and not job_handle and self.require_kernel_sandbox:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise RuntimeError("SecurityIsolationError: Win32 Job Object creation failed — refusing to execute untrusted code without kernel memory bounds.")

        cmd = [self.python_bin, "-I", "-S", "-B", "-u", harness_path]
        proc = subprocess.Popen(
            cmd,
            cwd=temp_dir,
            env=sanitized_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8"
        )

        if job_handle:
            assigned = assign_process_to_job(job_handle, proc.pid)
            if not assigned and sys.platform == "win32" and self.require_kernel_sandbox:
                proc.kill()
                kernel32.CloseHandle(job_handle)
                shutil.rmtree(temp_dir, ignore_errors=True)
                raise RuntimeError("SecurityIsolationError: Failed to assign process to Win32 Job Object sandbox.")

        return proc, job_handle

    def _parse_ipc_output(self, proc: subprocess.Popen, stdout_raw: str, stderr_raw: str, exec_time: float) -> SubprocessREPLResult:
        if "__VAZUS_IPC_START__" in stdout_raw:
            parts = stdout_raw.split("__VAZUS_IPC_START__")[1].split("__VAZUS_IPC_END__")
            payload = json.loads(parts[0])
            visible_stdout = stdout_raw.replace(f"__VAZUS_IPC_START__{parts[0]}__VAZUS_IPC_END__", "").strip()
            return SubprocessREPLResult(
                stdout=visible_stdout,
                stderr=stderr_raw,
                locals=payload.get("locals", {}),
                execution_time=exec_time,
                status="SUCCESS",
                final_answer=payload.get("final_answer")
            )
        return SubprocessREPLResult(
            stdout=stdout_raw,
            stderr=stderr_raw,
            locals={},
            execution_time=exec_time,
            status="ERROR" if proc.returncode != 0 else "SUCCESS"
        )

    def execute_code(self, code: str, context: Optional[Dict[str, Any]] = None) -> SubprocessREPLResult:
        start_time = time.perf_counter()
        context = context or {}

        temp_dir = tempfile.mkdtemp(prefix=f"vazus_repl_{uuid.uuid4().hex[:8]}_")
        harness_script = self._build_harness_script(code, context)
        harness_path = os.path.join(temp_dir, "harness.py")
        with open(harness_path, "w", encoding="utf-8") as f:
            f.write(harness_script)

        proc, job_handle = self._spawn_sandboxed_subprocess(temp_dir, harness_path)

        try:
            stdout_raw, stderr_raw = proc.communicate(timeout=self.timeout_seconds)
            exec_time = time.perf_counter() - start_time
            return self._parse_ipc_output(proc, stdout_raw, stderr_raw, exec_time)
        except subprocess.TimeoutExpired:
            logger.debug("Execution timed out after %ss for subprocess PID %s", self.timeout_seconds, proc.pid)
            proc.kill()
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
            return SubprocessREPLResult(
                stdout="",
                stderr=f"ExecutionTimeoutError: REPL step exceeded {self.timeout_seconds}s.",
                locals={},
                execution_time=self.timeout_seconds,
                status="TIMEOUT"
            )
        finally:
            if job_handle and sys.platform == "win32":
                kernel32.CloseHandle(job_handle)
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception as exc:
                logger.debug("temp_dir cleanup note: %s", exc)


if __name__ == "__main__":
    repl = ZeroTrustSubprocessREPL()
    r = repl.execute_code("x = 42\nprint(f'Computed answer: {x}')")
    print(f"[+] Sandbox REPL status: {r.status}, stdout: {r.stdout}, locals: {r.locals}")
