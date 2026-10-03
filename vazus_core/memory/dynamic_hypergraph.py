"""
vazus_core.memory.dynamic_hypergraph
====================================
Cognitive Dynamic Hypergraph with Ebbinghaus Decay & Two-Tier Memory Consolidation.
Implements:
1. Dynamic Hypergraph with n-ary relations (HyperEdge connecting multi-source to multi-target).
2. Hebbian Link Reinforcement (co-active & verified nodes gain synaptic strength).
3. Bounded Ebbinghaus Forgetting Curves with Stability Scaling (Memory Decay).
4. Two-Tier Consolidation (Hippocampus short-term episodic buffer -> Neocortex long-term semantic abstraction).
5. Cold-Storage Archival for decayed hypotheses to prevent lost-in-the-middle context noise.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from vazus_core.memory.db import DEFAULT_VAZUS_DB, get_db_connection
from vazus_core.memory.decay_policy import (
    DECAY_THRESHOLD,
    DEFAULT_BASE_STABILITY,
    MAX_STABILITY,
)

logger = logging.getLogger("vazus_core.memory.dynamic_hypergraph")


@dataclass
class HyperNode:
    """A concept or fact node in the cognitive dynamic hypergraph."""
    node_id: str
    content: str
    category: str = "semantic_fact"
    salience: float = 1.0  # Activation weight in [0.0, 1.0]
    stability: float = DEFAULT_BASE_STABILITY
    access_count: int = 1
    last_accessed: float = field(default_factory=time.time)
    created_at: float = field(default_factory=time.time)
    status: str = "active"  # "active", "decayed", "archived"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def compute_current_salience(self, now: Optional[float] = None) -> float:
        """Computes current salience via bounded Ebbinghaus forgetting curve."""
        t_now = now or time.time()
        delta_t = max(0.0, t_now - self.last_accessed)
        if self.stability <= 0 or math.isnan(self.stability) or math.isinf(self.stability):
            return 0.0
        try:
            decayed = self.salience * math.exp(-delta_t / self.stability)
            if math.isnan(decayed) or math.isinf(decayed):
                return 0.0
            return max(0.0, min(1.0, decayed))
        except (OverflowError, ZeroDivisionError):
            return 0.0


@dataclass
class HyperEdge:
    """An n-ary directed hyper-edge linking sources to targets."""
    edge_id: str
    sources: List[str]
    targets: List[str]
    relation: str
    weight: float = 0.5
    stability: float = DEFAULT_BASE_STABILITY
    hits: int = 1
    last_accessed: float = field(default_factory=time.time)
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def compute_current_weight(self, now: Optional[float] = None) -> float:
        """Computes current edge weight via bounded decay curve."""
        t_now = now or time.time()
        delta_t = max(0.0, t_now - self.last_accessed)
        if self.stability <= 0 or math.isnan(self.stability) or math.isinf(self.stability):
            return 0.0
        try:
            decayed = self.weight * math.exp(-delta_t / self.stability)
            if math.isnan(decayed) or math.isinf(decayed):
                return 0.0
            return max(0.0, min(1.0, decayed))
        except (OverflowError, ZeroDivisionError):
            return 0.0


@dataclass
class ConsolidationReport:
    """Summary metrics of episodic memory consolidation and compaction."""
    episodes_processed: int = 0
    abstractions_formed: int = 0
    nodes_reinforced: int = 0
    nodes_decayed: int = 0
    nodes_archived: int = 0
    edges_pruned: int = 0
    duration_ms: float = 0.0


class CognitiveDynamicHypergraph:
    """
    Cognitive Dynamic Hypergraph with Hebbian reinforcement, continuous decay,
    and two-tier (hippocampal episodic -> neocortical semantic) consolidation.
    """

    def __init__(self, db_path: Optional[Union[str, Path]] = None):
        target = db_path or os.getenv("VAZUS_DB_PATH") or DEFAULT_VAZUS_DB
        self.db_path = str(target)
        self.nodes: Dict[str, HyperNode] = {}
        self.edges: Dict[str, HyperEdge] = {}
        self._episodic_buffer: List[Dict[str, Any]] = []
        self._ensure_storage()

    def _ensure_storage(self) -> None:
        """Ensures SQLite persistence tables for hypernodes, hyperedges, and cold storage."""
        try:
            conn = get_db_connection(self.db_path)
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS cognitive_hyper_nodes (
                    node_id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    category TEXT NOT NULL,
                    salience REAL NOT NULL,
                    stability REAL NOT NULL,
                    access_count INTEGER NOT NULL,
                    last_accessed REAL NOT NULL,
                    created_at REAL NOT NULL,
                    status TEXT NOT NULL,
                    metadata_json TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS cognitive_hyper_edges (
                    edge_id TEXT PRIMARY KEY,
                    sources_json TEXT NOT NULL,
                    targets_json TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    weight REAL NOT NULL,
                    stability REAL NOT NULL,
                    hits INTEGER NOT NULL,
                    last_accessed REAL NOT NULL,
                    created_at REAL NOT NULL,
                    metadata_json TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS cognitive_cold_storage (
                    node_id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    category TEXT NOT NULL,
                    final_salience REAL NOT NULL,
                    archived_at REAL NOT NULL,
                    metadata_json TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS episodic_buffer_events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    raw_trace TEXT NOT NULL,
                    task_context TEXT,
                    created_at REAL NOT NULL
                )
            """)
            conn.commit()
            conn.close()
            self._load_active_graph()
        except Exception as exc:
            logger.warning("DynamicHypergraph storage init fallback: %s", exc)

    def _load_active_graph(self) -> None:
        """Loads non-archived nodes and edges from SQLite into in-memory cache."""
        try:
            conn = get_db_connection(self.db_path)
            cur = conn.cursor()
            cur.execute("""
                SELECT node_id, content, category, salience, stability,
                       access_count, last_accessed, created_at, status, metadata_json
                FROM cognitive_hyper_nodes
                WHERE status != 'archived'
            """)
            for row in cur.fetchall():
                meta = json.loads(row[9] or "{}") if row[9] else {}
                node = HyperNode(
                    node_id=row[0],
                    content=row[1],
                    category=row[2],
                    salience=float(row[3]),
                    stability=float(row[4]),
                    access_count=int(row[5]),
                    last_accessed=float(row[6]),
                    created_at=float(row[7]),
                    status=row[8],
                    metadata=meta,
                )
                self.nodes[node.node_id] = node

            cur.execute("""
                SELECT edge_id, sources_json, targets_json, relation, weight,
                       stability, hits, last_accessed, created_at, metadata_json
                FROM cognitive_hyper_edges
            """)
            for row in cur.fetchall():
                edge = HyperEdge(
                    edge_id=row[0],
                    sources=json.loads(row[1] or "[]"),
                    targets=json.loads(row[2] or "[]"),
                    relation=row[3],
                    weight=float(row[4]),
                    stability=float(row[5]),
                    hits=int(row[6]),
                    last_accessed=float(row[7]),
                    created_at=float(row[8]),
                    metadata=json.loads(row[9] or "{}") if row[9] else {},
                )
                self.edges[edge.edge_id] = edge
            conn.close()
        except Exception as exc:
            logger.debug("Active graph load from DB fallback: %s", exc)

    def add_node(
        self,
        node_id: str,
        content: str,
        category: str = "semantic_fact",
        salience: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> HyperNode:
        """Inserts or updates an active node in the hypergraph."""
        now = time.time()
        node = HyperNode(
            node_id=node_id,
            content=content,
            category=category,
            salience=min(1.0, max(0.05, salience)),
            stability=DEFAULT_BASE_STABILITY,
            access_count=1,
            last_accessed=now,
            created_at=now,
            status="active",
            metadata=metadata or {},
        )
        self.nodes[node_id] = node
        self._persist_node(node)
        return node

    def add_hyper_edge(
        self,
        sources: List[str],
        targets: List[str],
        relation: str,
        weight: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> HyperEdge:
        """Constructs an n-ary hyperedge connecting a group of sources to targets."""
        edge_id = hashlib.sha256(
            f"{','.join(sorted(sources))}::{relation}::{','.join(sorted(targets))}".encode("utf-8")
        ).hexdigest()[:16]

        edge = HyperEdge(
            edge_id=edge_id,
            sources=sources,
            targets=targets,
            relation=relation,
            weight=min(1.0, max(0.01, weight)),
            stability=DEFAULT_BASE_STABILITY,
            hits=1,
            last_accessed=time.time(),
            created_at=time.time(),
            metadata=metadata or {},
        )
        self.edges[edge_id] = edge
        self._persist_edge(edge)
        return edge

    def reinforce(
        self,
        node_ids: List[str],
        success_confidence: float = 1.0,
        learning_rate: float = 0.15,
    ) -> None:
        """
        Hebbian Reinforcement: Nodes co-active in verified successful executions
        increase their salience and expand their stability half-life.
        If success_confidence <= 0.0, applies penalty decay to unverified hypotheses.
        """
        now = time.time()
        if success_confidence <= 0.0:
            for nid in node_ids:
                node = self.nodes.get(nid)
                if node:
                    node.access_count += 1
                    node.last_accessed = now
                    node.salience = max(0.05, node.salience - learning_rate * 0.5)
                    self._persist_node(node)
            return

        for nid in node_ids:
            node = self.nodes.get(nid)
            if node:
                node.access_count += 1
                node.last_accessed = now
                # Hebbian rule: delta_w = lr * (1 - w) * confidence
                delta = learning_rate * (1.0 - node.salience) * min(1.0, max(0.0, success_confidence))
                node.salience = min(1.0, node.salience + delta)
                # Expand stability exponentially capped at MAX_STABILITY
                node.stability = min(
                    MAX_STABILITY,
                    DEFAULT_BASE_STABILITY * math.pow(1.0 + 0.15 * node.access_count, 0.75),
                )
                node.status = "active"
                self._persist_node(node)

        # Strengthen co-retrieved edges
        if len(node_ids) >= 2:
            for edge in self.edges.values():
                matched_sources = set(edge.sources).intersection(node_ids)
                matched_targets = set(edge.targets).intersection(node_ids)
                if matched_sources or matched_targets:
                    edge.hits += 1
                    edge.last_accessed = now
                    edge.weight = min(1.0, edge.weight + (learning_rate * (1.0 - edge.weight) * min(1.0, success_confidence)))
                    self._persist_edge(edge)

    def record_episodic_event(self, event_type: str, raw_trace: str, task_context: str = "") -> str:
        """Appends raw sensory/execution event to short-term episodic buffer (Hippocampus)."""
        event_id = hashlib.sha256(f"{event_type}:{time.time()}:{raw_trace[:40]}".encode()).hexdigest()[:12]
        event = {
            "event_id": event_id,
            "event_type": event_type,
            "raw_trace": raw_trace,
            "task_context": task_context,
            "created_at": time.time(),
        }
        self._episodic_buffer.append(event)
        try:
            conn = get_db_connection(self.db_path)
            conn.execute(
                "INSERT OR REPLACE INTO episodic_buffer_events VALUES (?, ?, ?, ?, ?)",
                (event_id, event_type, raw_trace, task_context, event["created_at"]),
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            logger.debug("Episodic buffer write failed: %s", exc)
        return event_id

    def consolidate_memory(self, decay_threshold: float = DECAY_THRESHOLD) -> ConsolidationReport:
        """
        Two-Tier Compaction Worker:
        1. Compacts raw short-term episodic events into synthesized long-term semantic lessons.
        2. Applies Ebbinghaus decay across all active hypernodes.
        3. Moves stale/hypothetical nodes below decay_threshold to cold storage.
        4. Prunes dangling or decayed hyperedges.
        """
        start_t = time.perf_counter()
        report = ConsolidationReport()
        now = time.time()

        # Step 1: Compact Hippocampal Episodes into Neocortical Abstractions
        episodes_to_process = list(self._episodic_buffer)
        self._episodic_buffer.clear()
        report.episodes_processed = len(episodes_to_process)

        if episodes_to_process:
            # Aggregate recurring failure or success patterns
            trace_groups: Dict[str, List[Dict[str, Any]]] = {}
            for ep in episodes_to_process:
                key = ep.get("event_type", "generic")
                trace_groups.setdefault(key, []).append(ep)

            for ev_type, group in trace_groups.items():
                if len(group) >= 1:
                    summary_content = (
                        f"Consolidated abstraction for {ev_type} ({len(group)} instances). "
                        f"Sample context: {group[0].get('task_context', '')[:100]}"
                    )
                    abs_id = f"abs_{ev_type}_{int(now)}"
                    self.add_node(
                        node_id=abs_id,
                        content=summary_content,
                        category="consolidated_abstraction",
                        salience=0.9,
                        metadata={"source_episodes_count": len(group)},
                    )
                    report.abstractions_formed += 1

        # Step 2: Apply Ebbinghaus Decay & Cold Storage Eviction
        active_ids = list(self.nodes.keys())
        for nid in active_ids:
            node = self.nodes[nid]
            current_salience = node.compute_current_salience(now)
            node.salience = current_salience

            if current_salience < decay_threshold:
                # Archive to cold storage
                node.status = "archived"
                self._archive_node_to_cold_storage(node)
                del self.nodes[nid]
                report.nodes_archived += 1
            elif current_salience < 0.4:
                node.status = "decayed"
                self._persist_node(node)
                report.nodes_decayed += 1
            else:
                self._persist_node(node)
                report.nodes_reinforced += 1

        # Step 3: Edge Decay & Dangling Edge Pruning
        active_edge_ids = list(self.edges.keys())
        edges_to_delete: List[str] = []
        for eid in active_edge_ids:
            edge = self.edges[eid]
            edge.weight = edge.compute_current_weight(now)
            sources_exist = all(s in self.nodes for s in edge.sources)
            targets_exist = all(t in self.nodes for t in edge.targets)
            if not sources_exist or not targets_exist or edge.weight < 0.05:
                edges_to_delete.append(eid)
                del self.edges[eid]
                report.edges_pruned += 1
            else:
                self._persist_edge(edge)

        if edges_to_delete:
            try:
                conn = get_db_connection(self.db_path)
                placeholders = ",".join("?" for _ in edges_to_delete)
                conn.execute(f"DELETE FROM cognitive_hyper_edges WHERE edge_id IN ({placeholders})", edges_to_delete)
                conn.commit()
                conn.close()
            except Exception as exc:
                logger.debug("Failed to delete pruned edges from DB: %s", exc)

        report.duration_ms = (time.perf_counter() - start_t) * 1000.0
        logger.info(
            "🧠 [HyperGraph Consolidation] Processed %d episodes, formed %d abstractions, archived %d decayed nodes, pruned %d edges in %.2fms",
            report.episodes_processed,
            report.abstractions_formed,
            report.nodes_archived,
            report.edges_pruned,
            report.duration_ms,
        )
        return report

    def search_active_context(self, query: str, top_k: int = 5) -> List[HyperNode]:
        """Returns the most salient active nodes matching the query, filtering out decayed/archived noise."""
        scored: List[Tuple[float, HyperNode]] = []
        tokens = set(query.lower().split())

        for node in self.nodes.values():
            if node.status == "archived":
                continue
            cur_salience = node.compute_current_salience()
            if cur_salience < DECAY_THRESHOLD:
                continue

            node_tokens = set(node.content.lower().split())
            overlap = len(tokens.intersection(node_tokens))
            score = (overlap + 0.1) * cur_salience
            scored.append((score, node))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored[:top_k]]

    def _persist_node(self, node: HyperNode) -> None:
        try:
            conn = get_db_connection(self.db_path)
            conn.execute(
                """
                INSERT OR REPLACE INTO cognitive_hyper_nodes
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    node.node_id,
                    node.content,
                    node.category,
                    node.salience,
                    node.stability,
                    node.access_count,
                    node.last_accessed,
                    node.created_at,
                    node.status,
                    json.dumps(node.metadata),
                ),
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            logger.debug("Failed to persist hypernode %s: %s", node.node_id, exc)

    def _persist_edge(self, edge: HyperEdge) -> None:
        try:
            conn = get_db_connection(self.db_path)
            conn.execute(
                """
                INSERT OR REPLACE INTO cognitive_hyper_edges
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    edge.edge_id,
                    json.dumps(edge.sources),
                    json.dumps(edge.targets),
                    edge.relation,
                    edge.weight,
                    edge.stability,
                    edge.hits,
                    edge.last_accessed,
                    edge.created_at,
                    json.dumps(edge.metadata),
                ),
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            logger.debug("Failed to persist hyperedge %s: %s", edge.edge_id, exc)

    def _archive_node_to_cold_storage(self, node: HyperNode) -> None:
        try:
            conn = get_db_connection(self.db_path)
            conn.execute(
                """
                INSERT OR REPLACE INTO cognitive_cold_storage
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    node.node_id,
                    node.content,
                    node.category,
                    node.salience,
                    time.time(),
                    json.dumps(node.metadata),
                ),
            )
            conn.execute("DELETE FROM cognitive_hyper_nodes WHERE node_id = ?", (node.node_id,))
            conn.commit()
            conn.close()
        except Exception as exc:
            logger.debug("Cold storage archival failed for %s: %s", node.node_id, exc)
