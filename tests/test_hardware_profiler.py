"""
Unit tests for Requirement R1: Hardware Microarchitecture Auto-Prober (vazus_core/hardware_profiler.py).
"""

import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
from unittest.mock import MagicMock, patch
import pytest

VAZUS_DIR = Path("C:/vazus")
if str(VAZUS_DIR) not in sys.path:
    sys.path.insert(0, str(VAZUS_DIR))

from vazus_core.hardware_profiler import HardwareCapProfiler


def test_detect_capabilities_structure():
    """Verify detect_capabilities returns a complete, well-formed dictionary."""
    profiler = HardwareCapProfiler()
    caps = profiler.detect_capabilities()

    assert isinstance(caps, dict)
    assert "cpu_isas" in caps
    assert "accelerators" in caps
    assert "cache_specs" in caps
    assert "system_info" in caps
    assert "probed_at" in caps


def test_cpu_isas_keys_and_types():
    """Verify required CPU ISAs are probed and returned as booleans."""
    profiler = HardwareCapProfiler()
    caps = profiler.detect_capabilities()
    isas = caps["cpu_isas"]

    required_isas = ["AVX2", "AVX-512", "FMA", "BMI2", "NEON"]
    for isa in required_isas:
        assert isa in isas, f"Missing ISA: {isa}"
        assert isinstance(isas[isa], bool), f"ISA {isa} value must be boolean"


def test_accelerators_keys_and_types():
    """Verify accelerator availability flags and device lists are properly populated."""
    profiler = HardwareCapProfiler()
    caps = profiler.detect_capabilities()
    acc = caps["accelerators"]

    assert "openvino_npu" in acc
    assert isinstance(acc["openvino_npu"], bool)

    assert "cuda_gpu" in acc
    assert isinstance(acc["cuda_gpu"], bool)

    assert "openvino_devices" in acc
    assert isinstance(acc["openvino_devices"], list)

    assert "cuda_device_count" in acc
    assert isinstance(acc["cuda_device_count"], int)


def test_cache_specs():
    """Verify L1/L2/L3 cache line alignment and cache size specs."""
    profiler = HardwareCapProfiler()
    caps = profiler.detect_capabilities()
    cache = caps["cache_specs"]

    assert "line_size_bytes" in cache
    assert isinstance(cache["line_size_bytes"], int)
    assert cache["line_size_bytes"] > 0

    assert "l1_cache_bytes" in cache
    assert cache["l1_cache_bytes"] is None or isinstance(cache["l1_cache_bytes"], int)

    assert "l2_cache_bytes" in cache
    assert cache["l2_cache_bytes"] is None or isinstance(cache["l2_cache_bytes"], int)

    assert "l3_cache_bytes" in cache
    assert cache["l3_cache_bytes"] is None or isinstance(cache["l3_cache_bytes"], int)


def test_save_profile_to_db_custom_path():
    """Verify persisting hardware profile to sqlite database creates table and inserts record."""
    profiler = HardwareCapProfiler()
    caps = profiler.detect_capabilities()

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_hardware.db")
        result = profiler.save_profile_to_db(db_path)
        assert result is True

        # Verify database contents
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT profile_json, probed_at FROM hardware_profiles")
            rows = cursor.fetchall()
            assert len(rows) == 1

            saved_json = rows[0][0]
            saved_caps = json.loads(saved_json)
            assert saved_caps["cpu_isas"] == caps["cpu_isas"]
            assert saved_caps["accelerators"] == caps["accelerators"]
            assert saved_caps["cache_specs"] == caps["cache_specs"]
            assert rows[0][1] is not None
        finally:
            conn.close()


def test_save_profile_to_db_auto_detects():
    """Verify save_profile_to_db automatically triggers detect_capabilities if not yet called."""
    profiler = HardwareCapProfiler()
    assert profiler._capabilities is None

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "auto_detect.db")
        result = profiler.save_profile_to_db(db_path)
        assert result is True
        assert profiler._capabilities is not None


def test_save_profile_to_db_error_handling():
    """Verify save_profile_to_db handles database write failures gracefully."""
    profiler = HardwareCapProfiler()
    invalid_path = os.path.join("Z:\\non_existent_dir_12345", "invalid.db")
    result = profiler.save_profile_to_db(invalid_path)
    assert result is False


def test_mocked_arm_neon_detection():
    """Verify ARM machine architecture sets NEON flag to True."""
    profiler = HardwareCapProfiler()
    with patch("platform.machine", return_value="aarch64"):
        caps = profiler.detect_capabilities()
        assert caps["cpu_isas"]["NEON"] is True


def test_mocked_cuda_accelerator_detection():
    """Verify CUDA accelerator detection when torch.cuda.is_available is mocked."""
    profiler = HardwareCapProfiler()
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = True
    mock_torch.cuda.device_count.return_value = 2
    mock_torch.cuda.get_device_name.return_value = "NVIDIA GeForce RTX 4090"

    with patch.dict(sys.modules, {"torch": mock_torch}):
        acc = profiler._probe_accelerators()
        assert acc["cuda_gpu"] is True
        assert acc["cuda_device_count"] == 2
        assert acc["cuda_device_name"] == "NVIDIA GeForce RTX 4090"


def test_mocked_openvino_npu_detection():
    """Verify OpenVINO NPU detection when OpenVINO Core returns NPU device."""
    profiler = HardwareCapProfiler()
    mock_core = MagicMock()
    mock_core.available_devices = ["CPU", "NPU"]

    with patch("openvino.Core", return_value=mock_core):
        acc = profiler._probe_accelerators()
        assert acc["openvino_npu"] is True
        assert "NPU" in acc["openvino_devices"]


