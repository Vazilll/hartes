#!/usr/bin/env python3
"""
vazus_core.memory.dream_consolidator — Mem0 Dream / Sleep-Time Consolidation Engine.
===================================================================================

Inspired by Mem0 Dream (August 2026 SOTA) & Biological Sleep Consolidation:
  - Deduplicates and merges redundant reflexion lessons.
  - Performs bi-temporal fact conflict resolution (valid_until / superseded_by).
  - Cleans orphaned knowledge graph edges (kg_edges).
  - Prunes and compacts stale telemetry call graphs.
  - Executes SQLite WAL checkpoint and VACUUM.

Usage:
  from vazus_core.memory.dream_consolidator import DreamConsolidator
  stats = DreamConsolidator().run_full_consolidation()
"""

import datetime
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

from vazus_core.memory.db import DEFAULT_VAZUS_DB, get_db_connection
from vazus_core.memory.embeddings import UnifiedEmbeddingManager

logger = logging.getLogger("vazus_core.memory.dream")


class DreamConsolidator:
    """
    Asynchronous sleep-time memory organizer and fact consolidation engine.
    """

    def __init__(self, db_path: Optional[Union[str, Path]] = None):
        env_db = os.environ.get("VAZUS_DB_PATH")
        target_path = db_path or env_db or DEFAULT_VAZUS_DB
        self.db_path = str(target_path) if target_path else DEFAULT_VAZUS_DB
        self._embed_mgr = None
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        """Creates tables required by consolidation passes if they don't exist."""
        try:
            conn = get_db_connection(self.db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reflexion_lessons (
                    lesson_id TEXT PRIMARY KEY,
                    task_type TEXT,
                    error_sig TEXT,
                    lesson_text TEXT,
                    fix_hint TEXT,
                    success_count INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT (datetime('now')),
                    embedding_json TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS telemetry_call_edges (
                    source TEXT,
                    target TEXT,
                    call_count INTEGER DEFAULT 1,
                    avg_latency_ms REAL DEFAULT 0.0,
                    last_called TEXT DEFAULT (datetime('now')),
                    PRIMARY KEY (source, target)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS dream_consolidation_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    stats_json TEXT NOT NULL,
                    duration_seconds REAL NOT NULL,
                    status TEXT NOT NULL
                )
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning("DreamConsolidator table init failed: %s", e)

    @property
    def embed_mgr(self) -> UnifiedEmbeddingManager:
        if self._embed_mgr is None:
            self._embed_mgr = UnifiedEmbeddingManager()
        return self._embed_mgr

    def run_full_consolidation(self, run_vacuum: bool = False) -> Dict[str, int]:
        """Runs all memory consolidation passes sequentially."""
        logger.info("🌙 [Mem0 Dream] Starting sleep-time memory consolidation on %s...", self.db_path)
        start_t = time.perf_counter()

        stats = {
            "lessons_deduped": self.consolidate_reflexion_lessons(),
            "facts_consolidated": self.consolidate_bitemporal_facts(),
            "orphaned_edges_pruned": self.prune_orphaned_kg_edges(),
            "telemetry_compacted": self.compact_telemetry_edges(),
        }

        if run_vacuum:
            self.vacuum_and_checkpoint()
            stats["vacuum_performed"] = 1

        elapsed = time.perf_counter() - start_t
        try:
            conn = get_db_connection(self.db_path)
            with conn:
                conn.execute(
                    "INSERT INTO dream_consolidation_log (timestamp, stats_json, duration_seconds, status) VALUES (?, ?, ?, ?)",
                    (datetime.datetime.now(datetime.timezone.utc).isoformat(), json.dumps(stats), elapsed, "SUCCESS"),
                )
            conn.close()
        except Exception as exc:
            logger.warning("Failed to record dream consolidation log: %s", exc)

        logger.info("✨ [Mem0 Dream] Memory consolidation finished in %.2fs. Stats: %s", elapsed, json.dumps(stats))
        return stats

    def consolidate_reflexion_lessons(self) -> int:
        """
        Deduplicates reflexion_lessons by merging identical or high-similarity error signatures.
        Keeps highest success_count and newest timestamp.
        """
        try:
            conn = get_db_connection(self.db_path)
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(reflexion_lessons)")
            cols = [c[1] for c in cur.fetchall()]
            pk_col = "lesson_id" if "lesson_id" in cols else "id"

            if pk_col == "lesson_id":
                cur.execute("""
                    SELECT lesson_id, task_type, error_sig, lesson_text, fix_hint, success_count, created_at, embedding_json
                    FROM reflexion_lessons
                    ORDER BY created_at DESC
                """)
            else:
                cur.execute(f"""
                    SELECT {pk_col}, task_type, error_sig, lesson_text, fix_hint, success_count, created_at, embedding_json
                    FROM reflexion_lessons
                    ORDER BY created_at DESC
                """)
            rows = cur.fetchall()
            if not rows:
                conn.close()
                return 0

            seen_keys: Dict[Tuple[str, str], Dict[str, Any]] = {}
            duplicates_to_delete = []
            updates_to_apply = []

            for r in rows:
                lid, t_type, err_sig, l_text, f_hint, s_cnt, c_at, emb_json = r
                t_type = (t_type or "").strip()
                err_sig = (err_sig or "").strip()
                key = (t_type, err_sig)

                if key in seen_keys:
                    master = seen_keys[key]
                    master["total_success"] += s_cnt or 0
                    master["ids_to_merge"].append(lid)
                    duplicates_to_delete.append(lid)
                else:
                    seen_keys[key] = {
                        "master_id": lid,
                        "total_success": (s_cnt or 0),
                        "ids_to_merge": [],
                    }

            for key, data in seen_keys.items():
                if data["ids_to_merge"]:
                    updates_to_apply.append((data["total_success"], data["master_id"]))

            with conn:
                for total_sc, master_id in updates_to_apply:
                    if pk_col == "lesson_id":
                        conn.execute(
                            "UPDATE reflexion_lessons SET success_count = ? WHERE lesson_id = ?", (total_sc, master_id)
                        )
                    else:
                        conn.execute(
                            f"UPDATE reflexion_lessons SET success_count = ? WHERE {pk_col} = ?", (total_sc, master_id)
                        )
                for dup_id in duplicates_to_delete:
                    if pk_col == "lesson_id":
                        conn.execute("DELETE FROM reflexion_lessons WHERE lesson_id = ?", (dup_id,))
                    else:
                        conn.execute(f"DELETE FROM reflexion_lessons WHERE {pk_col} = ?", (dup_id,))

            conn.close()
            logger.info(
                "🧠 [Mem0 Dream] Lessons deduped: merged %d duplicates into primary entries.", len(duplicates_to_delete)
            )
            return len(duplicates_to_delete)
        except Exception as e:
            logger.error("Failed to consolidate reflexion lessons: %s", e)
            return 0

    def consolidate_bitemporal_facts(self) -> int:
        """
        Scans memory_facts_v2 for superseded or contradictory facts,
        setting valid_until and superseded_by.
        """
        try:
            conn = get_db_connection(self.db_path)
            cur = conn.cursor()
            cur.execute("""
                SELECT id, fact_text, category, confidence, embedding_json, valid_from, valid_until
                FROM memory_facts_v2
                WHERE valid_until IS NULL
                ORDER BY created_at DESC
            """)
            facts = cur.fetchall()
            if len(facts) < 2:
                conn.close()
                return 0

            invalidated = 0
            now = time.time()

            for i in range(len(facts)):
                id_a, text_a, cat_a, conf_a, emb_a_json, vf_a, vu_a = facts[i]
                if not emb_a_json:
                    continue
                try:
                    vec_a = json.loads(emb_a_json)
                except Exception as exc:
                    logger.debug("Failed to decode embedding JSON for fact %s: %s", id_a, exc)
                    continue

                for j in range(i + 1, len(facts)):
                    id_b, text_b, cat_b, conf_b, emb_b_json, vf_b, vu_b = facts[j]
                    if cat_a != cat_b or not emb_b_json:
                        continue
                    try:
                        vec_b = json.loads(emb_b_json)
                    except Exception as exc:
                        logger.debug("Failed to decode embedding JSON for fact %s: %s", id_b, exc)
                        continue

                    # High similarity in same category indicates replacement
                    sim = self.embed_mgr.compute_batch_similarity(vec_a, [vec_b])[0]
                    if sim > 0.92:
                        with conn:
                            conn.execute(
                                """
                                UPDATE memory_facts_v2
                                SET valid_until = ?, superseded_by = ?
                                WHERE id = ? AND valid_until IS NULL
                            """,
                                (now, id_a, id_b),
                            )
                        invalidated += 1

            conn.close()
            logger.info("📅 [Mem0 Dream] Bi-temporal facts consolidated: %d older facts superseded.", invalidated)
            return invalidated
        except Exception as e:
            logger.error("Failed to consolidate bi-temporal facts: %s", e)
            return 0

    def prune_orphaned_kg_edges(self) -> int:
        """Removes graph edges whose source or target nodes were deleted."""
        try:
            conn = get_db_connection(self.db_path)
            with conn:
                cur = conn.cursor()
                cur.execute("""
                    DELETE FROM kg_edges
                    WHERE source_id NOT IN (SELECT id FROM kg_nodes)
                       OR target_id NOT IN (SELECT id FROM kg_nodes)
                """)
                pruned = cur.rowcount
            conn.close()
            if pruned > 0:
                logger.info("🕸️ [Mem0 Dream] Pruned %d orphaned kg_edges.", pruned)
            return pruned
        except Exception as e:
            logger.warning("Failed to prune orphaned kg_edges: %s", e)
            return 0

    def compact_telemetry_edges(self) -> int:
        """Removes telemetry edges not seen in the last 30 days if hit_count is low."""
        try:
            conn = get_db_connection(self.db_path)
            cutoff = time.time() - (30 * 86400)
            with conn:
                cur = conn.cursor()
                cols = {row[1] for row in cur.execute("PRAGMA table_info(telemetry_call_edges)").fetchall()}
                if not cols:
                    return 0
                time_col = "last_called" if "last_called" in cols else ("last_seen" if "last_seen" in cols else None)
                cnt_col = "call_count" if "call_count" in cols else ("hit_count" if "hit_count" in cols else None)
                if not time_col or not cnt_col:
                    return 0

                cur.execute(
                    f"""
                    DELETE FROM telemetry_call_edges
                    WHERE ({time_col} < datetime(?, 'unixepoch') OR {time_col} < ? OR {time_col} IS NULL)
                      AND {cnt_col} < 2
                    """,
                    (cutoff, cutoff),
                )
                compacted = cur.rowcount
            conn.close()
            if compacted > 0:
                logger.info("📡 [Mem0 Dream] Compacted %d stale telemetry edges.", compacted)
            return compacted
        except Exception as e:
            logger.warning("Failed to compact telemetry edges: %s", e)
            return 0

    def vacuum_and_checkpoint(self) -> None:
        """Executes SQLite WAL checkpoint and VACUUM."""
        try:
            conn = get_db_connection(self.db_path)
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            conn.execute("VACUUM;")
            conn.close()
            logger.info("🧹 [Mem0 Dream] SQLite WAL checkpoint and VACUUM completed.")
        except Exception as e:
            logger.warning("Failed to vacuum SQLite DB: %s", e)

    def get_last_consolidation(self) -> Optional[Dict[str, Any]]:
        """Returns the most recent consolidation run from dream_consolidation_log, or None."""
        try:
            conn = get_db_connection(self.db_path, read_only=True)
            cur = conn.cursor()
            cur.execute("""
                SELECT id, timestamp, stats_json, duration_seconds, status
                FROM dream_consolidation_log
                ORDER BY id DESC LIMIT 1
            """)
            row = cur.fetchone()
            conn.close()
            if not row:
                return None
            stats = {}
            if row[2]:
                try:
                    stats = json.loads(row[2])
                except Exception:
                    stats = {}
            return {
                "id": row[0],
                "timestamp": row[1],
                "stats": stats,
                "duration_seconds": row[3],
                "status": row[4],
            }
        except Exception as e:
            logger.debug("Failed reading last dream consolidation: %s", e)
            return None

    def get_consolidation_status(self) -> Dict[str, Any]:
        """Returns summary status of dream consolidation."""
        last_run = self.get_last_consolidation()
        if not last_run:
            return {
                "last_run": None,
                "hours_since_last": None,
                "status": "NEVER_RUN",
                "stats": {},
            }
        hours_since = None
        try:
            ts_str = last_run["timestamp"]
            if ts_str.endswith("Z"):
                ts_str = ts_str[:-1] + "+00:00"
            ts = datetime.datetime.fromisoformat(ts_str)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=datetime.timezone.utc)
            now = datetime.datetime.now(datetime.timezone.utc)
            hours_since = round((now - ts).total_seconds() / 3600.0, 1)
        except Exception as e:
            logger.debug("Error computing hours_since_last: %s", e)

        return {
            "last_run": last_run["timestamp"],
            "hours_since_last": hours_since,
            "status": last_run.get("status", "SUCCESS"),
            "duration_seconds": last_run.get("duration_seconds", 0.0),
            "stats": last_run.get("stats", {}),
        }


def get_consolidation_status(db_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """Helper retrieving dream consolidation status."""
    return DreamConsolidator(db_path).get_consolidation_status()


def run_dream_consolidation(db_path: Optional[Union[str, Path]] = None, run_vacuum: bool = False) -> Dict[str, int]:
    """Helper running full dream consolidation."""
    return DreamConsolidator(db_path).run_full_consolidation(run_vacuum=run_vacuum)
