"""
vazus_autonomous_harness.memory.titans — Titans Test-Time Neural Memory (arXiv:2501.00663).

Implements long-term associative neural memory with test-time surprise-based gradient descent
and adaptive momentum for super-long context (>128K tokens) retention.

Mathematical Formulation:
- L_surprise(x_t) = ||x̂_t - x_t||^2
- g_t = ∇_M L_surprise(x_t)
- S_t = η_t * S_{t-1} - θ_t * g_t (momentum accumulation)
- M_t = (1 - α_t) * M_{t-1} + S_t ⊗ v_t^T (associative matrix update)
"""

import math
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
import numpy as np


@dataclass
class TitansConfig:
    dim: int = 64
    eta: float = 0.9          # Momentum decay factor
    theta: float = 0.05       # Surprise gradient step size
    alpha: float = 0.01       # Memory forget gate rate
    eps: float = 1e-8


class TitansNeuralMemory:
    """
    Titans / ATLAS Long-Term Test-Time Neural Memory Engine.
    Provides O(1) continuous state updates without token context exhaustion.
    """

    def __init__(self, config: Optional[TitansConfig] = None):
        self.config = config or TitansConfig()
        self.dim = self.config.dim
        # M_t: dim x dim associative memory weight matrix
        self.M = np.zeros((self.dim, self.dim), dtype=np.float32)
        # S_t: momentum buffer for fast adaptation
        self.S = np.zeros((self.dim, self.dim), dtype=np.float32)
        self.total_steps = 0
        self.cumulative_surprise = 0.0

    def _normalize(self, v: np.ndarray) -> np.ndarray:
        norm = np.linalg.norm(v)
        if norm > self.config.eps:
            return v / norm
        return v

    def retrieve(self, query: np.ndarray) -> np.ndarray:
        """
        Associative recall from long-term memory: y = M * query.
        """
        q = np.asarray(query, dtype=np.float32).reshape(-1)
        if len(q) != self.dim:
            # Pad or truncate to self.dim
            q = np.pad(q, (0, max(0, self.dim - len(q))))[:self.dim]
        q_norm = self._normalize(q)
        recalled = np.matmul(self.M, q_norm)
        return recalled

    def step(self, key: np.ndarray, value: np.ndarray, target: Optional[np.ndarray] = None) -> float:
        """
        Executes a single test-time surprise-based gradient update step:
        1. Predict: ŷ = M * key
        2. Surprise: L_surprise = ||ŷ - target||^2 (defaults to target=value)
        3. Gradient: g = 2 * (ŷ - target) ⊗ key^T
        4. Momentum: S = eta * S - theta * g
        5. Memory: M = (1 - alpha) * M + S
        """
        k = np.asarray(key, dtype=np.float32).reshape(-1)
        v = np.asarray(value, dtype=np.float32).reshape(-1)
        
        # Pad or truncate to self.dim
        k = np.pad(k, (0, max(0, self.dim - len(k))))[:self.dim]
        v = np.pad(v, (0, max(0, self.dim - len(v))))[:self.dim]

        k_norm = self._normalize(k)
        t = v if target is None else np.pad(np.asarray(target, dtype=np.float32).reshape(-1), (0, max(0, self.dim - len(target))))[:self.dim]

        # Prediction and surprise
        pred = np.matmul(self.M, k_norm)
        err = pred - t
        surprise = float(np.sum(err ** 2))

        # Gradient with respect to M: dL/dM = 2 * err ⊗ k_norm^T
        grad = 2.0 * np.outer(err, k_norm)

        # Update momentum buffer S_t = eta * S_{t-1} - theta * grad
        self.S = self.config.eta * self.S - self.config.theta * grad

        # Update associative memory M_t = (1 - alpha) * M_{t-1} + S_t
        self.M = (1.0 - self.config.alpha) * self.M + self.S

        self.total_steps += 1
        self.cumulative_surprise += surprise
        return surprise

    def get_stats(self) -> Dict[str, Any]:
        """Returns diagnostic telemetry of the Titans neural memory layer."""
        frobenius_norm = float(np.linalg.norm(self.M))
        avg_surprise = (self.cumulative_surprise / max(1, self.total_steps))
        return {
            "total_steps": self.total_steps,
            "frobenius_norm": round(frobenius_norm, 4),
            "avg_surprise": round(avg_surprise, 4),
            "dim": self.dim,
        }

    def reset(self):
        """Clears memory buffers."""
        self.M.fill(0.0)
        self.S.fill(0.0)
        self.total_steps = 0
        self.cumulative_surprise = 0.0
