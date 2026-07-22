"""
═══════════════════════════════════════════════════════════════
  NPU Backend — Neural Processing Unit Detection & ONNX Runtime
═══════════════════════════════════════════════════════════════

Обнаружение и использование NPU через ONNX Runtime.
Поддерживаемые провайдеры:
  - QNNExecutionProvider     (Qualcomm NPU)
  - DmlExecutionProvider     (DirectML: Intel/AMD/Qualcomm NPU + GPU fallback)
  - OpenVINOExecutionProvider (Intel NPU/VPU)

Tiered fallback: NPU → DirectML(GPU) → CUDA → CPU

Usage:
    from core.runtime.npu_backend import NPUBackend
    
    info = NPUBackend.detect()
    if info.available:
        session = NPUBackend.create_session("model.onnx")
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Any

logger = logging.getLogger("Tars.NPU")

# ═══════════════════════════════════════════
# NPU Provider Priority (best → worst)
# ═══════════════════════════════════════════

NPU_PROVIDERS = [
    "QNNExecutionProvider",       # Qualcomm NPU (Snapdragon X Elite)
    "OpenVINOExecutionProvider",  # Intel NPU (Meteor Lake, Arrow Lake)
    "DmlExecutionProvider",       # DirectML (Windows NPU/GPU universal)
]

GPU_PROVIDERS = [
    "CUDAExecutionProvider",      # NVIDIA GPU
    "ROCMExecutionProvider",      # AMD GPU
    "DmlExecutionProvider",       # DirectML GPU fallback
]

CPU_PROVIDERS = [
    "CPUExecutionProvider",       # Always available
]

# All providers in priority order
ALL_PROVIDERS_PRIORITY = NPU_PROVIDERS + GPU_PROVIDERS + CPU_PROVIDERS


@dataclass
class NPUInfo:
    """Information about detected NPU hardware."""
    available: bool = False
    provider: str = ""              # Active ONNX provider name
    device_name: str = "unknown"    # Human-readable device name
    all_providers: List[str] = field(default_factory=list)
    is_npu: bool = False            # True if actual NPU (not GPU fallback)
    estimated_tdp_watts: float = 0  # Estimated power consumption
    
    def __repr__(self):
        if self.available:
            return f"NPUInfo(provider={self.provider}, device={self.device_name}, tdp≈{self.estimated_tdp_watts}W)"
        return "NPUInfo(not available)"


class NPUBackend:
    """Static utility class for NPU detection and ONNX session management."""
    
    _cached_info: Optional[NPUInfo] = None
    _ort_available: Optional[bool] = None
    
    @classmethod
    def _ensure_ort(cls) -> bool:
        """Check if onnxruntime is installed."""
        if cls._ort_available is not None:
            return cls._ort_available
        try:
            import onnxruntime  # noqa: F401
            cls._ort_available = True
        except ImportError:
            cls._ort_available = False
            logger.debug("onnxruntime not installed — NPU disabled")
        return cls._ort_available
    
    @classmethod
    def detect(cls, force_refresh: bool = False) -> NPUInfo:
        """
        Detect available NPU hardware.
        
        Returns:
            NPUInfo with detection results. Cached after first call.
        """
        if cls._cached_info is not None and not force_refresh:
            return cls._cached_info
        
        info = NPUInfo()
        
        if not cls._ensure_ort():
            cls._cached_info = info
            return info
        
        import onnxruntime as ort
        available = ort.get_available_providers()
        info.all_providers = available
        
        # Find best NPU provider
        for provider in NPU_PROVIDERS:
            if provider in available:
                info.available = True
                info.provider = provider
                info.is_npu = True
                break
        
        # If no NPU, check for GPU (DirectML may be GPU-only)
        if not info.available:
            for provider in GPU_PROVIDERS:
                if provider in available and provider != "DmlExecutionProvider":
                    info.available = True
                    info.provider = provider
                    info.is_npu = False
                    break
        
        # Device name and TDP estimation
        if info.provider == "QNNExecutionProvider":
            info.device_name = "Qualcomm NPU"
            info.estimated_tdp_watts = 5.0
        elif info.provider == "OpenVINOExecutionProvider":
            info.device_name = "Intel NPU"
            info.estimated_tdp_watts = 5.0
        elif info.provider == "DmlExecutionProvider":
            info.device_name = "DirectML (NPU/GPU)"
            info.estimated_tdp_watts = 15.0  # Could be NPU (5W) or GPU (50W)
        elif info.provider == "CUDAExecutionProvider":
            info.device_name = "NVIDIA GPU"
            info.estimated_tdp_watts = 50.0
        elif info.provider == "ROCMExecutionProvider":
            info.device_name = "AMD GPU"
            info.estimated_tdp_watts = 50.0
        
        if info.available:
            logger.info(
                f"NPU detected: {info.provider} ({info.device_name}), "
                f"~{info.estimated_tdp_watts}W"
            )
        else:
            logger.info("No NPU detected — CPU fallback for sleep mode")
        
        cls._cached_info = info
        return info
    
    @classmethod
    def is_available(cls) -> bool:
        """Quick check if any NPU/accelerator is available."""
        return cls.detect().available
    
    @classmethod
    def get_ort_providers(cls, prefer_npu: bool = True) -> List[str]:
        """
        Get ordered list of ONNX Runtime execution providers.
        
        Args:
            prefer_npu: If True, NPU providers come first.
                        If False, GPU providers come first.
        
        Returns:
            List of provider names in priority order.
            Only includes providers actually available on this system.
        """
        if not cls._ensure_ort():
            return ["CPUExecutionProvider"]
        
        import onnxruntime as ort
        available = set(ort.get_available_providers())
        
        if prefer_npu:
            priority = NPU_PROVIDERS + GPU_PROVIDERS + CPU_PROVIDERS
        else:
            priority = GPU_PROVIDERS + NPU_PROVIDERS + CPU_PROVIDERS
        
        # Filter to only available providers (deduplicated, order preserved)
        result = []
        seen = set()
        for p in priority:
            if p in available and p not in seen:
                result.append(p)
                seen.add(p)
        
        # Always include CPU as final fallback
        if "CPUExecutionProvider" not in seen:
            result.append("CPUExecutionProvider")
        
        return result
    
    @classmethod
    def create_session(
        cls,
        onnx_path: str,
        prefer_npu: bool = True,
        session_options: Any = None,
    ) -> Any:
        """
        Create an ONNX Runtime InferenceSession with best available provider.
        
        Args:
            onnx_path: Path to .onnx model file
            prefer_npu: If True, try NPU first
            session_options: Optional ort.SessionOptions
        
        Returns:
            ort.InferenceSession configured for best available hardware
        
        Raises:
            ImportError: If onnxruntime is not installed
        """
        if not cls._ensure_ort():
            raise ImportError(
                "onnxruntime not installed. "
                "Install: pip install onnxruntime-directml (Windows NPU) "
                "or pip install onnxruntime (CPU only)"
            )
        
        import onnxruntime as ort
        
        providers = cls.get_ort_providers(prefer_npu=prefer_npu)
        
        if session_options is None:
            session_options = ort.SessionOptions()
            session_options.graph_optimization_level = (
                ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            )
            # Reduce thread contention in sleep mode
            session_options.intra_op_num_threads = 2
            session_options.inter_op_num_threads = 1
        
        # Try providers in order, fall back on failure
        last_error = None
        for i in range(len(providers)):
            try_providers = providers[i:]
            try:
                session = ort.InferenceSession(
                    onnx_path,
                    sess_options=session_options,
                    providers=try_providers,
                )
                active = session.get_providers()
                logger.info(
                    f"ONNX session created: {onnx_path} → {active[0]}"
                )
                return session
            except Exception as e:
                last_error = e
                logger.debug(f"Provider {try_providers[0]} failed: {e}")
                continue
        
        # Final fallback: CPU only
        try:
            session = ort.InferenceSession(
                onnx_path,
                sess_options=session_options,
                providers=["CPUExecutionProvider"],
            )
            logger.warning(f"ONNX session fallback to CPU: {onnx_path}")
            return session
        except Exception:
            raise RuntimeError(
                f"Failed to create ONNX session for {onnx_path}: {last_error}"
            )
    
    @classmethod
    def active_provider_name(cls, session: Any) -> str:
        """Get the name of the active provider for an ONNX session."""
        try:
            providers = session.get_providers()
            return providers[0] if providers else "unknown"
        except Exception:
            return "unknown"
    
    @classmethod
    def power_estimate(cls) -> dict:
        """
        Estimate power consumption for different compute paths.
        
        Returns dict with estimated TDP in watts for each available path.
        """
        info = cls.detect()
        estimates = {"cpu": 25.0}  # Typical laptop CPU package
        
        if info.is_npu:
            estimates["npu"] = info.estimated_tdp_watts
        
        try:
            import torch
            if torch.cuda.is_available():
                estimates["gpu"] = 50.0  # Conservative estimate
        except ImportError:
            pass
        
        estimates["sleep_mode"] = (
            info.estimated_tdp_watts if info.available else 25.0
        )
        
        return estimates
