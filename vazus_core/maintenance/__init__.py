"""
vazus_core.maintenance — Automated Maintenance, Indexing, and Spec Synchronization.
"""

from .auto_index_runner import (
    AutoIndexRunner,
    SpecSynchronizer,
    run_maintenance,
)
from .db_optimizer import optimize_database

__all__ = [
    "AutoIndexRunner",
    "SpecSynchronizer",
    "run_maintenance",
    "optimize_database",
]
