"""
vazus_core.memory.decay_policy
==============================
Canonical single-source-of-truth constants for biological and cognitive memory decay.
Synchronizes Ebbinghaus stability curves across dynamic_hypergraph and synaptic_pruner.
"""

from __future__ import annotations

# Base temporal bounds in days
DECAY_BASE_DAYS: float = 2.0
DECAY_MAX_DAYS: float = 365.0

# In seconds for time-delta calculations
DEFAULT_BASE_STABILITY: float = 86400.0 * DECAY_BASE_DAYS   # 172,800.0s (2 days)
MAX_STABILITY: float = 86400.0 * DECAY_MAX_DAYS             # 31,536,000.0s (365 days)
BASE_STABILITY: float = DEFAULT_BASE_STABILITY              # Alias for synaptic_pruner compatibility

# Hebbian learning parameters
HEBBIAN_REINFORCEMENT_FACTOR: float = 1.15                  # Multiplier for confirmed links
DEFAULT_ALPHA_STABILITY: float = 0.15                       # Hebbian stability step alpha
DEFAULT_BETA_STABILITY: float = 0.70                        # Hebbian stability power beta

# Pruning & Archival Thresholds
COLD_STORAGE_THRESHOLD: float = 0.05                        # Salience / confidence below this -> cold storage
DECAY_THRESHOLD: float = 0.15                               # Threshold for hypergraph node decay/archival
EDGE_PRUNE_THRESHOLD: float = COLD_STORAGE_THRESHOLD         # Edge pruning cutoff for synaptic pruner
