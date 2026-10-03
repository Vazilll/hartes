"""
Win32 Job Objects Sandbox Guard for Vazus SuperGraph OS.
Implements process tree containment, hard memory caps, and automatic child termination.
"""

import ctypes
import sys
from ctypes import wintypes

# Windows Constants
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
JOB_OBJECT_LIMIT_JOB_MEMORY = 0x00000200
JOB_OBJECT_LIMIT_DIE_ON_UNHANDLED_EXCEPTION = 0x00000400
JobObjectExtendedLimitInformation = 9


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
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


class Win32JobSandbox:
    """
    Win32 Job Objects wrapper guaranteeing process isolation and resource limits.
    """

    def __init__(self, memory_limit_mb: int = 512, kill_on_close: bool = True):
        self.memory_limit_bytes = memory_limit_mb * 1024 * 1024
        self.kill_on_close = kill_on_close
        self.job_handle = None
        self._is_windows = sys.platform == "win32"

        if self._is_windows:
            self._create_job_object()

    def _create_job_object(self):
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.job_handle = kernel32.CreateJobObjectW(None, None)
        if not self.job_handle:
            error = ctypes.get_last_error()
            raise OSError(f"CreateJobObjectW failed with error code {error}")

        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        flags = 0
        if self.kill_on_close:
            flags |= JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if self.memory_limit_bytes > 0:
            flags |= JOB_OBJECT_LIMIT_PROCESS_MEMORY | JOB_OBJECT_LIMIT_JOB_MEMORY

        info.BasicLimitInformation.LimitFlags = flags
        info.ProcessMemoryLimit = self.memory_limit_bytes
        info.JobMemoryLimit = self.memory_limit_bytes

        success = kernel32.SetInformationJobObject(
            self.job_handle,
            JobObjectExtendedLimitInformation,
            ctypes.byref(info),
            ctypes.sizeof(info),
        )
        if not success:
            error = ctypes.get_last_error()
            kernel32.CloseHandle(self.job_handle)
            self.job_handle = None
            raise OSError(f"SetInformationJobObject failed with error code {error}")

    def assign_process(self, pid_or_handle: int) -> bool:
        """
        Assigns a process (by PID or process handle) to this Job Object.
        """
        if not self._is_windows or not self.job_handle:
            return False

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

        # If it looks like a PID, open the process handle
        handle_to_close = None
        if pid_or_handle > 0 and pid_or_handle < 0x100000:
            PROCESS_SET_QUOTA = 0x0100
            PROCESS_TERMINATE = 0x0001
            h_process = kernel32.OpenProcess(PROCESS_SET_QUOTA | PROCESS_TERMINATE, False, pid_or_handle)
            if not h_process:
                return False
            proc_handle = h_process
            handle_to_close = h_process
        else:
            proc_handle = pid_or_handle

        try:
            success = kernel32.AssignProcessToJobObject(self.job_handle, proc_handle)
            return bool(success)
        finally:
            if handle_to_close:
                kernel32.CloseHandle(handle_to_close)

    def terminate(self, exit_code: int = 1) -> bool:
        """
        Terminates all processes currently assigned to the job object.
        """
        if not self._is_windows or not self.job_handle:
            return False
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        return bool(kernel32.TerminateJobObject(self.job_handle, exit_code))

    def close(self):
        """Closes the job object handle, terminating processes if kill_on_close is set."""
        if self._is_windows and self.job_handle:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.CloseHandle(self.job_handle)
            self.job_handle = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
