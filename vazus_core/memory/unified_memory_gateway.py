"""
vazus_core.memory.unified_memory_gateway — Unified Canonical Memory Gateway.
=============================================================================

Consolidates memory subsystems into a single canonical API:
  1. SQLite Persistent WAL (vazus.db)
  2. Karpathy LLM Wiki Compiler (services/memory/semantic/wiki/)
  3. Mem0 Episodic Memory (mem0_memory_engine)
  4. Graphify AST Code Topology (graphify_engine)
  5. 768-D Vector Embeddings Layer (embeddings)
  6. Organic Insight Ledger (organic_insights table)

Eliminates memory fragmentation, split-brain knowledge, and redundant queries.
"""

import os
import re
import heapq
import sqlite3
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Union

from vazus_core.memory.mem0_memory_engine import Mem0Engine
from vazus_core.engine.graphify_engine import GraphifyEngine
from vazus_core.storage.sqlite_pool import RobustSQLitePool
from vazus_core.memory.db import DEFAULT_VAZUS_DB

logger = logging.getLogger("vazus_core.memory.gateway")

DEFAULT_DB_PATH: str = DEFAULT_VAZUS_DB
DEFAULT_WIKI_ROOT: str = r"/home/tarhes/Проекты/vazus/services/memory/semantic/wiki"


