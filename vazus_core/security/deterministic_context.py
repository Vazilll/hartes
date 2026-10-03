"""
Deterministic Session Context alias in vazus_core.security.
Re-exports from vazus_core.engine.deterministic_context for modular security context tracking.
"""

from vazus_core.engine.deterministic_context import (
    DeterministicSessionContext,
    VirtualClock,
)

__all__ = ["VirtualClock", "DeterministicSessionContext"]
