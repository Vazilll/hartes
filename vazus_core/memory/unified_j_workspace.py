"""
vazus_core.memory.unified_j_workspace
=====================================
Unified J-Space (Jacobian Latent Space) Cognitive Broadcast Hub.

Consolidates:
1. In-memory K-sparse bounded global workspace (GWT bottleneck, K <= 16)
2. Persistent SQLite vector index (768D L2-normalized float32 BLOBs)
3. Zero-overhead top-K cosine similarity search via NumPy
4. Backward-compatible API with GlobalJWorkspace and JSpaceVectorIndex
"""

from __future__ import annotations

import os
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np

DEFAULT_DB_PATH = Path("C:/vazus/services/memory/vazus.db")


@dataclass
class JSpaceConcept:
    """Represents an active concept in the Unified J-Workspace."""

    concept_id: str
    semantic_label: str
    activation_strength: float  # 0.0 to 1.0
    embedding_vector: Optional[List[float]] = None  # 768-dim vector
    source_subagent: str = "orchestrator"
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


class UnifiedJWorkspace:
    """
    Unified Facade for J-Space Cognitive Architecture in Vazus OS.
    Seamlessly merges fast active memory and persistent SQLite vector storage.
    """

    def __init__(self, capacity: int = 16, embedding_dim: int = 768, db_path: Optional[str] = None) -> None:
        self.capacity = capacity
        self.embedding_dim = embedding_dim

        env_db = os.environ.get("VAZUS_DB_PATH")
        raw_path = db_path or env_db or str(DEFAULT_DB_PATH)
        self._is_memory = str(raw_path) == ":memory:"
        self.db_path = Path(raw_path) if not self._is_memory else Path(":memory:")

        self.active_concepts: Dict[str, JSpaceConcept] = {}
        self.broadcast_history: List[Dict[str, Any]] = []

        self._shared_conn: Optional[sqlite3.Connection] = None
        if self._is_memory:
            self._shared_conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._shared_conn.row_factory = sqlite3.Row

        self._ensure_table()

    def _get_connection(self) -> sqlite3.Connection:
        if self._is_memory:
            return self._shared_conn  # type: ignore
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _release_connection(self, conn: sqlite3.Connection) -> None:
        if not self._is_memory:
            conn.close()

    def _ensure_table(self) -> None:
        conn = self._get_connection()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS j_space_vectors (
                    id TEXT PRIMARY KEY,
                    concept_id TEXT NOT NULL,
                    semantic_label TEXT NOT NULL,
                    salience REAL NOT NULL,
                    vector BLOB NOT NULL,
                    source TEXT NOT NULL,
                    created_at REAL NOT NULL
                );
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_unified_j_space_concept_id 
                ON j_space_vectors(concept_id);
            """)
            conn.commit()
        finally:
            self._release_connection(conn)

    def broadcast_concept(
        self,
        concept_id: str,
        semantic_label: str,
        activation_strength: float,
        source_subagent: str = "orchestrator",
        embedding_vector: Optional[List[float]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> JSpaceConcept:
        """
        Broadcasts a concept into the privileged global workspace.
        Maintains bounded capacity and automatically persists vector embeddings.
        """
        if embedding_vector and len(embedding_vector) != self.embedding_dim:
            raise ValueError(
                f"Embedding dimension mismatch: expected {self.embedding_dim}, got {len(embedding_vector)}"
            )

        clamped_strength = min(1.0, max(0.0, float(activation_strength)))

        concept = JSpaceConcept(
            concept_id=concept_id,
            semantic_label=semantic_label,
            activation_strength=clamped_strength,
            embedding_vector=embedding_vector,
            source_subagent=source_subagent,
            metadata=metadata or {},
        )

        self.active_concepts[concept_id] = concept

        # Enforce bounded capacity (K-sparse attention bottleneck)
        if len(self.active_concepts) > self.capacity:
            sorted_by_strength = sorted(self.active_concepts.items(), key=lambda item: item[1].activation_strength)
            evict_key, _ = sorted_by_strength[0]
            del self.active_concepts[evict_key]

        # Automatically persist vector if provided
        if embedding_vector:
            self._persist_vector(
                concept_id=concept_id,
                semantic_label=semantic_label,
                salience=clamped_strength,
                vector=embedding_vector,
                source=source_subagent,
            )

        self.broadcast_history.append(
            {
                "action": "broadcast",
                "concept_id": concept_id,
                "label": semantic_label,
                "source": source_subagent,
                "timestamp": time.time(),
            }
        )
        if len(self.broadcast_history) > 100:
            self.broadcast_history = self.broadcast_history[-100:]

        return concept

    def decay_concepts(self, decay_rate: float = 0.1, min_threshold: float = 0.05) -> int:
        """
        Applies exponential salience decay to all active concepts in RAM.
        Concepts falling below min_threshold are pruned to prevent unbounded memory growth.
        Returns the count of pruned concepts.
        """
        pruned_count = 0
        to_delete = []
        for cid, concept in self.active_concepts.items():
            concept.activation_strength *= 1.0 - decay_rate
            if concept.activation_strength < min_threshold:
                to_delete.append(cid)
        for cid in to_delete:
            del self.active_concepts[cid]
            pruned_count += 1
        return pruned_count

    def _persist_vector(
        self, concept_id: str, semantic_label: str, salience: float, vector: List[float], source: str
    ) -> None:
        """Persists L2-normalized float32 vector into SQLite table."""
        vec_arr = np.array(vector, dtype=np.float32)
        norm = np.linalg.norm(vec_arr)
        if norm > 1e-9:
            vec_arr = vec_arr / norm
        blob = vec_arr.tobytes()

        record_id = str(uuid.uuid4())
        conn = self._get_connection()
        try:
            conn.execute(
                """
                INSERT INTO j_space_vectors (id, concept_id, semantic_label, salience, vector, source, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (record_id, concept_id, semantic_label, salience, blob, source, time.time()),
            )
            conn.commit()
        finally:
            self._release_connection(conn)

    def count_stored_vectors(self) -> int:
        """Returns total number of stored vectors in SQLite."""
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT COUNT(*) FROM j_space_vectors")
            row = cursor.fetchone()
            return int(row[0]) if row else 0
        finally:
            self._release_connection(conn)

    def count(self) -> int:
        """Alias for count_stored_vectors."""
        return self.count_stored_vectors()

    def search_similar(
        self,
        query_vector: Union[List[float], np.ndarray],
        top_k: int = 5,
        min_salience: float = 0.0,
        min_similarity: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """Searches top-K similar concepts using cosine similarity."""
        q_arr = np.array(query_vector, dtype=np.float32)
        q_norm = np.linalg.norm(q_arr)
        if q_norm > 1e-9:
            q_arr = q_arr / q_norm

        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT id, concept_id, semantic_label, salience, vector, source, created_at FROM j_space_vectors"
            )
            rows = cursor.fetchall()
            if not rows:
                return []

            results = []
            for r in rows:
                if r["salience"] < min_salience:
                    continue
                v_arr = np.frombuffer(r["vector"], dtype=np.float32)
                sim = float(np.dot(q_arr, v_arr))
                if sim < min_similarity:
                    continue
                results.append(
                    {
                        "id": r["id"],
                        "concept_id": r["concept_id"],
                        "semantic_label": r["semantic_label"],
                        "salience": r["salience"],
                        "similarity": sim,
                        "source": r["source"],
                        "created_at": r["created_at"],
                    }
                )

            results.sort(key=lambda x: x["similarity"], reverse=True)
            return results[:top_k]
        finally:
            self._release_connection(conn)

    def modulate_concept(self, concept_id: str, new_strength: float) -> bool:
        """Modulates the activation strength of a concept (cognitive control)."""
        if concept_id in self.active_concepts:
            clamped = min(1.0, max(0.0, float(new_strength)))
            self.active_concepts[concept_id].activation_strength = clamped
            if clamped <= 0.0:
                del self.active_concepts[concept_id]
            return True
        return False

    def decay_activations(self, decay_rate: float = 0.05) -> None:
        """Applies temporal decay to all active concepts."""
        to_delete = []
        for cid, concept in self.active_concepts.items():
            concept.activation_strength = max(0.0, concept.activation_strength - decay_rate)
            if concept.activation_strength <= 0.0:
                to_delete.append(cid)
        for cid in to_delete:
            del self.active_concepts[cid]

    def get_concept(self, concept_id: str) -> Optional[JSpaceConcept]:
        return self.active_concepts.get(concept_id)

    def get_active_concepts(self) -> Dict[str, JSpaceConcept]:
        return dict(self.active_concepts)

    def swap_concept(self, target_id: str, replacement: JSpaceConcept) -> bool:
        """Causal J-Space intervention: atomically replaces an active concept."""
        if target_id in self.active_concepts:
            del self.active_concepts[target_id]
            self.active_concepts[replacement.concept_id] = replacement
            return True
        return False

    def export_workspace_state(self) -> Dict[str, Any]:
        """Exports the compact O(1) representation of the global workspace for prompt injection."""
        return {
            "active_count": len(self.active_concepts),
            "workspace_concepts": [
                {
                    "id": c.concept_id,
                    "label": c.semantic_label,
                    "strength": round(c.activation_strength, 3),
                    "source": c.source_subagent,
                }
                for c in sorted(self.active_concepts.values(), key=lambda x: x.activation_strength, reverse=True)
            ],
        }

    def get_broadcast_context(self, max_concepts: int = 5) -> str:
        """Returns a compact human-readable string of the top active concepts."""
        if not self.active_concepts:
            return "[J-Space: empty — no active concepts]"
        top = sorted(self.active_concepts.values(), key=lambda x: x.activation_strength, reverse=True)[:max_concepts]
        lines = ["[J-Space Active Concepts]"]
        for c in top:
            lines.append(f"  • {c.semantic_label} (strength={c.activation_strength:.2f}, src={c.source_subagent})")
        return "\n".join(lines)

    def export_summary(self) -> List[Dict[str, Any]]:
        """Exports active concepts ordered by activation strength."""
        sorted_concepts = sorted(self.active_concepts.values(), key=lambda c: c.activation_strength, reverse=True)
        return [
            {
                "concept_id": c.concept_id,
                "label": c.semantic_label,
                "strength": round(c.activation_strength, 3),
                "source": c.source_subagent,
                "metadata": c.metadata,
            }
            for c in sorted_concepts
        ]

    def broadcast(
        self,
        concept_id: str,
        label: Optional[str] = None,
        semantic_label: Optional[str] = None,
        strength: Optional[float] = None,
        activation_strength: Optional[float] = None,
        vector: Optional[Union[List[float], np.ndarray]] = None,
        embedding_vector: Optional[Union[List[float], np.ndarray]] = None,
        source: str = "orchestrator",
        source_subagent: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> JSpaceConcept:
        """Flexible broadcast alias compatible with both GlobalJWorkspace and JSpaceVectorIndex conventions."""
        s_label = semantic_label or label or ""
        s_strength = (
            activation_strength if activation_strength is not None else (strength if strength is not None else 0.5)
        )
        raw_vec = embedding_vector if embedding_vector is not None else vector
        if raw_vec is not None and hasattr(raw_vec, "tolist"):
            vec_list = raw_vec.tolist()
        elif raw_vec is not None:
            vec_list = list(raw_vec)
        else:
            vec_list = None
        src = source_subagent or source
        return self.broadcast_concept(
            concept_id=concept_id,
            semantic_label=s_label,
            activation_strength=s_strength,
            source_subagent=src,
            embedding_vector=vec_list,
            metadata=metadata,
        )

    def clear(self) -> None:
        self.active_concepts.clear()
        self.broadcast_history.clear()
