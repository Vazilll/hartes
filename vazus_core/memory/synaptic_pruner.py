"""
vazus_core.memory.synaptic_pruner
=================================
Biological Synaptic Pruning & Memory Consolidation Engine.
Implements Ebbinghaus Forgetting Curves with Stability Scaling,
Hebbian Co-Retrieval Edge Reinforcement, and 3-Tier SQLite Pruning.
"""

from __future__ import annotations

import json
import logging
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple, Union

from vazus_core.analysis.kg_schema import ensure_kg_schema
from vazus_core.memory.db import DEFAULT_VAZUS_DB, get_db_connection
from vazus_core.memory.decay_policy import (
    BASE_STABILITY,
    MAX_STABILITY,
)

logger = logging.getLogger("vazus_core.memory.synaptic_pruner")


@dataclass
class PruningMetrics:
    initial_edges: int = 0
    pruned_edges: int = 0
    updated_edges: int = 0
    initial_nodes: int = 0
    pruned_nodes: int = 0
    compacted_vectors: int = 0
    duration_sec: float = 0.0


class SynapticPruner:
    """
    Biological Synaptic Pruning and Hebbian Reinforcement Engine.
    Operates on kg_edges, kg_nodes, and j_space_vectors in vazus.db.
    """

    def __init__(
        self,
        db_path: Optional[Union[str, Path]] = None,
        edge_prune_threshold: float = 0.05,
        alpha_stability: float = 0.15,
        beta_stability: float = 0.70,
    ) -> None:
        self.db_path = str(db_path or DEFAULT_VAZUS_DB)
        self.edge_prune_threshold = edge_prune_threshold
        self.alpha = alpha_stability
        self.beta = beta_stability

    def reinforce_hebbian_link(
        self,
        node_a: str,
        node_b: str,
        cosine_sim: float = 0.5,
        relation: str = "hebbian_co_active",
        learning_rate: float = 0.10,
    ) -> float:
        """
        Hebbian Learning Rule: nodes co-retrieved during successful tasks strengthen edge.
        dw = eta * (1 - w) * max(0.1, cosine_sim)
        Stability is scaled using bounded DHP-style formula capped at MAX_STABILITY.
        """
        if node_a == node_b:
            return 1.0

        src, dst = sorted([node_a, node_b])
        now = time.time()
        conn = get_db_connection(self.db_path)
        ensure_kg_schema(conn.cursor())

        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT strength, properties FROM kg_edges WHERE source_id=? AND target_id=? AND relation=?",
                (src, dst, relation),
            )
            row = cur.fetchone()

            if row:
                old_w = float(row[0])
                props = json.loads(row[1] or "{}")
                hits = props.get("hits", 1) + 1
                # Bounded non-exploding DHP stability curve
                s_new = min(MAX_STABILITY, BASE_STABILITY * math.pow(1.0 + self.alpha * hits, self.beta))

                delta_w = learning_rate * (1.0 - old_w) * max(0.1, cosine_sim)
                new_w = min(1.0, old_w + delta_w)
                props.update({"last_accessed": now, "hits": hits, "stability": round(s_new, 2)})
            else:
                new_w = min(1.0, 0.35 + 0.25 * max(0.0, cosine_sim))
                props = {
                    "created_at": now,
                    "last_accessed": now,
                    "hits": 1,
                    "stability": BASE_STABILITY,
                }

            cur.execute(
                """
                INSERT INTO kg_edges (source_id, target_id, relation, strength, properties)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(source_id, target_id, relation) DO UPDATE SET
                    strength = excluded.strength,
                    properties = excluded.properties
                """,
                (src, dst, relation, round(new_w, 4), json.dumps(props)),
            )
            conn.commit()
            return new_w
        finally:
            conn.close()

    def apply_ebbinghaus_decay_and_prune(self) -> PruningMetrics:
        """
        Pass 1: Computes Ebbinghaus decay on all edges. Prunes edges below threshold.
                Advances last_accessed to prevent compounding decay error.
        Pass 2: Removes disconnected orphan nodes (degree == 0, excluding immutable nodes).
        Pass 3: WAL Checkpoint.
        """
        start_t = time.perf_counter()
        metrics = PruningMetrics()
        now = time.time()

        conn = get_db_connection(self.db_path)
        cur = conn.cursor()
        ensure_kg_schema(cur)

        try:
            # 1. Edge Decay and Pruning
            cur.execute("SELECT source_id, target_id, relation, strength, properties FROM kg_edges")
            edges = cur.fetchall()
            metrics.initial_edges = len(edges)

            edges_to_delete: List[Tuple[str, str, str]] = []
            edges_to_update: List[Tuple[float, str, str, str, str]] = []

            for src, dst, rel, strength, props_raw in edges:
                props = json.loads(props_raw or "{}")
                last_accessed = float(props.get("last_accessed", props.get("created_at", now)))
                stability = float(props.get("stability", 86400.0 * 7.0))  # Default 7 days stability
                delta_t = max(0.0, now - last_accessed)

                # Ebbinghaus: R(t) = exp(- delta_t / stability)
                decay_factor = math.exp(- delta_t / max(1.0, stability))
                decayed_strength = float(strength) * decay_factor

                if decayed_strength < self.edge_prune_threshold:
                    edges_to_delete.append((src, dst, rel))
                else:
                    # Advance last_accessed to now to avoid compounding decay across consecutive runs
                    props["last_accessed"] = now
                    edges_to_update.append((round(decayed_strength, 4), json.dumps(props), src, dst, rel))

            if edges_to_update:
                cur.executemany(
                    "UPDATE kg_edges SET strength=?, properties=? WHERE source_id=? AND target_id=? AND relation=?",
                    edges_to_update,
                )
            metrics.updated_edges = len(edges_to_update)

            if edges_to_delete:
                cur.executemany(
                    "DELETE FROM kg_edges WHERE source_id=? AND target_id=? AND relation=?",
                    edges_to_delete,
                )
            metrics.pruned_edges = len(edges_to_delete)

            # 2. Dendritic Orphan Node Pruning
            cur.execute("SELECT COUNT(*) FROM kg_nodes")
            metrics.initial_nodes = cur.fetchone()[0]

            cur.execute("""
                DELETE FROM kg_nodes
                WHERE id NOT IN (SELECT source_id FROM kg_edges UNION SELECT target_id FROM kg_edges)
                  AND COALESCE(domain, '') NOT IN ('memory_wiki', 'organic_memory', 'health', 'kgb_analytics', 'core', 'academic')
                  AND COALESCE(json_extract(properties, '$.immutable'), 0) NOT IN (1, 'true', '1')
                  AND (properties NOT LIKE '%"immutable": true%' OR properties IS NULL)
                  AND (properties NOT LIKE '%"immutable": 1%' OR properties IS NULL)
            """)
            metrics.pruned_nodes = cur.rowcount

            conn.commit()

            # 3. WAL Checkpoint
            try:
                cur.execute("PRAGMA wal_checkpoint(PASSIVE)")
            except Exception as e:
                logger.debug("WAL checkpoint non-fatal: %s", e)

        finally:
            conn.close()

        metrics.duration_sec = time.perf_counter() - start_t
        logger.info("🌿 [SynapticPruner] Finished in %.3fs: %s", metrics.duration_sec, metrics)
        return metrics