# ADVERSARIAL STRESS TESTS FOR MILESTONE 1 CHALLENGE


def test_adversarial_invalid_db_paths():
    """Verify save_profile_to_db returns False gracefully for various invalid paths."""
    profiler = HardwareCapProfiler()

    # Non-existent directory
    invalid_dir_path = os.path.join("non_existent_folder_xyz987", "test.db")
    assert profiler.save_profile_to_db(invalid_dir_path) is False

    # Directory instead of file
    with tempfile.TemporaryDirectory() as tmpdir:
        assert profiler.save_profile_to_db(tmpdir) is False

    # Null byte in filename
    assert profiler.save_profile_to_db("test_\x00_invalid.db") is False


def test_adversarial_readonly_db_permissions():
    """Verify save_profile_to_db returns False when target file is read-only."""
    profiler = HardwareCapProfiler()
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "readonly.db")
        open(db_path, "w").close()
        os.chmod(db_path, 0o444)
        if sys.platform == "win32":
            import stat

            os.chmod(db_path, stat.S_IREAD)
        try:
            assert profiler.save_profile_to_db(db_path) is False
        finally:
            os.chmod(db_path, 0o777)


def test_adversarial_memory_db_path():
    """Verify save_profile_to_db succeeds with SQLite :memory: path."""
    profiler = HardwareCapProfiler()
    assert profiler.save_profile_to_db(":memory:") is True


def test_adversarial_unserializable_capabilities():
    """Verify save_profile_to_db handles JSON serialization failures gracefully."""
    profiler = HardwareCapProfiler()
    profiler.detect_capabilities()
    profiler._capabilities["unserializable"] = set([1, 2, 3])
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        assert profiler.save_profile_to_db(db_path) is False


def test_adversarial_openvino_failures():
    """Verify OpenVINO probing handles Core initialization errors and missing properties safely."""
    profiler = HardwareCapProfiler()
    with patch("openvino.Core", side_effect=RuntimeError("OpenVINO driver failure")):
        caps = profiler.detect_capabilities()
        assert "accelerators" in caps
        assert caps["accelerators"]["openvino_available"] is False

    mock_core = MagicMock()
    mock_core.available_devices = ["CPU"]
    mock_core.get_property.side_effect = Exception("Property not supported")
    with patch("openvino.Core", return_value=mock_core):
        caps = profiler.detect_capabilities()
        assert caps["cpu_isas"]["AVX2"] is not None


def test_adversarial_pytorch_cuda_partial_failures():
    """Verify PyTorch CUDA probing degrades gracefully when get_device_name fails."""
    profiler = HardwareCapProfiler()
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = True
    mock_torch.cuda.device_count.return_value = 1
    mock_torch.cuda.get_device_name.side_effect = RuntimeError("CUDA driver error")

    with patch.dict(sys.modules, {"torch": mock_torch}):
        acc = profiler._probe_accelerators()
        assert acc["cuda_gpu"] is True
        assert acc["cuda_device_count"] == 1
        assert acc["cuda_device_name"] is None


def test_adversarial_win32_isa_exceptions():
    """Verify Win32 ISA probing handles kernel32 OS errors without crashing."""
    profiler = HardwareCapProfiler()
    with patch("ctypes.windll.kernel32.IsProcessorFeaturePresent", side_effect=OSError("Access denied")):
        flags = {"AVX2": False, "AVX-512": False, "FMA": False, "BMI2": False, "NEON": False}
        profiler._probe_win32_isas(flags)
        # Should complete silently without throwing


def test_adversarial_empty_machine_arch():
    """Verify empty machine string from platform.machine does not crash profiler."""
    profiler = HardwareCapProfiler()
    with patch("platform.machine", return_value=""):
        caps = profiler.detect_capabilities()
        assert "cpu_isas" in caps


def test_adversarial_multithreaded_db_writes():
    """Verify 20 concurrent threads calling save_profile_to_db on same database do not crash."""
    import threading

    profiler = HardwareCapProfiler()
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "concurrent.db")
        results = []

        def worker():
            p = HardwareCapProfiler()
            res = p.save_profile_to_db(db_path)
            results.append(res)

        threads = [threading.Thread(target=worker) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 20
        # At least one write succeeded and no exceptions were raised
        assert any(r is True for r in results)


def test_adversarial_win32_cache_info_failure():
    """Verify Win32 cache probing falls back safely if GetLogicalProcessorInformation returns 0."""
    profiler = HardwareCapProfiler()
    if sys.platform == "win32":
        with patch("ctypes.windll.kernel32.GetLogicalProcessorInformation", return_value=0):
            line_size, caches = profiler._probe_win32_cache()
            assert line_size is None
            assert caches == {}


def test_adversarial_unicode_db_path():
    """Verify saving profile to a database path with Unicode Cyrillic characters and spaces."""
    profiler = HardwareCapProfiler()
    with tempfile.TemporaryDirectory() as tmpdir:
        unicode_dir = os.path.join(tmpdir, "профиль_hardware_2026")
        os.makedirs(unicode_dir, exist_ok=True)
        db_path = os.path.join(unicode_dir, "база_данных.db")
        assert profiler.save_profile_to_db(db_path) is True


def test_adversarial_extreme_payload_db_save():
    """Verify saving an extremely large hardware profile payload (10 MB) into SQLite."""
    profiler = HardwareCapProfiler()
    caps = profiler.detect_capabilities()
    caps["large_blob"] = "X" * 10 * 1024 * 1024
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "large.db")
        assert profiler.save_profile_to_db(db_path) is True

