"""
Google Agent Memory Bank for Vazus SuperGraph OS.
Provides multi-tiered memory governance (Working Memory, Untrusted Observation,
Verified Fact, ADR), automated session transcript consolidation, and SQLite persistence.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MemoryTier(str, Enum):
    WORKING_MEMORY = "working_memory"
    UNTRUSTED_OBSERVATION = "untrusted_observation"
    VERIFIED_FACT = "verified_fact"
    ARCHITECTURAL_DECISION = "architectural_decision"


class MemoryEntry(BaseModel):
    entry_id: str = Field(default_factory=lambda: "mem_" + uuid.uuid4().hex[:10])
    tier: MemoryTier = MemoryTier.UNTRUSTED_OBSERVATION
    category: str = "general"
    content: str
    session_id: str = "default"
    timestamp: float = Field(default_factory=time.time)
    confidence: float = 0.5
    verified_by: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentMemoryBank:
    """
    Persistent multi-tiered Agent Memory Bank.
    """

    def __init__(self, db_path: Optional[str] = None):
        env_db = os.environ.get("VAZUS_DB_PATH")
        self.db_path = db_path or env_db or r"C:\vazus\services\memory\vazus.db"
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS agent_memory_bank (
                    entry_id TEXT PRIMARY KEY,
                    tier TEXT NOT NULL,
                    category TEXT NOT NULL,
                    content TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    confidence REAL NOT NULL,
                    verified_by TEXT,
                    metadata TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_mem_tier ON agent_memory_bank(tier);
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_mem_session ON agent_memory_bank(session_id);
            """)
            conn.commit()

    def record_observation(
        self,
        content: str,
        category: str = "general",
        session_id: str = "default",
        confidence: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MemoryEntry:
        """Quarantines a new observation as UNTRUSTED_OBSERVATION."""
        entry = MemoryEntry(
            tier=MemoryTier.UNTRUSTED_OBSERVATION,
            category=category,
            content=content,
            session_id=session_id,
            confidence=confidence,
            metadata=metadata or {},
        )
        self._insert_entry(entry)
        return entry

    def promote_to_verified(self, entry_id: str, verifier: str = "concordia_jury_66%") -> bool:
        """Promotes an observation to VERIFIED_FACT after validation."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE agent_memory_bank
                SET tier = ?, verified_by = ?, confidence = 1.0
                WHERE entry_id = ?
                """,
                (MemoryTier.VERIFIED_FACT.value, verifier, entry_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def record_adr(
        self,
        title: str,
        decision: str,
        rationale: str,
        session_id: str = "default",
    ) -> MemoryEntry:
        """Records a durable Architectural Decision (ADR)."""
        content = f"ADR [{title}]: {decision} | Rationale: {rationale}"
        entry = MemoryEntry(
            tier=MemoryTier.ARCHITECTURAL_DECISION,
            category="adr",
            content=content,
            session_id=session_id,
            confidence=1.0,
            verified_by="system_architect",
            metadata={"title": title, "decision": decision, "rationale": rationale},
        )
        self._insert_entry(entry)
        return entry

    def query_memory(
        self,
        query: str,
        tier: Optional[MemoryTier] = None,
        category: Optional[str] = None,
        limit: int = 10,
    ) -> List[MemoryEntry]:
        """Queries entries matching text and optional tier filters."""
        sql = "SELECT entry_id, tier, category, content, session_id, timestamp, confidence, verified_by, metadata FROM agent_memory_bank WHERE 1=1"
        params: List[Any] = []

        if tier:
            sql += " AND tier = ?"
            params.append(tier.value)

        if category:
            sql += " AND category = ?"
            params.append(category)

        if query.strip():
            sql += " AND content LIKE ?"
            params.append(f"%{query.strip()}%")

        sql += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        results = []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            for row in cursor.fetchall():
                results.append(
                    MemoryEntry(
                        entry_id=row[0],
                        tier=MemoryTier(row[1]),
                        category=row[2],
                        content=row[3],
                        session_id=row[4],
                        timestamp=row[5],
                        confidence=row[6],
                        verified_by=row[7],
                        metadata=json.loads(row[8]),
                    )
                )
        return results

    def consolidate_session(self, session_id: str, messages: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Asynchronously consolidates conversation messages into durable memory entries.
        """
        extracted_observations = 0
        for msg in messages:
            content = str(msg.get("content", ""))
            role = str(msg.get("role", "user"))
            if not content:
                continue

            # Identify facts or preferences
            if role in ["user", "USER_INPUT"]:
                if any(
                    k in content.lower()
                    for k in [
                        "всегда",
                        "предпочитаю",
                        "правило",
                        "запрещено",
                        "никогда",
                        "настройка",
                        "rule",
                        "preference",
                    ]
                ):
                    self.record_observation(
                        content=content,
                        category="user_preference",
                        session_id=session_id,
                        confidence=0.8,
                    )
                    extracted_observations += 1
            elif role in ["assistant", "PLANNER_RESPONSE"]:
                if "verified" in content.lower() or "passed" in content.lower():
                    self.record_observation(
                        content=content[:300],
                        category="system_verification",
                        session_id=session_id,
                        confidence=0.7,
                    )
                    extracted_observations += 1

        return {
            "session_id": session_id,
            "observations_extracted": extracted_observations,
        }

    def get_stats(self) -> Dict[str, int]:
        """Returns counts across all memory tiers."""
        stats = {t.value: 0 for t in MemoryTier}
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT tier, COUNT(*) FROM agent_memory_bank GROUP BY tier")
            for tier_val, count in cursor.fetchall():
                stats[tier_val] = count
        return stats

    def _insert_entry(self, entry: MemoryEntry) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO agent_memory_bank
                (entry_id, tier, category, content, session_id, timestamp, confidence, verified_by, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.entry_id,
                    entry.tier.value,
                    entry.category,
                    entry.content,
                    entry.session_id,
                    entry.timestamp,
                    entry.confidence,
                    entry.verified_by,
                    json.dumps(entry.metadata),
                ),
            )
            conn.commit()
