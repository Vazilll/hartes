"""
vazus_core.mem0_memory_engine — mem0-Inspired Persistent Memory & Entity Extraction Engine.
Provides automatic entity, fact, and preference extraction, deduplication, and 768D vector search
inside vazus.db for Vazus SuperGraph OS v5.0.
"""

import os
import re
import time
import json
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional

import sys
sys.path.insert(0, "C:/vazus")

from vazus_core.memory.db import get_db_connection
from vazus_core.memory.embeddings import get_embedding_manager

DB_PATH = r"C:\vazus\services\memory\vazus.db"


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
    """

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._ensure_table()
        self.emb_mgr = get_embedding_manager()

    def _ensure_table(self):
        conn = get_db_connection(self.db_path)
        conn.execute(self.TABLE_SQL)
        # Safe bi-temporal column migrations for existing databases
        try:
            conn.execute("ALTER TABLE mem0_facts ADD COLUMN status TEXT DEFAULT 'ACTIVE';")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE mem0_facts ADD COLUMN valid_from REAL;")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE mem0_facts ADD COLUMN valid_until REAL;")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE mem0_facts ADD COLUMN superseded_by TEXT;")
        except Exception:
            pass
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
                except Exception:
                    pass

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

    def search_facts(self, query: str, top_k: int = 5, rrf_k: int = 60) -> List[Dict[str, Any]]:
        """
        Searches active facts using Hybrid Reciprocal Rank Fusion (Dense 768D + Lexical Matching).
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

        q_vec = self.emb_mgr.get_embedding(query)
        q_tokens = set(re.findall(r"\w+", query.lower()))

        dense_scored = []
        lexical_scored = []

        for r in rows:
            fid, cat, ent, text, emb_str = r[0], r[1], r[2], r[3], r[4]
            emb = json.loads(emb_str) if emb_str else []
            sim = self.emb_mgr.compute_similarity(q_vec, emb)
            dense_scored.append((fid, cat, ent, text, sim))

            # Lexical overlap
            text_tokens = set(re.findall(r"\w+", text.lower()))
            overlap = len(q_tokens & text_tokens) / max(1, len(q_tokens))
            lexical_scored.append((fid, cat, ent, text, overlap))

        dense_scored.sort(key=lambda x: x[4], reverse=True)
        lexical_scored.sort(key=lambda x: x[4], reverse=True)

        # Reciprocal Rank Fusion (RRF)
        rrf_map: Dict[str, float] = {}
        meta_map = {}

        for rank, item in enumerate(dense_scored, 1):
            fid = item[0]
            rrf_map[fid] = rrf_map.get(fid, 0.0) + (1.0 / (rrf_k + rank))
            meta_map[fid] = item

        for rank, item in enumerate(lexical_scored, 1):
            fid = item[0]
            rrf_map[fid] = rrf_map.get(fid, 0.0) + (1.0 / (rrf_k + rank))
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


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    mem0 = Mem0Engine()
    res = mem0.add_fact("User prefers Hermes-style non-blocking subagent delegation", category="user_preference")
    print(f"[+] Mem0 Fact Result: {res}")
    facts = mem0.search_facts("subagent delegation preference")
    print(f"[+] Search Facts Result: {facts}")
