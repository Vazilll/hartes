"""
vazus_core.evolution
Bio-inspired Autonomous Evolution & Recursive Self-Improvement Engine.
Active: Darwinian code evolution (sandboxed, MCP-exposed). Legacy Hebbian
compilation and prompt gradient optimization were removed 2026-08-15.
"""

from .darwinian_evolver import run_evolution_cycle, evaluate_fitness

__all__ = [
    "run_evolution_cycle",
    "evaluate_fitness"
]