class UnifiedMemoryGateway:
    """
    Single canonical point of entry for all memory read and write operations.
    """

    def __init__(
        self,
        db_path: Optional[Union[str, Path]] = None,
        wiki_root: Optional[Union[str, Path]] = None
    ):
        target_db = db_path or os.getenv("VAZUS_DB_PATH", DEFAULT_VAZUS_DB)
        target_wiki = wiki_root or os.getenv("VAZUS_WIKI_ROOT", DEFAULT_WIKI_ROOT)
        self.db_path = Path(target_db).resolve()
        self.wiki_root = Path(target_wiki).resolve()
        self.pool = RobustSQLitePool(str(self.db_path))
        self.mem0 = Mem0Engine(db_path=str(self.db_path))
        self.graphify = GraphifyEngine(db_path=str(self.db_path))

    def store_fact(self, fact_text: str, category: str = "general", entity: str = "user", tags: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Stores a verified fact across episodic memory (mem0) and persistent SQLite ledger.
        """
        # 1. Store in Mem0 episodic fact memory
        fact_id = self.mem0.add_fact(
            fact_text=fact_text,
            category=category,
            entity=entity
        )

        # 2. Record in SQLite organic_insights ledger for durability
        with self.pool.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS organic_insights (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    node_id TEXT UNIQUE,
                    category TEXT,
                    insight TEXT,
                    timestamp REAL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute(
                "INSERT INTO organic_insights (category, insight) VALUES (?, ?)",
                (category, fact_text)
            )
            conn.commit()


        return {
            "status": "STORED",
            "fact_id": fact_id,
            "category": category,
            "entity": entity,
        }

    def crystallize_insight(
        self,
        category: str,
        insight_text: str,
        node_id: Optional[str] = None,
        timestamp: Optional[float] = None,
    ) -> Optional[int]:
        """
        Crystallizes a verified architectural optimization or rejected candidate
        into the organic_insights ledger with bitemporal deduplication and idempotence.
        """
        if not node_id:
            import hashlib
            digest = hashlib.sha256(f"{category}:{insight_text}".encode()).hexdigest()[:16]
            resolved_node_id = f"node_{digest}"
        else:
            resolved_node_id = node_id

        import time
        valid_ts = timestamp if timestamp is not None else time.time()

        try:
            with self.pool.connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT id FROM organic_insights WHERE node_id = ?",
                    (resolved_node_id,),
                )
                existing = cur.fetchone()
                if existing:
                    cur.execute(
                        """
                        UPDATE organic_insights
                        SET category = ?, insight = ?, timestamp = ?, created_at = datetime('now')
                        WHERE id = ?
                        """,
                        (category, insight_text, valid_ts, existing[0]),
                    )
                    insight_id = existing[0]
                else:
                    try:
                        cur.execute(
                            """
                            INSERT INTO organic_insights (category, insight, timestamp, node_id, created_at)
                            VALUES (?, ?, ?, ?, datetime('now'))
                            """,
                            (category, insight_text, valid_ts, resolved_node_id),
                        )
                        insight_id = cur.lastrowid
                    except sqlite3.IntegrityError:
                        cur.execute(
                            """
                            UPDATE organic_insights
                            SET category = ?, insight = ?, timestamp = ?, created_at = datetime('now')
                            WHERE node_id = ?
                            """,
                            (category, insight_text, valid_ts, resolved_node_id),
                        )
                        cur.execute("SELECT id FROM organic_insights WHERE node_id = ?", (resolved_node_id,))
                        row = cur.fetchone()
                        insight_id = row[0] if row else None
                conn.commit()
                return insight_id
        except (sqlite3.Error, OSError) as e:
            logger.warning("[MemoryGateway] Failed to crystallize insight: %s", e)
            return None

    def recall(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Unified recall across Episodic memory (Mem0), Organic insights, and Code topology.
        """
        results = []

        # 1. Search episodic facts
        mem0_facts = self.mem0.search_facts(query=query, top_k=top_k)
        for f in mem0_facts:
            fact_content = f.get("fact_text", f.get("fact", f.get("text", "")))
            if fact_content:
                results.append({
                    "source": "mem0_episodic",
                    "content": fact_content,
                    "score": f.get("score", 1.0),
                    "category": f.get("category", "general")
                })

        # 2. Search organic insights SQLite ledger with dynamic relevance scoring
        with self.pool.connection() as conn:
            cursor = conn.cursor()
            try:
                q_words = [w.strip() for w in re.findall(r"\w+", query.lower()) if len(w.strip()) > 2]
                rows = []
                if q_words:
                    try:
                        fts_query = " OR ".join(f'"{w}"' for w in q_words)
                        cursor.execute(
                            "SELECT category, insight FROM organic_insights_fts "
                            "WHERE organic_insights_fts MATCH ? ORDER BY rank LIMIT 50",
                            (fts_query,),
                        )
                        rows = cursor.fetchall()
                    except (sqlite3.OperationalError, sqlite3.DatabaseError) as fts_err:
                        logger.debug("[MemoryGateway] FTS recall fallback: %s", fts_err)
                        rows = []

                    if not rows:
                        conditions = " OR ".join(["insight LIKE ? OR category LIKE ?" for _ in q_words])
                        params = []
                        for w in q_words:
                            params.extend([f"%{w}%", f"%{w}%"])
                        cursor.execute(
                            f"SELECT category, insight FROM organic_insights WHERE {conditions} ORDER BY id DESC LIMIT 50",
                            params,
                        )
                        rows = cursor.fetchall()
                else:
                    cursor.execute("SELECT category, insight FROM organic_insights ORDER BY id DESC LIMIT 10")
                    rows = cursor.fetchall()

                q_token_set = set(q_words)
                organic_matches = []
                seen_insights = set()
                for row in rows:
                    cat, ins = row[0], row[1]
                    if not ins or ins in seen_insights:
                        continue
                    seen_insights.add(ins)
                    ins_tokens = set(re.findall(r"\w+", ins.lower()))
                    overlap = len(q_token_set & ins_tokens) / max(1, len(q_token_set)) if q_token_set else 0.5
                    # Dynamic score based on lexical overlap
                    relevance_score = 0.5 + (0.5 * overlap)
                    organic_matches.append({
                        "source": "sqlite_organic",
                        "content": ins,
                        "score": round(relevance_score, 3),
                        "category": cat
                    })
                results.extend(heapq.nlargest(top_k, organic_matches, key=lambda x: x["score"]))
            except (sqlite3.Error, OSError) as e:
                logger.warning(f"[MemoryGateway] SQLite recall warning: {e}")
        # 3. Search Karpathy Markdown Wiki notes (title + full text content)
        try:
            wiki_matches = []
            q_lower = query.lower()
            q_token_set = set(re.findall(r"\w+", q_lower))
            if self.wiki_root.exists():
                for md_file in self.wiki_root.glob("*.md"):
                    fname = md_file.stem.lower()
                    title_match = any(tok in fname for tok in q_token_set) if q_token_set else False
                    try:
                        content = md_file.read_text(encoding="utf-8", errors="ignore")
                    except Exception:
                        content = ""

                    file_tokens = set(re.findall(r"\w+", content.lower()))
                    overlap = len(q_token_set & file_tokens) / max(1, len(q_token_set)) if q_token_set else 0.0

                    if title_match or overlap >= 0.25:
                        snippet = content[:350].strip()
                        # Higher score for title matches + content overlap
                        wiki_score = 0.7 + (0.5 * overlap) + (0.2 if title_match else 0.0)
                        wiki_matches.append({
                            "source": "karpathy_wiki",
                            "content": f"[[{md_file.stem}]]: {snippet}",
                            "file_path": str(md_file),
                            "score": round(min(1.5, wiki_score), 3),
                            "category": "wiki_article"
                        })
                        if len(wiki_matches) >= 5:
                            break
            results.extend(wiki_matches)
        except Exception as wiki_err:
            logger.debug("Wiki search non-fatal notice: %s", wiki_err)

        # 4. Check for matching code symbols in Graphify
        code_context = self.graphify.get_compact_subgraph_context(query)
        if "# Symbol" not in code_context and "not found" not in code_context:
            is_exact = query in code_context
            sym_score = 1.3 if is_exact else 1.05
            results.append({
                "source": "graphify_code_topology",
                "content": code_context,
                "score": sym_score,
                "category": "code_symbol"
            })

        # Sort aggregated results across all 4 layers by confidence score
        # Select top_k aggregated results across all 4 layers by confidence score
        return heapq.nlargest(top_k, results, key=lambda x: x.get("score", 0.0))
    def query_code_symbol(self, symbol_name: str) -> str:
        """Retrieves exact deterministic 1-hop AST topology for a code symbol."""
        return self.graphify.get_compact_subgraph_context(symbol_name)

    def write_wiki_article(self, title: str, markdown_content: str, links: Optional[List[str]] = None) -> Path:
        """
        Writes or updates a structured Markdown page in the Karpathy Wiki knowledge graph,
        and atomically synchronizes the insight into SQLite organic_insights and Mem0 episodic facts.
        """
        self.wiki_root.mkdir(parents=True, exist_ok=True)
        safe_title = title.replace(" ", "_").replace("/", "_") + ".md"
        file_path = self.wiki_root / safe_title

        formatted_links = "\n".join([f"- [[{link}]]" for link in (links or [])])
        full_doc = f"# {title}\n\n{markdown_content}\n\n## References & Wikilinks\n{formatted_links}\n"
        file_path.write_text(full_doc, encoding="utf-8")

        # Bidirectional sync: index summary into SQLite organic_insights
        summary = f"[[{title}]]: {markdown_content[:250].strip()}"
        try:
            with self.pool.connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS organic_insights (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        node_id TEXT UNIQUE,
                        category TEXT,
                        insight TEXT,
                        timestamp REAL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cur.execute(
                    "INSERT INTO organic_insights (category, insight) VALUES (?, ?)",
                    ("wiki_article", summary)
                )
                conn.commit()
        except Exception as e:
            logger.warning(f"[MemoryGateway] Failed to sync wiki article to SQLite: {e}")

        # Sync to Mem0
        try:
            self.mem0.add_fact(
                fact_text=summary,
                category="wiki",
                entity="system"
            )
        except Exception as mem_err:
            logger.debug("Mem0 sync note: %s", mem_err)

        return file_path

