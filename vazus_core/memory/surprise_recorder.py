"""
vazus_core.memory.surprise_recorder
===================================
Surprise-Driven Memory Recording (Titans Neural Architecture).
Filters trivial, predictable events from long-term memory consolidation:
only events whose actual outcome deviates from prediction (surprise > threshold)
are committed to the cognitive dynamic hypergraph and episodic buffer.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional, Tuple

import numpy as np

logger = logging.getLogger("vazus_core.memory.surprise_recorder")


class SurpriseRecorder:
    """
    Titans-style Surprise Filter for Cognitive Memory.
    Calculates surprise metric: S = 1.0 - cosine_similarity(y_pred, y_actual).
    Gating condition: S > threshold -> record to long-term memory.
    """

    def __init__(
        self,
        threshold: float = 0.70,
        hypergraph: Optional[Any] = None,
        episodic_store: Optional[Any] = None,
    ):
        self.threshold = float(threshold)
        self.hypergraph = hypergraph
        self.episodic_store = episodic_store
        self._total_events: int = 0
        self._surprising_events: int = 0

    @staticmethod
    def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
        """Calculates normalized cosine similarity bounded in [-1.0, 1.0]."""
        a = np.asarray(vec_a, dtype=np.float32).flatten()
        b = np.asarray(vec_b, dtype=np.float32).flatten()

        norm_a = float(np.linalg.norm(a))
        norm_b = float(np.linalg.norm(b))

        if norm_a < 1e-7 or norm_b < 1e-7:
            return 0.0

        dot = float(np.dot(a, b))
        sim = dot / (norm_a * norm_b)
        return float(max(-1.0, min(1.0, sim)))

    def compute_surprise(
        self,
        predicted_embedding: np.ndarray,
        actual_embedding: np.ndarray,
    ) -> float:
        """
        Computes the prediction error / surprise score in [0.0, 2.0],
        normalized to [0.0, 1.0] for standard forward comparisons.
        """
        sim = self.cosine_similarity(predicted_embedding, actual_embedding)
        # Bounded between 0.0 (identical) and 1.0 (orthogonal or opposite)
        surprise = max(0.0, min(1.0, (1.0 - sim) / 1.0 if sim >= 0 else 1.0))
        return round(surprise, 4)

    def should_record(
        self,
        event: Dict[str, Any],
        predicted_embedding: np.ndarray,
        actual_embedding: np.ndarray,
    ) -> Tuple[bool, float]:
        """
        Evaluates whether an event carries sufficient information-theoretic
        surprise to warrant long-term episodic or hypergraph retention.
        """
        self._total_events += 1
        surprise = self.compute_surprise(predicted_embedding, actual_embedding)
        is_surprising = surprise >= self.threshold

        if is_surprising:
            self._surprising_events += 1

        return is_surprising, surprise

    def record_if_surprising(
        self,
        event: Dict[str, Any],
        predicted_embedding: np.ndarray,
        actual_embedding: np.ndarray,
    ) -> Dict[str, Any]:
        """
        Conditionally writes event to long-term memory stores if surprise >= threshold.
        Returns a telemetry outcome dictionary.
        """
        should_rec, surprise = self.should_record(event, predicted_embedding, actual_embedding)
        outcome = {
            "recorded": should_rec,
            "surprise_score": surprise,
            "threshold": self.threshold,
            "timestamp": time.time(),
            "event_id": event.get("id") or event.get("event_id"),
        }

        if not should_rec:
            logger.debug(
                "Event %s pruned: surprise %.3f < threshold %.3f",
                outcome["event_id"],
                surprise,
                self.threshold,
            )
            return outcome

        # Commit to Dynamic Hypergraph if injected
        if self.hypergraph is not None:
            try:
                node_id = str(outcome["event_id"] or f"surprise_{int(time.time()*1000)}")
                content = str(event.get("content") or event.get("summary") or event)
                salience = min(1.0, max(0.5, surprise))
                if hasattr(self.hypergraph, "add_node"):
                    self.hypergraph.add_node(
                        node_id=node_id,
                        content=content,
                        category="surprising_episodic",
                        salience=salience,
                    )
            except Exception as e:
                logger.warning("Failed to record surprising event in hypergraph: %s", e)

        # Commit to Episodic Store if injected
        if self.episodic_store is not None:
            try:
                if hasattr(self.episodic_store, "write"):
                    self.episodic_store.write(event)
                elif hasattr(self.episodic_store, "insert"):
                    self.episodic_store.insert(event)
            except Exception as e:
                logger.warning("Failed to record surprising event in episodic store: %s", e)

        return outcome

    @property
    def statistics(self) -> Dict[str, Any]:
        """Returns filter retention and pass-through telemetry."""
        ratio = (self._surprising_events / self._total_events) if self._total_events > 0 else 0.0
        return {
            "total_events_evaluated": self._total_events,
            "surprising_events_recorded": self._surprising_events,
            "retention_ratio": round(ratio, 4),
            "threshold": self.threshold,
        }
