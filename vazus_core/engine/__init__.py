"""
vazus_core.engine subpackage.
"""

__all__ = [
    "Gemma4NPUEngine",
    "GenerationResult",
    "EngineTelemetry",
    "StreamToken",
]


def __getattr__(name: str):
    if name in __all__:
        import vazus_core.engine.gemma4_npu_engine as _mod
        return getattr(_mod, name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

