"""
vazus_core.global_j_workspace
==============================
Global Workspace Theory (GWT) & J-Space (Jacobian Latent Space) Architecture for Vazus OS.
Inspired by Anthropic's Global Workspace Discovery (2026) & Baars/Dehaene Cognitive Models.

Provides a centralized, bounded latent broadcast hub where multiple autonomous subagents
(Planner, Coder, Verifier, Researcher) read and write compressed conceptual representations
without quadratic conversational token bloat.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class JSpaceConcept:
    """Represents a privileged active concept in the Global J-Workspace."""

    concept_id: str
    semantic_label: str
    activation_strength: float  # 0.0 to 1.0
    embedding_vector: Optional[List[float]] = None  # 768-dim vector
    source_subagent: str = "orchestrator"
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


class GlobalJWorkspace:
    """
    Central Cognitive Broadcast Hub for Multi-Agent Orchestration.
    Enforces a strictly bounded capacity (K-sparse workspace) to prevent cognitive overload.
    """

    def __init__(self, capacity: int = 16, embedding_dim: int = 768, db_path: Optional[str] = None) -> None:
        self.capacity = capacity
        self.embedding_dim = embedding_dim
        env_db = os.environ.get("VAZUS_DB_PATH")
        self.db_path = db_path or env_db or r"C:\vazus\services\memory\vazus.db"
        self.active_concepts: Dict[str, JSpaceConcept] = {}
        self.broadcast_history: List[Dict[str, Any]] = []

    def broadcast_concept(
        self,
        concept_id: str,
        semantic_label: str,
        activation_strength: float,
        source_subagent: str,
        embedding_vector: Optional[List[float]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> JSpaceConcept:
        """
        Broadcasts a concept into the privileged global workspace.
        If workspace exceeds capacity, lowest-activation non-essential concepts are evicted.
        """
        if embedding_vector and len(embedding_vector) != self.embedding_dim:
            raise ValueError(
                f"Embedding dimension mismatch: expected {self.embedding_dim}, got {len(embedding_vector)}"
            )

        concept = JSpaceConcept(
            concept_id=concept_id,
            semantic_label=semantic_label,
            activation_strength=min(1.0, max(0.0, activation_strength)),
            embedding_vector=embedding_vector,
            source_subagent=source_subagent,
            metadata=metadata or {},
        )

        self.active_concepts[concept_id] = concept

        # Enforce bounded workspace capacity (competitive attention bottleneck)
        if len(self.active_concepts) > self.capacity:
            sorted_by_strength = sorted(self.active_concepts.items(), key=lambda item: item[1].activation_strength)
            evict_key, _ = sorted_by_strength[0]
            del self.active_concepts[evict_key]

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
        Applies exponential salience decay to active concepts in RAM.
        Prunes concepts below min_threshold to bound memory footprint.
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

    def modulate_concept(self, concept_id: str, new_strength: float) -> bool:
        """Modulates the activation strength of a concept (top-down cognitive control)."""
        if concept_id in self.active_concepts:
            self.active_concepts[concept_id].activation_strength = min(1.0, max(0.0, new_strength))
            if new_strength <= 0.0:
                del self.active_concepts[concept_id]
            return True
        return False

    def swap_concept(self, target_id: str, replacement: JSpaceConcept) -> bool:
        """
        Causal J-Space intervention: atomically replaces a concept in the workspace,
        causing all observing subagents to pivot their downstream reasoning.
        """
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
        """
        Returns a compact human-readable string of the top active concepts for
        zero-cost prompt injection into LLM context windows.
        """
        if not self.active_concepts:
            return "[J-Space: empty — no active concepts]"
        top = sorted(self.active_concepts.values(), key=lambda x: x.activation_strength, reverse=True)[:max_concepts]
        lines = ["[J-Space Active Concepts]"]
        for c in top:
            lines.append(f"  • {c.semantic_label} (strength={c.activation_strength:.2f}, src={c.source_subagent})")
        return "\n".join(lines)

    def _ensure_db_table(self) -> None:
        if not self.db_path:
            return
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS j_workspace_state (
                    concept_id TEXT PRIMARY KEY,
                    semantic_label TEXT NOT NULL,
                    activation_strength REAL NOT NULL,
                    source_subagent TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    metadata_json TEXT,
                    embedding_blob BLOB
                );
            """)
            # Migration: add embedding_blob column if missing from old schema
            try:
                conn.execute("SELECT embedding_blob FROM j_workspace_state LIMIT 1")
            except sqlite3.OperationalError:
                conn.execute("ALTER TABLE j_workspace_state ADD COLUMN embedding_blob BLOB")
            conn.commit()
        finally:
            conn.close()

    def save_to_db(self) -> int:
        """Saves current active concepts to SQLite via UPSERT (no destructive DELETE)."""
        self._ensure_db_table()
        if not self.db_path:
            return 0
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        try:
            current_ids = set()
            for c in self.active_concepts.values():
                import struct

                emb_blob = None
                if c.embedding_vector:
                    emb_blob = struct.pack(f"{len(c.embedding_vector)}f", *c.embedding_vector)
                conn.execute(
                    """
                    INSERT OR REPLACE INTO j_workspace_state
                    (concept_id, semantic_label, activation_strength, source_subagent, timestamp, metadata_json, embedding_blob)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        c.concept_id,
                        c.semantic_label,
                        c.activation_strength,
                        c.source_subagent,
                        c.timestamp,
                        json.dumps(c.metadata or {}),
                        emb_blob,
                    ),
                )
                current_ids.add(c.concept_id)
            # Only remove concepts that are no longer active (evicted from K-sparse workspace)
            if current_ids:
                placeholders = ",".join("?" * len(current_ids))
                conn.execute(
                    f"DELETE FROM j_workspace_state WHERE concept_id NOT IN ({placeholders})", list(current_ids)
                )
            conn.commit()
        finally:
            conn.close()
        return len(self.active_concepts)

    def load_from_db(self) -> int:
        """Restores active concepts from SQLite database, including embedding vectors."""
        self._ensure_db_table()
        if not self.db_path:
            return 0
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT concept_id, semantic_label, activation_strength, source_subagent, timestamp, metadata_json, embedding_blob FROM j_workspace_state"
            )
            rows = cursor.fetchall()
            loaded = 0
            for r in rows:
                meta = {}
                try:
                    if r["metadata_json"]:
                        meta = json.loads(r["metadata_json"])
                except Exception:
                    pass
                emb_vec = None
                if r["embedding_blob"]:
                    import struct

                    blob = r["embedding_blob"]
                    count = len(blob) // 4
                    emb_vec = list(struct.unpack(f"{count}f", blob))
                concept = JSpaceConcept(
                    concept_id=r["concept_id"],
                    semantic_label=r["semantic_label"],
                    activation_strength=r["activation_strength"],
                    source_subagent=r["source_subagent"],
                    timestamp=r["timestamp"],
                    metadata=meta,
                    embedding_vector=emb_vec,
                )
                self.active_concepts[concept.concept_id] = concept
                loaded += 1
            return loaded
        finally:
            conn.close()
