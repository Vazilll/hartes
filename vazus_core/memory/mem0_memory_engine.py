"""
vazus_core.mem0_memory_engine — mem0-Inspired Persistent Memory & Entity Extraction Engine.
Provides automatic entity, fact, and preference extraction, deduplication, and 768D vector search
inside vazus.db for Vazus SuperGraph OS v5.0.
"""

import json
import logging
import os
import re
import sqlite3
import sys
import time
import numpy as np
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

from vazus_core.memory.db import get_db_connection
from vazus_core.memory.embeddings import get_embedding_manager

DB_PATH = os.environ.get("VAZUS_DB_PATH") or r"C:\vazus\services\memory\vazus.db"


class Mem0Engine:
    """
    mem0-inspired Persistent Memory & Fact Engine.
    Extracts facts, updates user preferences, deduplicates entries, and stores 768D vectors.
    """

    TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS mem0_facts (
        fact_id       TEXT PRIMARY KEY,
        category      TEXT,
        entity        TEXT,
        fact_text     TEXT,
        embedding_json TEXT,
        confidence    REAL DEFAULT 1.0,
        status        TEXT DEFAULT 'ACTIVE',
        valid_from    REAL,
        valid_until   REAL,
        superseded_by TEXT,
        created_at    REAL,
        updated_at    REAL
    );

    CREATE TABLE IF NOT EXISTS memory_facts_v2 (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        fact_text     TEXT    NOT NULL,
        category      TEXT    NOT NULL,
        status        TEXT    NOT NULL DEFAULT 'UNTRUSTED_OBSERVATION'
                      CHECK (status IN ('UNTRUSTED_OBSERVATION','CANDIDATE','VERIFIED_FACT','ARCHITECTURAL_DECISION','REJECTED','SUPERSEDED','EXPIRED')),
        confidence    REAL    NOT NULL DEFAULT 0.0,
        provenance    TEXT    NOT NULL,
        source_agent  TEXT    NOT NULL,
        content_hash  TEXT    NOT NULL UNIQUE,
        embedding_json TEXT,
        valid_from    REAL    NOT NULL,
        valid_until   REAL,
        superseded_by INTEGER REFERENCES memory_facts_v2(id),
        created_at    REAL    NOT NULL,
        updated_at    REAL    NOT NULL
    );

    CREATE TABLE IF NOT EXISTS memory_promotion_log (
        log_id        INTEGER PRIMARY KEY AUTOINCREMENT,
        fact_id       INTEGER NOT NULL,
        from_status   TEXT NOT NULL,
        to_status     TEXT NOT NULL,
        by_agent      TEXT NOT NULL,
        justification TEXT,
        promoted_at   REAL NOT NULL
    );
    """

    def __init__(self, db_path: Optional[str] = None):
        env_db = os.environ.get("VAZUS_DB_PATH")
        self.db_path = db_path or env_db or DB_PATH
        self._ensure_table()
        self.emb_mgr = get_embedding_manager()

    def _ensure_table(self):
        conn = get_db_connection(self.db_path)
        conn.executescript(self.TABLE_SQL)
        conn.commit()
        conn.close()

    def add_fact(self, fact_text: str, category: str = "user_preference", entity: str = "user") -> Dict[str, Any]:
        """
        Extracts, deduplicates, and adds a new fact/preference with bi-temporal lifecycle.
        Resolves contradictions by superseding outdated facts.
        """
        conn = get_db_connection(self.db_path)
        cur = conn.cursor()
        
        now = time.time()
        fact_id = f"fact_{int(now*1000)}"
        emb = self.emb_mgr.get_embedding(fact_text)
        emb_json = json.dumps(emb)

        # Check for existing active facts for this entity & category
        cur.execute(
            "SELECT fact_id, fact_text, embedding_json FROM mem0_facts WHERE entity = ? AND category = ? AND (status = 'ACTIVE' OR status IS NULL)",
            (entity, category)
        )
        existing = cur.fetchall()
        
        for row in existing:
            f_id, f_text, f_emb_json = row[0], row[1], row[2]
            if f_text.strip().lower() == fact_text.strip().lower():
                # Exact match -> update timestamp
                cur.execute("UPDATE mem0_facts SET updated_at = ?, valid_from = coalesce(valid_from, ?) WHERE fact_id = ?", (now, now, f_id))
                conn.commit()
                conn.close()
                return {"status": "UPDATED", "fact_id": f_id, "fact_text": fact_text}
            
            # Check for strong semantic overlap / contradiction resolution
            if f_emb_json:
                try:
                    f_emb = json.loads(f_emb_json)
                    sim = self.emb_mgr.compute_similarity(emb, f_emb)
                    if sim >= 0.88:
                        # High similarity but different phrasing -> supersede old fact
                        cur.execute(
                            "UPDATE mem0_facts SET status = 'SUPERSEDED', valid_until = ?, superseded_by = ? WHERE fact_id = ?",
                            (now, fact_id, f_id)
                        )
                except Exception as exc:
                    logger.debug("Failed computing semantic overlap for fact %s: %s", f_id, exc)

        cur.execute("""
            INSERT OR REPLACE INTO mem0_facts (
                fact_id, category, entity, fact_text, embedding_json, confidence,
                status, valid_from, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, 1.0, 'ACTIVE', ?, ?, ?)
        """, (fact_id, category, entity, fact_text, emb_json, now, now, now))
        conn.commit()
        conn.close()
        
        return {"status": "ADDED", "fact_id": fact_id, "fact_text": fact_text, "category": category}

    def _compute_adaptive_weights(self, query: str) -> tuple[float, float]:
        """Dynamically balances dense vs lexical RRF weights based on query signals."""
        has_code_signals = bool(re.search(r"[_./\\]|[a-z][A-Z]|\b(def|class|SELECT|FROM|PRAGMA|API)\b", query))
        has_quotes = '"' in query or "'" in query or '`' in query
        if has_code_signals or has_quotes:
            return 0.8, 1.4
        return 1.4, 0.7

    def search_facts(
        self,
        query: str,
        top_k: int = 5,
        rrf_k: int = 60,
        dense_weight: Optional[float] = None,
        lexical_weight: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Searches active facts using Adaptive Hybrid Reciprocal Rank Fusion (Dense 768D + Lexical Matching).
        Dynamically adjusts dense vs lexical weighting based on query signals.
        """
        conn = get_db_connection(self.db_path, read_only=True)
        cur = conn.cursor()
        cur.execute(
            "SELECT fact_id, category, entity, fact_text, embedding_json FROM mem0_facts WHERE status = 'ACTIVE' OR status IS NULL"
        )
        rows = cur.fetchall()
        conn.close()
        
        if not rows:
            return []

        auto_dense, auto_lex = self._compute_adaptive_weights(query)
        dense_w = dense_weight if dense_weight is not None else auto_dense
        lex_w = lexical_weight if lexical_weight is not None else auto_lex

        q_vec = np.array(self.emb_mgr.get_embedding(query), dtype=np.float32)
        q_norm = float(np.linalg.norm(q_vec))
        q_tokens = set(re.findall(r"\w+", query.lower()))

        dense_scored = []
        lexical_scored = []
        valid_rows = []
        vectors = []

        for r in rows:
            fid, cat, ent, text, emb_str = r[0], r[1], r[2], r[3], r[4]
            emb = None
            if emb_str:
                if isinstance(emb_str, (bytes, bytearray, memoryview)):
                    try:
                        emb = np.frombuffer(bytes(emb_str), dtype=np.float32)
                    except Exception:
                        emb = None
                elif isinstance(emb_str, str):
                    try:
                        emb = np.array(json.loads(emb_str), dtype=np.float32)
                    except Exception:
                        emb = None
            
            if emb is not None and len(emb) == len(q_vec):
                vectors.append(emb)
                valid_rows.append((fid, cat, ent, text))
            else:
                dense_scored.append((fid, cat, ent, text, 0.0))

            # Lexical overlap
            text_tokens = set(re.findall(r"\w+", text.lower()))
            overlap = len(q_tokens & text_tokens) / max(1, len(q_tokens))
            lexical_scored.append((fid, cat, ent, text, overlap))

        if vectors and q_norm > 0:
            mat = np.vstack(vectors)
            norms = np.linalg.norm(mat, axis=1)
            norms[norms == 0] = 1.0
            sims = np.dot(mat, q_vec) / (norms * q_norm)
            for i, sim_val in enumerate(sims):
                fid, cat, ent, text = valid_rows[i]
                dense_scored.append((fid, cat, ent, text, float(sim_val)))

        dense_scored.sort(key=lambda x: x[4], reverse=True)
        lexical_scored.sort(key=lambda x: x[4], reverse=True)

        # Adaptive Reciprocal Rank Fusion (RRF)
        rrf_map: Dict[str, float] = {}
        meta_map = {}

        for rank, item in enumerate(dense_scored, 1):
            fid = item[0]
            rrf_map[fid] = rrf_map.get(fid, 0.0) + (dense_w / (rrf_k + rank))
            meta_map[fid] = item

        for rank, item in enumerate(lexical_scored, 1):
            fid = item[0]
            rrf_map[fid] = rrf_map.get(fid, 0.0) + (lex_w / (rrf_k + rank))
            meta_map[fid] = item

        sorted_fids = sorted(rrf_map.items(), key=lambda x: x[1], reverse=True)
        results = []
        for fid, score in sorted_fids[:top_k]:
            item = meta_map[fid]
            results.append({
                "fact_id": fid,
                "category": item[1],
                "entity": item[2],
                "fact_text": item[3],
                "rrf_score": round(score, 5)
            })

        return results

    def record_observation_v2(
        self,
        fact_text: str,
        *,
        category: str = "observation",
        source_agent: str = "antigravity",
        provenance: str = "turn_context",
        status: str = "UNTRUSTED_OBSERVATION",
        confidence: float = 0.5
    ) -> Dict[str, Any]:
        """
        Records a new memory item into memory_facts_v2 in quarantine or candidate tier.
        Deduplicates by SHA-256 content hash.
        """
        import hashlib
        content_hash = hashlib.sha256(fact_text.strip().encode("utf-8")).hexdigest()
        now = time.time()
        emb = self.emb_mgr.get_embedding(fact_text)
        emb_json = json.dumps(emb)

        conn = get_db_connection(self.db_path)
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO memory_facts_v2 (
                    fact_text, category, status, confidence, provenance,
                    source_agent, content_hash, embedding_json, valid_from, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (fact_text, category, status, confidence, provenance, source_agent, content_hash, emb_json, now, now, now))
            row_id = cur.lastrowid
            conn.commit()
            conn.close()
            return {"status": "RECORDED", "id": row_id, "tier": status, "content_hash": content_hash}
        except sqlite3.IntegrityError:
            # Already exists by content hash -> update timestamp
            cur.execute("UPDATE memory_facts_v2 SET updated_at = ? WHERE content_hash = ?", (now, content_hash))
            conn.commit()
            conn.close()
            return {"status": "DEDUP_EXISTS", "content_hash": content_hash}

    def promote_fact_v2(
        self,
        fact_id: int,
        to_status: str = "VERIFIED_FACT",
        by_agent: str = "concordia_jury",
        justification: str = "Passed test suite and consensus verification"
    ) -> Dict[str, Any]:
        """
        Promotes a fact from UNTRUSTED_OBSERVATION / CANDIDATE to VERIFIED_FACT or ARCHITECTURAL_DECISION.
        Logs to memory_promotion_log audit table.
        """
        now = time.time()
        conn = get_db_connection(self.db_path)
        cur = conn.cursor()

        cur.execute("SELECT status FROM memory_facts_v2 WHERE id = ?", (fact_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            return {"status": "ERROR", "reason": f"Fact ID {fact_id} not found"}

        from_status = row[0]
        cur.execute(
            "UPDATE memory_facts_v2 SET status = ?, confidence = 1.0, updated_at = ? WHERE id = ?",
            (to_status, now, fact_id)
        )
        cur.execute("""
            INSERT INTO memory_promotion_log (fact_id, from_status, to_status, by_agent, justification, promoted_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (fact_id, from_status, to_status, by_agent, justification, now))

        conn.commit()
        conn.close()
        return {"status": "PROMOTED", "id": fact_id, "from": from_status, "to": to_status}

    def search_verified_facts_v2(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Searches ONLY verified facts and architectural decisions, ignoring untrusted observations.
        """
        conn = get_db_connection(self.db_path, read_only=True)
        cur = conn.cursor()
        cur.execute("""
            SELECT id, fact_text, category, status, confidence, provenance, source_agent, embedding_json
            FROM memory_facts_v2
            WHERE status IN ('VERIFIED_FACT', 'ARCHITECTURAL_DECISION')
        """)
        rows = cur.fetchall()
        conn.close()

        if not rows:
            return []

        q_vec = self.emb_mgr.get_embedding(query)
        scored = []
        for r in rows:
            f_id, text, cat, stat, conf, prov, agent, emb_str = r
            emb = json.loads(emb_str) if emb_str else []
            sim = self.emb_mgr.compute_similarity(q_vec, emb)
            scored.append({
                "id": f_id,
                "fact_text": text,
                "category": cat,
                "status": stat,
                "confidence": conf,
                "provenance": prov,
                "source_agent": agent,
                "similarity": round(sim, 4)
            })

        scored.sort(key=lambda x: x["similarity"], reverse=True)
        return scored[:top_k]


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    mem0 = Mem0Engine()
    res = mem0.add_fact("User prefers Hermes-style non-blocking subagent delegation", category="user_preference")
    print(f"[+] Mem0 Fact Result: {res}")
    facts = mem0.search_facts("subagent delegation preference")
    print(f"[+] Search Facts Result: {facts}")
