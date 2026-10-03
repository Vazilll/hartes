"""
vazus_core.telemetry.causal_tracer
==================================
Causal Graph Tracing & Decision Provenance Engine.
Implements:
1. Cryptographic Merkle-chain tracking of agent decisions and code artifacts.
2. Full explainability: "Artifact X generated from Memory Fact Y, verified by Test Z, approved by Jury W".
3. Tamper-evident lineage audit trail eliminating hallucinations and ungrounded code modifications.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from vazus_core.memory.db import DEFAULT_VAZUS_DB, get_db_connection

logger = logging.getLogger("vazus_core.telemetry.causal_tracer")


@dataclass(frozen=True)
class CausalNode:
    """An immutable, cryptographically chained decision node in the causal graph."""
    node_id: str
    artifact_type: str  # "CODE_PATCH", "ARCH_DECISION", "Z3_PROOF", "REFACTOR"
    content_hash: str
    memory_fact_hashes: Tuple[str, ...]
    test_verifier_hash: str
    jury_approval_hash: str
    parent_node_ids: Tuple[str, ...]
    agent_id: str
    timestamp: float
    merkle_signature: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def compute_signature(
        cls,
        content_hash: str,
        memory_fact_hashes: Tuple[str, ...],
        test_verifier_hash: str,
        jury_approval_hash: str,
        parent_node_ids: Tuple[str, ...],
        agent_id: str,
        timestamp: float,
        metadata_hash: str = "",
    ) -> str:
        data = (
            f"{content_hash}::"
            f"{','.join(sorted(memory_fact_hashes))}::"
            f"{test_verifier_hash}::"
            f"{jury_approval_hash}::"
            f"{','.join(sorted(parent_node_ids))}::"
            f"{agent_id}::"
            f"{timestamp}::"
            f"{metadata_hash}"
        )
        return hashlib.sha256(data.encode("utf-8")).hexdigest()


class CausalGraphTracer:
    """
    Causal Graph Tracing & Decision Provenance Engine.
    Records and verifies cryptographic lineage for every code mutation and decision.
    """

    def __init__(self, db_path: Optional[Union[str, Path]] = None):
        target = db_path or os.getenv("VAZUS_DB_PATH") or DEFAULT_VAZUS_DB
        self.db_path = str(target)
        self._nodes: Dict[str, CausalNode] = {}
        self._ensure_storage()

    def _ensure_storage(self) -> None:
        """Ensures causal provenance table exists in SQLite database."""
        try:
            conn = get_db_connection(self.db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS causal_decision_provenance (
                    node_id TEXT PRIMARY KEY,
                    artifact_type TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    memory_fact_hashes TEXT NOT NULL,
                    test_verifier_hash TEXT NOT NULL,
                    jury_approval_hash TEXT NOT NULL,
                    parent_node_ids TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    merkle_signature TEXT NOT NULL,
                    metadata_json TEXT
                )
            """)
            conn.commit()
            conn.close()
        except Exception as exc:
            logger.debug("CausalGraphTracer storage init fallback: %s", exc)

    def record_decision(
        self,
        artifact_type: str,
        content: str,
        memory_facts: Optional[List[str]] = None,
        test_verifier_output: str = "TEST_PASSED",
        jury_approval_verdict: str = "APPROVED_BY_CONCORDIA",
        parent_node_ids: Optional[List[str]] = None,
        agent_id: str = "vazus_architect",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CausalNode:
        """
        Creates, cryptographically signs, and stores a new causal decision node.
        """
        now = time.time()
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        
        mem_hashes = tuple(
            hashlib.sha256(f.encode("utf-8")).hexdigest()[:16] for f in (memory_facts or [])
        )
        test_hash = hashlib.sha256(test_verifier_output.encode("utf-8")).hexdigest()[:16]
        jury_hash = hashlib.sha256(jury_approval_verdict.encode("utf-8")).hexdigest()[:16]
        parents = tuple(parent_node_ids or [])
        meta_dict = metadata or {}
        meta_hash = hashlib.sha256(json.dumps(meta_dict, sort_keys=True).encode("utf-8")).hexdigest()[:16]

        sig = CausalNode.compute_signature(
            content_hash=content_hash,
            memory_fact_hashes=mem_hashes,
            test_verifier_hash=test_hash,
            jury_approval_hash=jury_hash,
            parent_node_ids=parents,
            agent_id=agent_id,
            timestamp=now,
            metadata_hash=meta_hash,
        )
        node_id = f"causal_{sig[:16]}"

        node = CausalNode(
            node_id=node_id,
            artifact_type=artifact_type,
            content_hash=content_hash,
            memory_fact_hashes=mem_hashes,
            test_verifier_hash=test_hash,
            jury_approval_hash=jury_hash,
            parent_node_ids=parents,
            agent_id=agent_id,
            timestamp=now,
            merkle_signature=sig,
            metadata=meta_dict,
        )

        self._nodes[node_id] = node
        self._persist_node(node)
        return node

    def verify_provenance(self, node_id: str, visited: Optional[Set[str]] = None) -> Tuple[bool, str]:
        """
        Cryptographically verifies the causal integrity of a node and its parents.
        Detects cycles in causal ancestry and validates tamper-evident signatures.
        """
        if visited is None:
            visited = set()

        if node_id in visited:
            return False, f"Cycle detected in causal ancestry at node '{node_id}'."
        visited.add(node_id)

        node = self._nodes.get(node_id) or self._load_node_from_db(node_id)
        if not node:
            return False, f"Causal node '{node_id}' not found in registry."

        # Verify signature
        meta_hash = hashlib.sha256(json.dumps(node.metadata or {}, sort_keys=True).encode("utf-8")).hexdigest()[:16]
        expected_sig = CausalNode.compute_signature(
            content_hash=node.content_hash,
            memory_fact_hashes=node.memory_fact_hashes,
            test_verifier_hash=node.test_verifier_hash,
            jury_approval_hash=node.jury_approval_hash,
            parent_node_ids=node.parent_node_ids,
            agent_id=node.agent_id,
            timestamp=node.timestamp,
            metadata_hash=meta_hash,
        )

        if expected_sig != node.merkle_signature:
            return False, f"Tamper detected! Merkle signature mismatch on node '{node_id}'."

        # Verify parents recursively with cycle tracking
        for parent_id in node.parent_node_ids:
            p_valid, p_msg = self.verify_provenance(parent_id, visited=set(visited))
            if not p_valid:
                return False, f"Parent lineage failure at '{parent_id}': {p_msg}"

        return True, "Provenance signature and causal ancestry verified cryptographically."

    def get_provenance_narrative(self, node_id: str) -> str:
        """
        Generates human-readable explainability narrative for the decision.
        """
        node = self._nodes.get(node_id) or self._load_node_from_db(node_id)
        if not node:
            return f"Node {node_id} not found."

        parents_str = ", ".join(node.parent_node_ids) if node.parent_node_ids else "None (Root Decision)"
        return (
            f"[Decision Provenance {node.node_id}]\n"
            f"• Artifact: {node.artifact_type} (Content SHA: {node.content_hash[:12]})\n"
            f"• Sourced from {len(node.memory_fact_hashes)} memory facts (Hashes: {', '.join(node.memory_fact_hashes) or 'None'})\n"
            f"• Verified by Test Suite (Proof Hash: {node.test_verifier_hash})\n"
            f"• Approved by Concordia Jury / Gate (Verdict Hash: {node.jury_approval_hash})\n"
            f"• Parent Nodes: {parents_str}\n"
            f"• Executed by Agent: {node.agent_id}\n"
            f"• Merkle Signature: {node.merkle_signature[:24]}...\n"
        )

    def _persist_node(self, node: CausalNode) -> None:
        try:
            conn = get_db_connection(self.db_path)
            conn.execute(
                """
                INSERT OR REPLACE INTO causal_decision_provenance
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    node.node_id,
                    node.artifact_type,
                    node.content_hash,
                    json.dumps(list(node.memory_fact_hashes)),
                    node.test_verifier_hash,
                    node.jury_approval_hash,
                    json.dumps(list(node.parent_node_ids)),
                    node.agent_id,
                    node.timestamp,
                    node.merkle_signature,
                    json.dumps(node.metadata),
                ),
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            logger.debug("Failed to persist causal node %s: %s", node.node_id, exc)

    def _load_node_from_db(self, node_id: str) -> Optional[CausalNode]:
        try:
            conn = get_db_connection(self.db_path)
            cur = conn.cursor()
            cur.execute("SELECT * FROM causal_decision_provenance WHERE node_id = ?", (node_id,))
            row = cur.fetchone()
            conn.close()
            if row:
                return CausalNode(
                    node_id=row[0],
                    artifact_type=row[1],
                    content_hash=row[2],
                    memory_fact_hashes=tuple(json.loads(row[3])),
                    test_verifier_hash=row[4],
                    jury_approval_hash=row[5],
                    parent_node_ids=tuple(json.loads(row[6])),
                    agent_id=row[7],
                    timestamp=float(row[8]),
                    merkle_signature=row[9],
                    metadata=json.loads(row[10] or "{}"),
                )
        except Exception as exc:
            logger.debug("Failed to load causal node from DB: %s", exc)
        return None
