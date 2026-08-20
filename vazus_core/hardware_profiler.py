"""
Hardware Microarchitecture Auto-Prober for vazus SuperGraph OS v4.0.
Probes CPU ISAs (AVX2, AVX-512, FMA, BMI2, NEON), accelerator availability (OpenVINO NPU, CUDA GPU),
and L1/L2/L3 cache line alignment specifications.
"""

import ctypes
import datetime
import json
import logging
import os
import platform
import sqlite3
import sys
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class HardwareCapProfiler:
    """Probes hardware capabilities including CPU ISAs, accelerators, and cache parameters."""

    def __init__(self) -> None:
        self._capabilities: Optional[Dict[str, Any]] = None

    def detect_capabilities(self) -> Dict[str, Any]:
        """
        Probe CPU ISAs, accelerator availability, and cache specifications.
        Returns a dictionary containing all probed hardware capabilities.
        """
        cpu_isas = self._probe_cpu_isas()
        accelerators = self._probe_accelerators()
        cache_specs = self._probe_cache_specs()

        capabilities = {
            "cpu_isas": cpu_isas,
            "accelerators": accelerators,
            "cache_specs": cache_specs,
            "system_info": {
                "platform": platform.platform(),
                "machine": platform.machine(),
                "processor": platform.processor(),
                "python_version": sys.version,
            },
            "probed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

        self._capabilities = capabilities
        return capabilities

    def save_profile_to_db(self, db_path: Optional[str] = None) -> bool:
        """
        Persist hardware profile JSON to table `hardware_profiles` in sqlite db.
        Schema: hardware_profiles (id INTEGER PRIMARY KEY AUTOINCREMENT, profile_json TEXT, probed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
        """
        from vazus_core.memory.db import DEFAULT_VAZUS_DB
        target_db = db_path or DEFAULT_VAZUS_DB
        try:
            if self._capabilities is None:
                self.detect_capabilities()

            profile_json = json.dumps(self._capabilities, indent=2)

            conn = sqlite3.connect(target_db)
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS hardware_profiles (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        profile_json TEXT,
                        probed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                cursor.execute(
                    "INSERT INTO hardware_profiles (profile_json) VALUES (?)",
                    (profile_json,),
                )
                conn.commit()
                return True
            finally:
                conn.close()
        except Exception as err:
            logger.error(f"Failed to save hardware profile to database '{db_path}': {err}")
            return False

    def _probe_cpu_isas(self) -> Dict[str, bool]:
        """Probe CPU ISAs: AVX2, AVX-512, FMA, BMI2, NEON."""
        flags = {
            "AVX2": False,
            "AVX-512": False,
            "FMA": False,
            "BMI2": False,
            "NEON": False,
        }

        # 1. Platform / OS specific ctypes inspection (Windows API & CPUID)
        self._probe_win32_isas(flags)
        self._probe_cpuid(flags)

        # 2. Linux /proc/cpuinfo inspection
        self._probe_proc_cpuinfo(flags)

        # 3. macOS sysctl inspection
        self._probe_macos_sysctl(flags)

        # 4. OpenVINO CPU capabilities inspection
        self._probe_openvino_cpu_caps(flags)

        # 5. PyTorch CPU capability inspection
        self._probe_pytorch_cpu_caps(flags)

        # 6. Architecture / machine fallback
        machine = platform.machine().lower()
        if "arm" in machine or "aarch64" in machine:
            # ARM64 architecture standardly includes NEON (ASIMD)
            flags["NEON"] = True

        return flags

    def _probe_win32_isas(self, flags: Dict[str, bool]) -> None:
        """Probe CPU features via Windows API (IsProcessorFeaturePresent)."""
        if sys.platform != "win32":
            return
        try:
            kernel32 = ctypes.windll.kernel32
            # Standard Windows processor feature flags:
            # PF_ARM_NEON_INSTRUCTIONS_AVAILABLE = 19
            # PF_AVX2_INSTRUCTIONS_AVAILABLE = 40
            # PF_AVX512F_INSTRUCTIONS_AVAILABLE = 41
            if kernel32.IsProcessorFeaturePresent(40):  # PF_AVX2
                flags["AVX2"] = True
            if kernel32.IsProcessorFeaturePresent(41):  # PF_AVX512F
                flags["AVX-512"] = True
            if kernel32.IsProcessorFeaturePresent(19):  # PF_ARM_NEON
                flags["NEON"] = True
        except Exception:
            pass

    def _probe_cpuid(self, flags: Dict[str, bool]) -> None:
        """Execute CPUID directly on x86/x86_64 architectures using ctypes."""
        machine = platform.machine().lower()
        if machine not in ("amd64", "x86_64", "x86"):
            return
        if sys.platform != "win32":
            # Native CPUID memory allocation is win32 specific in this helper;
            # Linux/macOS are handled by /proc/cpuinfo & sysctl.
            return

        try:
            # 64-bit Windows calling convention for CPUID wrapper:
            # RCX=leaf, RDX=subleaf, R8=pointer to int[4]
            code = bytes([
                0x53,                   # push rbx
                0x89, 0xc8,             # mov eax, ecx
                0x89, 0xd1,             # mov ecx, edx
                0x0f, 0xa2,             # cpuid
                0x41, 0x89, 0x00,       # mov dword ptr [r8], eax
                0x41, 0x89, 0x58, 0x04, # mov dword ptr [r8+4], ebx
                0x41, 0x89, 0x48, 0x08, # mov dword ptr [r8+8], ecx
                0x41, 0x89, 0x50, 0x0c, # mov dword ptr [r8+12], edx
                0x5b,                   # pop rbx
                0xc3                    # ret
            ])

            MEM_COMMIT = 0x1000
            MEM_RESERVE = 0x2000
            PAGE_EXECUTE_READWRITE = 0x40

            kernel32 = ctypes.windll.kernel32
            kernel32.VirtualAlloc.restype = ctypes.c_void_p
            kernel32.VirtualAlloc.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_ulong, ctypes.c_ulong]
            ptr = kernel32.VirtualAlloc(None, len(code), MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE)
            if not ptr:
                return

            try:
                ctypes.memmove(ptr, code, len(code))
                CMPFUNC = ctypes.CFUNCTYPE(None, ctypes.c_uint32, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32 * 4))
                func = CMPFUNC(ptr)

                # Leaf 1: FMA & AVX
                regs1 = (ctypes.c_uint32 * 4)()
                func(1, 0, ctypes.byref(regs1))
                ecx1 = regs1[2]
                if ecx1 & (1 << 12):  # FMA bit
                    flags["FMA"] = True

                # Leaf 7, Subleaf 0: AVX2, BMI2, AVX-512
                regs7 = (ctypes.c_uint32 * 4)()
                func(7, 0, ctypes.byref(regs7))
                ebx7 = regs7[1]
                if ebx7 & (1 << 5):   # AVX2 bit
                    flags["AVX2"] = True
                if ebx7 & (1 << 8):   # BMI2 bit
                    flags["BMI2"] = True
                if ebx7 & (1 << 16):  # AVX512F bit
                    flags["AVX-512"] = True
            finally:
                kernel32.VirtualFree.restype = ctypes.c_bool
                kernel32.VirtualFree.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_ulong]
                kernel32.VirtualFree(ptr, 0, 0x8000)  # MEM_RELEASE
        except Exception:
            pass

    def _probe_proc_cpuinfo(self, flags: Dict[str, bool]) -> None:
        """Parse Linux /proc/cpuinfo if available."""
        if not os.path.exists("/proc/cpuinfo"):
            return
        try:
            with open("/proc/cpuinfo", "r", encoding="utf-8", errors="ignore") as f:
                content = f.read().lower()
                if "avx2" in content:
                    flags["AVX2"] = True
                if "avx512f" in content or "avx512" in content:
                    flags["AVX-512"] = True
                if "fma" in content:
                    flags["FMA"] = True
                if "bmi2" in content:
                    flags["BMI2"] = True
                if "neon" in content or "asimd" in content:
                    flags["NEON"] = True
        except Exception:
            pass

    def _probe_macos_sysctl(self, flags: Dict[str, bool]) -> None:
        """Probe macOS sysctl features if on Darwin."""
        if sys.platform != "darwin":
            return
        try:
            import subprocess
            res = subprocess.run(["sysctl", "-a"], capture_output=True, text=True, timeout=2)
            out = res.stdout.lower()
            if "hw.optional.avx2: 1" in out:
                flags["AVX2"] = True
            if "hw.optional.avx512f: 1" in out or "hw.optional.avx512: 1" in out:
                flags["AVX-512"] = True
            if "hw.optional.fma: 1" in out:
                flags["FMA"] = True
            if "hw.optional.bmi2: 1" in out:
                flags["BMI2"] = True
            if "hw.optional.neon: 1" in out or "hw.optional.arm64: 1" in out:
                flags["NEON"] = True
        except Exception:
            pass

    def _probe_openvino_cpu_caps(self, flags: Dict[str, bool]) -> None:
        """Probe OpenVINO CPU optimization capabilities."""
        try:
            try:
                import openvino as ov
                core = ov.Core()
            except (ImportError, AttributeError):
                import openvino.runtime as ov_rt
                core = ov_rt.Core()

            if "CPU" in core.available_devices:
                caps = core.get_property("CPU", "OPTIMIZATION_CAPABILITIES")
                caps_str = [str(c).upper() for c in caps]
                if any("AVX2" in c for c in caps_str):
                    flags["AVX2"] = True
                if any("AVX512" in c for c in caps_str):
                    flags["AVX-512"] = True
                if any("FMA" in c for c in caps_str):
                    flags["FMA"] = True
                if any("BMI2" in c for c in caps_str):
                    flags["BMI2"] = True
        except Exception:
            pass

    def _probe_pytorch_cpu_caps(self, flags: Dict[str, bool]) -> None:
        """Probe PyTorch CPU capabilities."""
        try:
            import torch
            if hasattr(torch.backends, "cpu") and hasattr(torch.backends.cpu, "get_cpu_capability"):
                cap = torch.backends.cpu.get_cpu_capability().upper()
                if "AVX512" in cap:
                    flags["AVX-512"] = True
                    flags["AVX2"] = True
                    flags["FMA"] = True
                elif "AVX2" in cap:
                    flags["AVX2"] = True
                    flags["FMA"] = True
        except Exception:
            pass

    def _probe_accelerators(self) -> Dict[str, Any]:
        """Probe accelerator availability (OpenVINO NPU, CUDA GPUs)."""
        openvino_devices: List[str] = []
        openvino_npu: bool = False
        openvino_available: bool = False

        try:
            try:
                import openvino as ov
                core = ov.Core()
            except (ImportError, AttributeError):
                import openvino.runtime as ov_rt
                core = ov_rt.Core()
            openvino_devices = [str(dev) for dev in core.available_devices]
            openvino_available = True
            openvino_npu = "NPU" in openvino_devices
        except Exception:
            pass

        cuda_gpu: bool = False
        cuda_device_count: int = 0
        cuda_device_name: Optional[str] = None

        try:
            import torch
            cuda_gpu = bool(torch.cuda.is_available())
            if cuda_gpu:
                cuda_device_count = int(torch.cuda.device_count())
                if cuda_device_count > 0:
                    cuda_device_name = str(torch.cuda.get_device_name(0))
        except Exception:
            pass

        return {
            "openvino_npu": openvino_npu,
            "cuda_gpu": cuda_gpu,
            "openvino_available": openvino_available,
            "openvino_devices": openvino_devices,
            "cuda_device_count": cuda_device_count,
            "cuda_device_name": cuda_device_name,
        }

    def _probe_cache_specs(self) -> Dict[str, Any]:
        """
        Probe L1/L2/L3 cache line alignment specifications (e.g. 64-byte line size,
        cache sizes or fallback defaults if OS sysconf is unavailable).
        """
        line_size_bytes = 64  # standard fallback line size
        l1_cache_bytes: Optional[int] = None
        l2_cache_bytes: Optional[int] = None
        l3_cache_bytes: Optional[int] = None

        # 1. Try Windows API
        if sys.platform == "win32":
            win_line_size, win_caches = self._probe_win32_cache()
            if win_line_size:
                line_size_bytes = win_line_size
            if "L1" in win_caches:
                l1_cache_bytes = win_caches["L1"]
            if "L2" in win_caches:
                l2_cache_bytes = win_caches["L2"]
            if "L3" in win_caches:
                l3_cache_bytes = win_caches["L3"]

        # 2. Try Linux sysconf / sysfs
        if sys.platform.startswith("linux"):
            lin_line_size, lin_caches = self._probe_linux_cache()
            if lin_line_size:
                line_size_bytes = lin_line_size
            if lin_caches.get("L1"):
                l1_cache_bytes = lin_caches["L1"]
            if lin_caches.get("L2"):
                l2_cache_bytes = lin_caches["L2"]
            if lin_caches.get("L3"):
                l3_cache_bytes = lin_caches["L3"]

        # 3. Fallback defaults if cache sizes remain undetected
        if l1_cache_bytes is None:
            l1_cache_bytes = 65536  # 64 KB fallback
        if l2_cache_bytes is None:
            l2_cache_bytes = 2097152  # 2 MB fallback
        if l3_cache_bytes is None:
            l3_cache_bytes = 12582912  # 12 MB fallback

        return {
            "line_size_bytes": line_size_bytes,
            "l1_cache_bytes": l1_cache_bytes,
            "l2_cache_bytes": l2_cache_bytes,
            "l3_cache_bytes": l3_cache_bytes,
        }

    def _probe_win32_cache(self) -> Tuple[Optional[int], Dict[str, int]]:
        """Query Win32 GetLogicalProcessorInformation for cache specs."""
        try:
            class CACHE_DESCRIPTOR(ctypes.Structure):
                _fields_ = [
                    ("Level", ctypes.c_byte),
                    ("Associativity", ctypes.c_byte),
                    ("LineSize", ctypes.c_ushort),
                    ("Size", ctypes.c_ulong),
                    ("Type", ctypes.c_int),
                ]

            class SYSTEM_LOGICAL_PROCESSOR_INFORMATION(ctypes.Structure):
                class _UNION(ctypes.Union):
                    _fields_ = [
                        ("ProcessorCore", ctypes.c_byte),
                        ("NumaNode", ctypes.c_ulong),
                        ("Cache", CACHE_DESCRIPTOR),
                        ("Reserved", ctypes.c_ulonglong * 2),
                    ]
                _fields_ = [
                    ("ProcessorMask", ctypes.c_size_t),
                    ("Relationship", ctypes.c_int),
                    ("u", _UNION),
                ]

            kernel32 = ctypes.windll.kernel32
            buffer_size = ctypes.c_ulong(0)
            kernel32.GetLogicalProcessorInformation(None, ctypes.byref(buffer_size))

            if buffer_size.value == 0:
                return None, {}

            buf = (ctypes.c_byte * buffer_size.value)()
            if not kernel32.GetLogicalProcessorInformation(ctypes.byref(buf), ctypes.byref(buffer_size)):
                return None, {}

            elem_size = ctypes.sizeof(SYSTEM_LOGICAL_PROCESSOR_INFORMATION)
            count = buffer_size.value // elem_size
            info_arr = ctypes.cast(buf, ctypes.POINTER(SYSTEM_LOGICAL_PROCESSOR_INFORMATION))

            line_size = None
            caches: Dict[str, int] = {}

            for i in range(count):
                item = info_arr[i]
                if item.Relationship == 2:  # RelationCache
                    cache = item.u.Cache
                    if cache.LineSize > 0:
                        line_size = int(cache.LineSize)
                    level_key = f"L{cache.Level}"
                    if level_key not in caches or cache.Size > caches[level_key]:
                        caches[level_key] = int(cache.Size)

            return line_size, caches
        except Exception:
            return None, {}

    def _probe_linux_cache(self) -> Tuple[Optional[int], Dict[str, int]]:
        """Query Linux sysconf / sysfs for cache line size and cache sizes."""
        line_size = None
        caches: Dict[str, int] = {}
        try:
            if hasattr(os, "sysconf"):
                try:
                    val = os.sysconf("SC_LEVEL1_DCACHE_LINESIZE")
                    if isinstance(val, int) and val > 0:
                        line_size = val
                except (ValueError, OSError):
                    pass

            base_dir = "/sys/devices/system/cpu/cpu0/cache"
            if os.path.exists(base_dir):
                for index_dir in os.listdir(base_dir):
                    index_path = os.path.join(base_dir, index_dir)
                    if os.path.isdir(index_path):
                        level_file = os.path.join(index_path, "level")
                        size_file = os.path.join(index_path, "size")
                        ls_file = os.path.join(index_path, "coherency_line_size")

                        if os.path.exists(ls_file) and line_size is None:
                            with open(ls_file, "r") as f:
                                line_size = int(f.read().strip())

                        if os.path.exists(level_file) and os.path.exists(size_file):
                            with open(level_file, "r") as f:
                                lvl = f.read().strip()
                            with open(size_file, "r") as f:
                                raw_sz = f.read().strip().upper()
                            sz_bytes = 0
                            if raw_sz.endswith("K"):
                                sz_bytes = int(raw_sz[:-1]) * 1024
                            elif raw_sz.endswith("M"):
                                sz_bytes = int(raw_sz[:-1]) * 1024 * 1024
                            elif raw_sz.isdigit():
                                sz_bytes = int(raw_sz)
                            caches[f"L{lvl}"] = sz_bytes
        except Exception:
            pass
        return line_size, caches
