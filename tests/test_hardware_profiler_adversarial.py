"""
Adversarial Stress Test Suite for HardwareCapProfiler (vazus_core/hardware_profiler.py).
Constructed by Challenger 2 for Milestone 1 verification.
"""

import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import concurrent.futures
from unittest.mock import MagicMock, patch
import pytest

VAZUS_DIR = Path("C:/vazus")
if str(VAZUS_DIR) not in sys.path:
    sys.path.insert(0, str(VAZUS_DIR))

from vazus_core.hardware_profiler import HardwareCapProfiler


def _proc_worker_save_profile(args):
    """Top-level helper function for multiprocessing pickling on Windows."""
    db_path, caps = args
    p = HardwareCapProfiler()
    p._capabilities = caps
    return p.save_profile_to_db(db_path)


# ============================================================================
# 1. Edge Case: Invalid Database Paths
# ============================================================================

def test_db_path_empty_string():
    """Test saving to empty string path."""
    profiler = HardwareCapProfiler()
    # Empty string to sqlite3.connect("") creates temporary private DB or fails depending on OS
    res = profiler.save_profile_to_db("")
    assert isinstance(res, bool)


def test_db_path_directory():
    """Test saving to a directory path instead of a file path."""
    profiler = HardwareCapProfiler()
    with tempfile.TemporaryDirectory() as tmpdir:
        res = profiler.save_profile_to_db(tmpdir)
        assert res is False


def test_db_path_non_string():
    """Test saving with non-string database path (e.g. integer, None)."""
    profiler = HardwareCapProfiler()
    res_int = profiler.save_profile_to_db(12345)  # type: ignore
    assert res_int is False


def test_db_path_null_byte():
    """Test saving with null byte in path string."""
    profiler = HardwareCapProfiler()
    res = profiler.save_profile_to_db("test\0invalid.db")
    assert res is False


def test_db_path_reserved_win32_names():
    """Test saving to Windows reserved device names (CON, NUL, AUX, PRN)."""
    if sys.platform != "win32":
        pytest.skip("Windows specific test")
    profiler = HardwareCapProfiler()
    res_nul = profiler.save_profile_to_db("NUL")
    assert isinstance(res_nul, bool)


# ============================================================================
# 2. Edge Case: Read-Only Permissions & DB Locks
# ============================================================================

def test_db_read_only_file():
    """Test saving to a read-only SQLite database file."""
    profiler = HardwareCapProfiler()
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "readonly.db")
        # Create empty file and set read-only attribute
        with open(db_path, "w") as f:
            f.write("")
        os.chmod(db_path, 0o444)

        try:
            res = profiler.save_profile_to_db(db_path)
            assert res is False
        finally:
            os.chmod(db_path, 0o666)


def test_db_exclusive_lock_conflict():
    """Test saving to a database file locked exclusively by another connection."""
    profiler = HardwareCapProfiler()
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "locked.db")
        
        # Initialize DB schema first
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE t (id INT)")
        conn.commit()

        # Acquire EXCLUSIVE lock in background connection with timeout=0.1
        lock_conn = sqlite3.connect(db_path, timeout=0.1)
        lock_conn.execute("BEGIN EXCLUSIVE TRANSACTION")

        try:
            res = profiler.save_profile_to_db(db_path)
            # Should handle SQLite OperationalError (database is locked) gracefully
            assert res is False
        finally:
            lock_conn.rollback()
            lock_conn.close()
            conn.close()


# ============================================================================
# 3. Edge Case: Missing Dependencies & Mocked Exceptions
# ============================================================================

def test_openvino_runtime_error_exception():
    """Test behavior when OpenVINO raises RuntimeError during device probing."""
    profiler = HardwareCapProfiler()
    mock_core = MagicMock()
    type(mock_core).available_devices = patch.object(
        MagicMock, "__get__", side_effect=RuntimeError("OpenVINO driver panic")
    )

    with patch("openvino.Core", return_value=mock_core):
        acc = profiler._probe_accelerators()
        assert acc["openvino_available"] is False
        assert acc["openvino_npu"] is False
        assert acc["openvino_devices"] == []


