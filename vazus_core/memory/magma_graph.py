"""
vazus_core.memory.magma_graph — Multi-Agent Graph Memory Architecture (MAGMA 4-Graph).
Provides 4 distinct edge topologies (semantic, temporal, causal, entity),
Hebbian co-retrieval strengthening, exponential edge decay, and intent-aware traversal.
"""

import json
import logging
import math
import time
from typing import Any, Dict, List, Optional

from vazus_core.analysis.kg_schema import ensure_kg_schema
from vazus_core.memory.db import get_db_connection

logger = logging.getLogger("MAGMAGraph")


class MAGMAEdgeType:
    """MAGMA 4-Graph relation types."""

    ENTITY = "entity"  # Syntactic AST dependencies, structs, functions
    CAUSAL = "causal"  # Architectural rationales, decision lineage ("why")
    TEMPORAL = "temporal"  # Version chronology, mutation timestamps ("when")
    SEMANTIC = "semantic"  # 768-D embedding vector similarity ("similar")


class MAGMAGraphEngine:
    """
    Engine for managing dynamic, self-reinforcing Multi-Agent Graph Memory.
    Features:
    - 4-Graph edge typing.
    - Hebbian co-retrieval strengthening.
    - Exponential half-life decay.
    - Intent-aware graph navigation.
    """

    INTENT_EDGE_MAP = {
        "why": [MAGMAEdgeType.CAUSAL, MAGMAEdgeType.SEMANTIC],
        "rationale": [MAGMAEdgeType.CAUSAL, MAGMAEdgeType.SEMANTIC],
        "cause": [MAGMAEdgeType.CAUSAL],
        "when": [MAGMAEdgeType.TEMPORAL],
        "history": [MAGMAEdgeType.TEMPORAL, MAGMAEdgeType.ENTITY],
        "version": [MAGMAEdgeType.TEMPORAL],
        "depends": [MAGMAEdgeType.ENTITY, MAGMAEdgeType.SEMANTIC],
        "struct": [MAGMAEdgeType.ENTITY],
        "class": [MAGMAEdgeType.ENTITY],
        "similar": [MAGMAEdgeType.SEMANTIC, MAGMAEdgeType.ENTITY],
    }

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def _get_connection(self):
        conn = get_db_connection(self.db_path)
        cur = conn.cursor()
        ensure_kg_schema(cur)
        conn.commit()
        return conn

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        relation: str = MAGMAEdgeType.SEMANTIC,
        strength: float = 1.0,
        properties: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Adds or updates an edge in the MAGMA graph."""
        props_json = json.dumps(properties or {"created_at": time.time(), "last_accessed": time.time()})
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO kg_edges (source_id, target_id, relation, strength, properties)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(source_id, target_id, relation) DO UPDATE SET
                    strength = excluded.strength,
                    properties = excluded.properties
                """,
                (source_id, target_id, relation, float(strength), props_json),
            )
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error("Failed to add edge %s -> %s (%s): %s", source_id, target_id, relation, e)
            return False

    def reinforce_co_retrieval(
        self,
        node_a: str,
        node_b: str,
        boost: float = 0.05,
        relation: str = MAGMAEdgeType.SEMANTIC,
    ) -> float:
        """
        Hebbian learning rule: nodes retrieved together strengthen their connection weight.
        w_new = min(1.0, w_old + boost * (1.0 - w_old))
        """
        if node_a == node_b:
            return 1.0

        src, dst = sorted([node_a, node_b])
        now = time.time()

        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT strength, properties FROM kg_edges WHERE source_id=? AND target_id=? AND relation=?",
            (src, dst, relation),
        )
        row = cur.fetchone()

        if row:
            old_w = float(row[0])
            props = json.loads(row[1] or "{}")
            new_w = min(1.0, old_w + boost * (1.0 - old_w))
            props["last_accessed"] = now
            props["co_retrievals"] = props.get("co_retrievals", 0) + 1
        else:
            new_w = min(1.0, 0.5 + boost * 0.5)
            props = {"created_at": now, "last_accessed": now, "co_retrievals": 1}

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
        conn.close()
        return new_w

    def apply_exponential_decay(
        self,
        half_life_days: float = 30.0,
        min_threshold: float = 0.05,
    ) -> int:
        """
        Applies exponential time decay to edge weights based on last_accessed time.
        Prunes edges that drop below min_threshold.
        Returns the number of pruned edges.
        """
        now = time.time()
        decay_constant = math.log(2) / (half_life_days * 86400.0)
        pruned_count = 0

        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT source_id, target_id, relation, strength, properties FROM kg_edges")
        rows = cur.fetchall()

        for src, dst, rel, strength, props_str in rows:
            props = json.loads(props_str or "{}")
            last_access = props.get("last_accessed", props.get("created_at", now))
            delta_sec = max(0.0, now - last_access)

            decayed_strength = float(strength) * math.exp(-decay_constant * delta_sec)

            if decayed_strength < min_threshold:
                cur.execute("DELETE FROM kg_edges WHERE source_id=? AND target_id=? AND relation=?", (src, dst, rel))
                pruned_count += 1
            else:
                cur.execute(
                    "UPDATE kg_edges SET strength=? WHERE source_id=? AND target_id=? AND relation=?",
                    (round(decayed_strength, 4), src, dst, rel),
                )

        conn.commit()
        conn.close()
        return pruned_count

    def _get_target_relations(self, intent: str) -> List[str]:
        intent_lower = intent.lower().strip()
        for key, rels in self.INTENT_EDGE_MAP.items():
            if key in intent_lower:
                return rels
        return [
            MAGMAEdgeType.SEMANTIC,
            MAGMAEdgeType.ENTITY,
            MAGMAEdgeType.CAUSAL,
            MAGMAEdgeType.TEMPORAL,
        ]

    def intent_aware_traverse(
        self,
        start_node_id: str,
        intent: str = "general",
        max_depth: int = 2,
        min_strength: float = 0.1,
    ) -> List[Dict[str, Any]]:
        """
        Traverses the MAGMA graph prioritizing relations aligned with the user's intent.
        Executes a single Recursive CTE query eliminating N+1 roundtrips.
        """
        target_relations = self._get_target_relations(intent)
        conn = self._get_connection()
        cur = conn.cursor()

        # Single-query Recursive CTE with delimited cycle-prevention and per-edge relation tracking
        cte_query = """
        WITH RECURSIVE graph_traverse(curr_id, next_id, relation, strength, depth, visited_nodes, path_str) AS (
            SELECT
                source_id, target_id, relation, strength, 1,
                '|' || source_id || '|' || target_id || '|',
                source_id || '--[' || relation || ']-->' || target_id
            FROM kg_edges
            WHERE source_id = ? AND strength >= ?
            UNION ALL
            SELECT
                target_id, source_id, relation, strength, 1,
                '|' || target_id || '|' || source_id || '|',
                target_id || '--[' || relation || ']-->' || source_id
            FROM kg_edges
            WHERE target_id = ? AND strength >= ?

            UNION ALL

            SELECT
                e.source_id, e.target_id, e.relation, e.strength, gt.depth + 1,
                gt.visited_nodes || e.target_id || '|',
                gt.path_str || ';' || e.source_id || '--[' || e.relation || ']-->' || e.target_id
            FROM kg_edges e
            JOIN graph_traverse gt ON e.source_id = gt.next_id
            WHERE gt.depth < ?
              AND e.strength >= ?
              AND instr(gt.visited_nodes, '|' || e.target_id || '|') = 0
            UNION ALL
            SELECT
                e.target_id, e.source_id, e.relation, e.strength, gt.depth + 1,
                gt.visited_nodes || e.source_id || '|',
                gt.path_str || ';' || e.target_id || '--[' || e.relation || ']-->' || e.source_id
            FROM kg_edges e
            JOIN graph_traverse gt ON e.target_id = gt.next_id
            WHERE gt.depth < ?
              AND e.strength >= ?
              AND instr(gt.visited_nodes, '|' || e.source_id || '|') = 0
        )
        SELECT curr_id, next_id, relation, strength, depth, visited_nodes, path_str FROM graph_traverse;
        """

        try:
            cur.execute(cte_query, (start_node_id, min_strength, start_node_id, min_strength, max_depth, min_strength, max_depth, min_strength))
            rows = cur.fetchall()
        finally:
            conn.close()

        # Process CTE results, computing intent-weighted path scores
        node_best: Dict[str, Dict[str, Any]] = {}
        for curr_id, next_id, rel, strength, depth, visited_nodes, path_str in rows:
            rel_multiplier = 1.2 if rel in target_relations else 0.8
            accum_weight = float(strength) * rel_multiplier
            path_list = [seg.strip() for seg in path_str.split(";") if seg.strip()]

            if next_id not in node_best or accum_weight > node_best[next_id]["strength"]:
                node_best[next_id] = {
                    "node_id": next_id,
                    "depth": depth,
                    "strength": round(accum_weight, 4),
                    "path": path_list,
                }

        results = list(node_best.values())
        results.sort(key=lambda x: x["strength"], reverse=True)
        return results


# Global singleton instance
magma_graph_engine = MAGMAGraphEngine()

__all__ = [
    "MAGMAEdgeType",
    "MAGMAGraphEngine",
    "magma_graph_engine",
]
