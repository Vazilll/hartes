"""
vazus_core.memory.j_space_vector_index
======================================
Постоянный векторный индекс SQLite для семантического пространства J-Space (768D):
- Хранение 768-мерных L2-нормированных векторов в binary BLOB (float32).
- Векторизованный косинусный поиск top-K через NumPy.
- Привязка к канонической базе данных vazus.db (или тестовому sandbox).
"""

import math
import os
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

DEFAULT_DB_PATH = Path("C:/vazus/services/memory/vazus.db")


class JSpaceVectorIndex:
    """
    Управляет постоянным векторным индексом концептов и эпизодов J-Space.
    Использует аппаратный sqlite-vec vec0 виртуальный индекс с автоматическим
    NumPy-фоллбэком.
    """

    def __init__(self, db_path: Optional[str] = None):
        # Honor test isolation env variable if set
        env_db = os.environ.get("VAZUS_DB_PATH")
        raw_path = db_path or env_db or str(DEFAULT_DB_PATH)
        self._is_memory = str(raw_path) == ":memory:"
        self.db_path = Path(raw_path) if not self._is_memory else Path(":memory:")
        # For :memory: mode keep a single persistent connection
        self._shared_conn: Optional[sqlite3.Connection] = None
        if self._is_memory:
            self._shared_conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._shared_conn.row_factory = sqlite3.Row
            self._load_sqlite_vec(self._shared_conn)
        self._ensure_table()

    @staticmethod
    def _load_sqlite_vec(conn: sqlite3.Connection) -> bool:
        """Dynamically loads the sqlite-vec extension if available."""
        try:
            import sqlite_vec
            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
            conn.enable_load_extension(False)
            return True
        except Exception:
            return False

    def _get_connection(self) -> sqlite3.Connection:
        if self._is_memory:
            return self._shared_conn  # type: ignore
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        self._load_sqlite_vec(conn)
        return conn

    def _release_connection(self, conn: sqlite3.Connection) -> None:
        """Close connection only if it's not the shared :memory: one."""
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
                CREATE INDEX IF NOT EXISTS idx_j_space_concept_id 
                ON j_space_vectors(concept_id);
            """)
            # Create vec0 virtual table for hardware-accelerated 768D similarity
            try:
                conn.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS vec_j_space 
                    USING vec0(rowid integer primary key, embedding float[768]);
                """)
                # Backfill existing vectors from j_space_vectors into vec_j_space
                conn.execute("""
                    INSERT OR IGNORE INTO vec_j_space(rowid, embedding)
                    SELECT rowid, vector FROM j_space_vectors
                    WHERE length(vector) = 3072
                      AND rowid NOT IN (SELECT rowid FROM vec_j_space);
                """)
            except Exception:
                pass
            conn.commit()
        finally:
            self._release_connection(conn)

    def insert_vector(
        self,
        concept_id: str,
        semantic_label: str,
        vector: np.ndarray,
        salience: float = 0.5,
        source: str = "npu_sensor",
    ) -> str:
        """Сохраняет вектор в базу данных."""
        vec = np.asarray(vector, dtype=np.float32).flatten()
        norm = np.linalg.norm(vec)
        if norm > 1e-6:
            vec = vec / norm

        record_id = str(uuid.uuid4())
        now = time.time()

        conn = self._get_connection()
        try:
            cur = conn.execute(
                """
                INSERT INTO j_space_vectors (id, concept_id, semantic_label, salience, vector, source, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (record_id, concept_id, semantic_label, salience, vec.tobytes(), source, now),
            )
            rowid = cur.lastrowid
            if rowid and len(vec) == 768:
                try:
                    conn.execute("INSERT OR REPLACE INTO vec_j_space(rowid, embedding) VALUES (?, ?)", (rowid, vec.tobytes()))
                except Exception:
                    pass
            conn.commit()
        finally:
            self._release_connection(conn)

        return record_id

    def upsert_vector(
        self,
        concept_id: str,
        semantic_label: str,
        vector: np.ndarray,
        salience: float = 0.5,
        source: str = "npu_sensor",
    ) -> str:
        """Сохраняет или обновляет вектор в базе данных для заданного concept_id."""
        vec = np.asarray(vector, dtype=np.float32).flatten()
        norm = np.linalg.norm(vec)
        if norm > 1e-6:
            vec = vec / norm

        record_id = str(uuid.uuid4())
        now = time.time()

        conn = self._get_connection()
        try:
            try:
                conn.execute(
                    "DELETE FROM vec_j_space WHERE rowid IN (SELECT rowid FROM j_space_vectors WHERE concept_id = ?)",
                    (concept_id,),
                )
            except Exception:
                pass
            conn.execute("DELETE FROM j_space_vectors WHERE concept_id = ?", (concept_id,))
            cur = conn.execute(
                """
                INSERT INTO j_space_vectors (id, concept_id, semantic_label, salience, vector, source, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (record_id, concept_id, semantic_label, salience, vec.tobytes(), source, now),
            )
            rowid = cur.lastrowid
            if rowid and len(vec) == 768:
                try:
                    conn.execute("INSERT OR REPLACE INTO vec_j_space(rowid, embedding) VALUES (?, ?)", (rowid, vec.tobytes()))
                except Exception:
                    pass
            conn.commit()
        finally:
            self._release_connection(conn)

        return record_id

    def delete_by_source(self, source: str) -> int:
        """Удаляет все векторы с указанным source."""
        conn = self._get_connection()
        try:
            try:
                conn.execute(
                    "DELETE FROM vec_j_space WHERE rowid IN (SELECT rowid FROM j_space_vectors WHERE source = ?)",
                    (source,),
                )
            except Exception:
                pass
            cursor = conn.execute("DELETE FROM j_space_vectors WHERE source = ?", (source,))
            conn.commit()
            return cursor.rowcount
        finally:
            self._release_connection(conn)

    def search_similar(
        self,
        query_vector: np.ndarray,
        top_k: int = 3,
        min_similarity: float = 0.55,
        source: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Выполняет аппаратный векторный поиск через sqlite-vec vec0 index
        с автоматическим векторизованным NumPy-фоллбэком.
        """
        q_vec = np.asarray(query_vector, dtype=np.float32).flatten()
        q_norm = np.linalg.norm(q_vec)
        if q_norm < 1e-6:
            return []
        q_vec = q_vec / q_norm

        conn = self._get_connection()
        try:
            # 1. Попытка через sqlite-vec vec0 виртуальную таблицу (768D)
            if len(q_vec) == 768:
                try:
                    max_dist = math.sqrt(max(0.0, 2.0 * (1.0 - min_similarity)))
                    limit_fetch = top_k * 4 if source else top_k
                    query_sql = """
                        SELECT v.rowid, v.distance, j.id, j.concept_id, j.semantic_label, j.salience, j.source, j.created_at
                        FROM vec_j_space v
                        JOIN j_space_vectors j ON j.rowid = v.rowid
                        WHERE v.embedding MATCH ? AND v.distance <= ?
                        ORDER BY v.distance
                        LIMIT ?
                    """
                    vec_cursor = conn.execute(query_sql, (q_vec.tobytes(), max_dist, limit_fetch))
                    vec_rows = vec_cursor.fetchall()
                    if vec_rows:
                        vec_results = []
                        for r in vec_rows:
                            if source and r["source"] != source:
                                continue
                            dist = float(r["distance"])
                            cos_sim = max(0.0, min(1.0, 1.0 - (dist * dist) / 2.0))
                            if cos_sim >= min_similarity:
                                vec_results.append(
                                    {
                                        "id": r["id"],
                                        "concept_id": r["concept_id"],
                                        "semantic_label": r["semantic_label"],
                                        "salience": r["salience"],
                                        "similarity": round(cos_sim, 4),
                                        "source": r["source"],
                                        "created_at": r["created_at"],
                                    }
                                )
                        if vec_results:
                            return vec_results[:top_k]
                except Exception:
                    pass

            # 2. Фоллбэк на NumPy векторизованный расчет
            if source:
                cursor = conn.execute(
                    "SELECT id, concept_id, semantic_label, salience, vector, source, created_at FROM j_space_vectors WHERE source = ?",
                    (source,),
                )
            else:
                cursor = conn.execute(
                    "SELECT id, concept_id, semantic_label, salience, vector, source, created_at FROM j_space_vectors"
                )
            rows = cursor.fetchall()
        finally:
            self._release_connection(conn)

        if not rows:
            return []

        results = []
        for r in rows:
            blob = r["vector"]
            stored_vec = np.frombuffer(blob, dtype=np.float32)
            if len(stored_vec) != len(q_vec):
                continue
            cos_sim = float(np.dot(q_vec, stored_vec))
            if cos_sim >= min_similarity:
                results.append(
                    {
                        "id": r["id"],
                        "concept_id": r["concept_id"],
                        "semantic_label": r["semantic_label"],
                        "salience": r["salience"],
                        "similarity": round(cos_sim, 4),
                        "source": r["source"],
                        "created_at": r["created_at"],
                    }
                )

        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]

    def count(self, source: Optional[str] = None) -> int:
        conn = self._get_connection()
        try:
            if source:
                cursor = conn.execute("SELECT COUNT(*) FROM j_space_vectors WHERE source = ?", (source,))
            else:
                cursor = conn.execute("SELECT COUNT(*) FROM j_space_vectors")
            return cursor.fetchone()[0]
        finally:
            self._release_connection(conn)