def test_openvino_get_property_unexpected_type():
    """Test when OpenVINO get_property returns non-iterable or unexpected types."""
    profiler = HardwareCapProfiler()
    mock_core = MagicMock()
    mock_core.available_devices = ["CPU"]
    mock_core.get_property.return_value = 12345  # Not a list of strings!

    with patch("openvino.Core", return_value=mock_core):
        flags = {"AVX2": False, "AVX-512": False, "FMA": False, "BMI2": False, "NEON": False}
        profiler._probe_openvino_cpu_caps(flags)
        assert isinstance(flags["AVX2"], bool)


def test_torch_cuda_driver_error():
    """Test when torch.cuda.is_available() raises RuntimeError or DriverError."""
    profiler = HardwareCapProfiler()
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.side_effect = RuntimeError("CUDA driver initialization failed")

    with patch.dict(sys.modules, {"torch": mock_torch}):
        acc = profiler._probe_accelerators()
        assert acc["cuda_gpu"] is False
        assert acc["cuda_device_count"] == 0
        assert acc["cuda_device_name"] is None


def test_torch_cuda_get_device_name_out_of_bounds():
    """Test when torch.cuda.get_device_name(0) raises IndexError."""
    profiler = HardwareCapProfiler()
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = True
    mock_torch.cuda.device_count.return_value = 1
    mock_torch.cuda.get_device_name.side_effect = IndexError("Invalid GPU index")

    with patch.dict(sys.modules, {"torch": mock_torch}):
        acc = profiler._probe_accelerators()
        assert acc["cuda_gpu"] is True
        assert acc["cuda_device_count"] == 1
        assert acc["cuda_device_name"] is None


def test_torch_cpu_capability_attribute_error():
    """Test when torch.backends.cpu.get_cpu_capability returns invalid string or raises AttributeError."""
    profiler = HardwareCapProfiler()
    mock_torch = MagicMock()
    mock_torch.backends.cpu.get_cpu_capability.side_effect = AttributeError("Backend not found")

    with patch.dict(sys.modules, {"torch": mock_torch}):
        flags = {"AVX2": False, "AVX-512": False, "FMA": False, "BMI2": False, "NEON": False}
        profiler._probe_pytorch_cpu_caps(flags)
        assert flags["AVX2"] is False


def test_win32_virtual_alloc_failure():
    """Test CPUID probe when VirtualAlloc returns NULL (simulating out of memory)."""
    if sys.platform != "win32":
        pytest.skip("Win32 specific test")

    profiler = HardwareCapProfiler()
    flags = {"AVX2": False, "AVX-512": False, "FMA": False, "BMI2": False, "NEON": False}

    with patch("ctypes.windll.kernel32.VirtualAlloc", return_value=0):
        profiler._probe_cpuid(flags)
        assert flags["AVX2"] is False


def test_win32_cache_buffer_size_zero():
    """Test Win32 cache probe when GetLogicalProcessorInformation fails or sets buffer size to 0."""
    if sys.platform != "win32":
        pytest.skip("Win32 specific test")

    profiler = HardwareCapProfiler()
    with patch("ctypes.windll.kernel32.GetLogicalProcessorInformation", return_value=0):
        line_size, caches = profiler._probe_win32_cache()
        assert line_size is None
        assert caches == {}


def test_mac_sysctl_timeout_and_error():
    """Test macOS sysctl probing under subprocess timeout / error."""
    profiler = HardwareCapProfiler()
    flags = {"AVX2": False, "AVX-512": False, "FMA": False, "BMI2": False, "NEON": False}

    import subprocess
    with patch("sys.platform", "darwin"):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="sysctl", timeout=2)):
            profiler._probe_macos_sysctl(flags)
            assert flags["AVX2"] is False


