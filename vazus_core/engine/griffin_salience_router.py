"""
vazus_core.engine.griffin_salience_router
=========================================
DeepMind Griffin-Gated Salience Router for J-Space.
Combines linear recurrent gating with vector memory cache to intelligently route tasks:
- If J-Space semantic similarity > 0.92 -> Fast Path (<15ms NPU / cached execution).
- Recurrent gating state tracks sequential cognitive load.
- If salience > 0.75 -> Deep Cloud Path (Gemini Pro, formal SMT proofs).
- Otherwise -> Fast Local Path (Gemma 4 NPU / Arc GPU).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Optional

import numpy as np

logger = logging.getLogger("vazus_core.engine.griffin_salience_router")

FORMAL_HIGH_SALIENCE_PATTERNS = [
    re.compile(r"(?i)\b(?:smt|z3|proof|докажи|теорем|инвариант|formal|верификац|concordia|falsif)\b"),
    re.compile(r"(?i)\b(?:архитектур|refactor|evolution|darwin|map_elites|funsearch)\b"),
    re.compile(r"(?i)\b(?:security|jail|cve|vulnerability|exploit)\b"),
]


@dataclass
class RoutingResult:
    """Decision output of Griffin salience gating."""
    tier: str  # "FAST_CACHE", "FAST_LOCAL", "DEEP_CLOUD"
    engine_name: str
    salience_score: float
    recurrent_gate_state: float
    cached_concept_id: Optional[str] = None
    similarity: float = 0.0
    reason: str = ""


class GriffinSalienceRouter:
    """
    Griffin-Gated Neural Attention & Memory Router.
    Implements recurrent gated state h_t = alpha * h_{t-1} + (1 - alpha) * input_salience.
    """

    def __init__(
        self,
        j_space_index: Optional[Any] = None,
        fast_engine: Optional[Any] = None,
        deep_engine: Optional[Any] = None,
        similarity_threshold: float = 0.92,
        salience_threshold: float = 0.75,
        recurrent_alpha: float = 0.70,
    ):
        self.j_space = j_space_index
        self.fast_engine = fast_engine
        self.deep_engine = deep_engine
        self.similarity_threshold = similarity_threshold
        self.salience_threshold = salience_threshold
        self.alpha = recurrent_alpha
        self.h_t: float = 0.20  # Baseline cognitive load state

    def compute_instantaneous_salience(self, query: str) -> float:
        """Calculates instantaneous input salience based on syntax, vocabulary, and keywords."""
        if not query or not query.strip():
            return 0.0

        base_salience = 0.20

        # Pattern matches for formal, high-stakes tasks (SMT, Z3, verification, formal proofs)
        for pat in FORMAL_HIGH_SALIENCE_PATTERNS:
            if pat.search(query):
                base_salience += 0.58
                break

        # Query length / complexity bonus
        word_count = len(query.split())
        if word_count > 60:
            base_salience += 0.20
        elif word_count > 25:
            base_salience += 0.10

        # Code block presence
        if "```" in query or "def " in query or "class " in query:
            base_salience += 0.15

        return min(1.0, round(base_salience, 4))

    def update_recurrent_gate(self, input_salience: float) -> float:
        """Griffin linear recurrence update: h_t = alpha * h_{t-1} + (1 - alpha) * x_t."""
        self.h_t = self.alpha * self.h_t + (1.0 - self.alpha) * input_salience
        return round(self.h_t, 4)

    def route(
        self,
        query: str,
        embedding: Optional[np.ndarray] = None,
    ) -> RoutingResult:
        """
        Routes the task through memory cache, fast local engine, or deep cloud engine.
        """
        # 1. Check J-Space fast memory cache
        if self.j_space is not None and embedding is not None:
            try:
                similar = self.j_space.search_similar(embedding, top_k=1, min_similarity=self.similarity_threshold)
                if similar and similar[0].get("similarity", 0.0) >= self.similarity_threshold:
                    match = similar[0]
                    return RoutingResult(
                        tier="FAST_CACHE",
                        engine_name="JSpaceMemoryCache",
                        salience_score=0.1,
                        recurrent_gate_state=self.h_t,
                        cached_concept_id=match.get("concept_id"),
                        similarity=match.get("similarity", 0.0),
                        reason=f"High-fidelity J-Space match (sim {match.get('similarity'):.3f})",
                    )
            except Exception as e:
                logger.debug("J-Space route lookup error: %s", e)

        # 2. Compute Griffin recurrent gated salience
        instant_s = self.compute_instantaneous_salience(query)
        recurrent_s = self.update_recurrent_gate(instant_s)
        effective_salience = max(instant_s, recurrent_s)

        # 3. Route based on salience threshold
        if effective_salience >= self.salience_threshold:
            return RoutingResult(
                tier="DEEP_CLOUD",
                engine_name="Cloud_Gemini_Deep",
                salience_score=effective_salience,
                recurrent_gate_state=recurrent_s,
                reason=f"High cognitive salience ({effective_salience:.2f} >= {self.salience_threshold:.2f})",
            )
        else:
            return RoutingResult(
                tier="FAST_LOCAL",
                engine_name="Local_NPU_Arc",
                salience_score=effective_salience,
                recurrent_gate_state=recurrent_s,
                reason=f"Sub-threshold salience ({effective_salience:.2f} < {self.salience_threshold:.2f})",
            )
