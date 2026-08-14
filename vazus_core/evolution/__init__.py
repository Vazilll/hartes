"""
vazus_core.evolution
Bio-inspired Autonomous Evolution & Recursive Self-Improvement Engine.
Includes Darwinian code crossover, Hebbian tool compilation, and prompt gradient optimization.
"""

from .prompt_optimizer import run as run_prompt_optimization
from .hebbian_compiler import compile_tool as compile_hebbian_tool
from .darwinian_evolver import run_evolution_cycle, evaluate_fitness

__all__ = [
    "run_prompt_optimization",
    "compile_hebbian_tool",
    "run_evolution_cycle",
    "evaluate_fitness"
]