def test_linux_proc_cpuinfo_permission_denied():
    """Test Linux /proc/cpuinfo parsing when permission denied or unreadable."""
    profiler = HardwareCapProfiler()
    flags = {"AVX2": False, "AVX-512": False, "FMA": False, "BMI2": False, "NEON": False}

    with patch("os.path.exists", return_value=True):
        with patch("builtins.open", side_effect=PermissionError("Access denied")):
            profiler._probe_proc_cpuinfo(flags)
            assert flags["AVX2"] is False


# ============================================================================
# 4. Edge Case: Concurrent DB Writes
# ============================================================================

def test_concurrent_threads_save_profile_to_db():
    """Test concurrent thread invocations of save_profile_to_db on same SQLite file."""
    profiler = HardwareCapProfiler()
    profiler.detect_capabilities()

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "concurrent_threads.db")
        num_threads = 15
        results = []

        def worker():
            res = profiler.save_profile_to_db(db_path)
            results.append(res)

        threads = [threading.Thread(target=worker) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == num_threads
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT count(*) FROM hardware_profiles")
            count = cursor.fetchone()[0]
            success_count = sum(1 for r in results if r is True)
            assert count == success_count
        finally:
            conn.close()


def test_concurrent_processes_save_profile_to_db():
    """Test concurrent process execution of save_profile_to_db."""
    profiler = HardwareCapProfiler()
    caps = profiler.detect_capabilities()

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "concurrent_procs.db")
        num_workers = 6

        tasks = [(db_path, caps) for _ in range(num_workers)]
        with concurrent.futures.ProcessPoolExecutor(max_workers=num_workers) as executor:
            results = list(executor.map(_proc_worker_save_profile, tasks))

        assert len(results) == num_workers
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT count(*) FROM hardware_profiles")
            count = cursor.fetchone()[0]
            assert count == sum(1 for r in results if r is True)
        finally:
            conn.close()


# ============================================================================
# 5. Edge Case: Unusual OS Environment Variables & Machine Types
# ============================================================================

def test_unusual_machine_architectures():
    """Test probing on unusual/unknown CPU architectures (e.g. RISC-V, SPARC, S390x)."""
    profiler = HardwareCapProfiler()
    for arch in ["riscv64", "sparc64", "s390x", "mips64", "unknown_arch"]:
        with patch("platform.machine", return_value=arch):
            caps = profiler.detect_capabilities()
            assert isinstance(caps["cpu_isas"], dict)
            assert caps["system_info"]["machine"] == arch


def test_cuda_visible_devices_env_variations():
    """Test behavior under unusual CUDA environment variables."""
    profiler = HardwareCapProfiler()
    with patch.dict(os.environ, {"CUDA_VISIBLE_DEVICES": "-1"}):
        caps = profiler.detect_capabilities()
        assert "accelerators" in caps


# ============================================================================
# 6. Edge Case: Extreme Values & Fallbacks
# ============================================================================

def test_cache_specs_fallback_behavior():
    """Verify fallback values when all platform cache probes return None."""
    profiler = HardwareCapProfiler()
    with patch.object(profiler, "_probe_win32_cache", return_value=(None, {})):
        with patch.object(profiler, "_probe_linux_cache", return_value=(None, {})):
            cache = profiler._probe_cache_specs()
            assert cache["line_size_bytes"] == 64
            assert cache["l1_cache_bytes"] == 65536
            assert cache["l2_cache_bytes"] == 2097152
            assert cache["l3_cache_bytes"] == 12582912


def test_json_serialization_validity():
    """Verify detected capabilities dictionary is strictly JSON serializable."""
    profiler = HardwareCapProfiler()
    caps = profiler.detect_capabilities()
    dumped = json.dumps(caps)
    loaded = json.loads(dumped)
    assert loaded == caps
