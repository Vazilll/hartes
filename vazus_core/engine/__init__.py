"""
vazus_core.engine subpackage.
"""

__all__ = [
    "Gemma4NPUEngine",
    "GenerationResult",
    "EngineTelemetry",
    "StreamToken",
    "SpeculativeNPUEngine",
    "SpeculativeDraft",
    "SpeculativeResult",
]


def __getattr__(name: str):
    if name in ["Gemma4NPUEngine", "GenerationResult", "EngineTelemetry", "StreamToken"]:
        import vazus_core.engine.gemma4_npu_engine as _mod
        return getattr(_mod, name)
    if name in ["SpeculativeNPUEngine", "SpeculativeDraft", "SpeculativeResult"]:
        import vazus_core.engine.speculative_npu_engine as _smod
        return getattr(_smod, name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


