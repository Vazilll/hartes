"""
vazus_core.harness — Autonomous Harness & Neuromorphic Execution Scaffolding.
"""

from vazus_core.harness.reflex_circuit import (
    ReflexCircuitController,
    ReflexSignal,
    ReflexVerdict,
    ReflexActionType,
)
from vazus_core.harness.trajectory_optimizer import (
    TrajectoryOptimizer,
    Trajectory,
    TrajectoryStep,
    MicroRule,
)

__all__ = [
    "ReflexCircuitController",
    "ReflexSignal",
    "ReflexVerdict",
    "ReflexActionType",
    "TrajectoryOptimizer",
    "Trajectory",
    "TrajectoryStep",
    "MicroRule",
]
