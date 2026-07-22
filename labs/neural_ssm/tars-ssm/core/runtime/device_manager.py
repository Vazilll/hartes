"""
═══════════════════════════════════════════════════════════════
  DeviceManager — Unified Device Abstraction for TARS
═══════════════════════════════════════════════════════════════

Centralizes all device selection logic.
Replaces scattered `if cuda/cpu` checks throughout the codebase.

Usage:
    from core.runtime.device_manager import DeviceManager, get_device_manager

    dm = get_device_manager()
    device = dm.get_inference_device("large")   # "cuda" or "cpu"
    device = dm.get_inference_device("small")   # "npu" or "cpu"
    providers = dm.get_ort_providers()           # ["DmlEP", "CUDAEP", "CPUEP"]
"""

import logging
from typing import List, Optional

logger = logging.getLogger("Tars.DeviceManager")


class DeviceManager:
    """
    Unified device manager for TARS.
    
    Handles CPU / GPU (CUDA) / NPU selection for different workloads.
    NPU is preferred for lightweight inference tasks (sleep mode, VAD, reflexes).
    GPU is preferred for heavy inference (main model) and training.
    CPU is the universal fallback.
    """
    
    def __init__(self):
        from core.runtime.npu_backend import NPUBackend
        
        self.npu_info = NPUBackend.detect()
        self._torch_available = False
        self._cuda_available = False
        
        try:
            import torch
            self._torch_available = True
            self._cuda_available = torch.cuda.is_available()
        except ImportError:
            pass
        
        logger.info(
            f"DeviceManager: GPU={'✅' if self._cuda_available else '❌'}, "
            f"NPU={'✅ ' + self.npu_info.provider if self.npu_info.available else '❌'}"
        )
    
    @property
    def has_gpu(self) -> bool:
        return self._cuda_available
    
    @property
    def has_npu(self) -> bool:
        return self.npu_info.available
    
    @property
    def has_real_npu(self) -> bool:
        """True only if actual NPU (not GPU via DirectML)."""
        return self.npu_info.is_npu
    
    def get_inference_device(self, model_size: str = "medium") -> str:
        """
        Auto-select best device for inference.
        
        Args:
            model_size: "tiny" / "small" (< 10M params, prefer NPU)
                        "medium" (10-100M, GPU preferred)
                        "large" (> 100M, GPU only)
        
        Returns:
            PyTorch device string: "cuda", "cpu"
            Note: NPU is accessed via ONNX Runtime, not PyTorch.
                  For NPU workloads, use get_ort_providers() instead.
        """
        if model_size in ("tiny", "small"):
            # Small models: GPU if available, else CPU
            # NPU path is via ONNX Runtime, not torch device
            if self._cuda_available:
                return "cuda"
            return "cpu"
        
        elif model_size == "medium":
            if self._cuda_available:
                return "cuda"
            return "cpu"
        
        else:  # "large"
            if self._cuda_available:
                return "cuda"
            return "cpu"
    
    def get_training_device(self) -> str:
        """
        Device for training (backward pass).
        NPU does NOT support autograd — training is GPU/CPU only.
        """
        if self._cuda_available:
            return "cuda"
        return "cpu"
    
    def get_ort_providers(self, prefer_npu: bool = True) -> List[str]:
        """
        Get ordered ONNX Runtime providers.
        Delegates to NPUBackend.
        """
        from core.runtime.npu_backend import NPUBackend
        return NPUBackend.get_ort_providers(prefer_npu=prefer_npu)
    
    def get_sleep_mode_config(self) -> dict:
        """
        Configuration for sleep mode (B=0).
        
        Returns dict with:
            device: "npu" or "cpu"
            vad_provider: ONNX provider for VAD
            estimated_power_watts: TDP estimate
            prefetch_strategy: "madvise" or "none"
        """
        if self.npu_info.available:
            return {
                "device": "npu",
                "vad_provider": self.npu_info.provider,
                "estimated_power_watts": self.npu_info.estimated_tdp_watts,
                "prefetch_strategy": "madvise",
            }
        else:
            return {
                "device": "cpu",
                "vad_provider": "CPUExecutionProvider",
                "estimated_power_watts": 25.0,
                "prefetch_strategy": "madvise",
            }
    
    def summary(self) -> str:
        """One-line summary of available devices."""
        parts = []
        if self._cuda_available:
            parts.append("GPU(CUDA)")
        if self.npu_info.is_npu:
            parts.append(f"NPU({self.npu_info.provider.replace('ExecutionProvider', '')})")
        elif self.npu_info.available:
            parts.append(f"Accel({self.npu_info.provider.replace('ExecutionProvider', '')})")
        parts.append("CPU")
        return " → ".join(parts)


# ═══════════════════════════════════════
# Global singleton
# ═══════════════════════════════════════
_global_dm: Optional[DeviceManager] = None


def get_device_manager() -> DeviceManager:
    """Get or create global DeviceManager singleton."""
    global _global_dm
    if _global_dm is None:
        _global_dm = DeviceManager()
    return _global_dm
