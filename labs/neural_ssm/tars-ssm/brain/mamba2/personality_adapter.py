# personality_adapter.py — Re-export from canonical implementation
"""
═══════════════════════════════════════════════════════════════
  PersonalityAdapter — Re-export Bridge
═══════════════════════════════════════════════════════════════

Canonical implementation lives in brain/mamba2/adapters/personality_adapter.py.
This file re-exports for backward compatibility.

Usage:
    from brain.mamba2.personality_adapter import PersonalityAdapter
"""

from brain.mamba2.adapters.personality_adapter import (
    PersonalityAdapter,
    PersonalityLoss,
)

__all__ = ["PersonalityAdapter", "PersonalityLoss"]
