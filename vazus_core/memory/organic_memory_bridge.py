"""
vazus_core.organic_memory_bridge
Closed-Loop Organic Memory Engine for SuperGraph OS & Antigravity (AGY).
Provides automatic persistent memory recall, insight recording, and skill/harness synchronization.
"""

import os
import sqlite3
import json
import time
import sys
import re
import uuid
import hashlib
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')

from typing import Any

from vazus_core.db import get_db_connection, DEFAULT_VAZUS_DB, pack_vector_f32, unpack_vector_f32
from vazus_core.embeddings import get_embedding, UnifiedEmbeddingManager, get_embedding_manager

DB_PATH = os.getenv("VAZUS_DB_PATH", DEFAULT_VAZUS_DB)
WIKI_DIR = r"C:\vazus\services\memory\semantic"
SOUL_PATH = r"C:\vazus\services\memory\SOUL.md"
USER_PATH = r"C:\vazus\services\memory\USER.md"


def init_db(db_path: str | None = None) -> sqlite3.Connection:
    """Initializes and returns a WAL-enabled connection to vazus.db with unified schemas."""
    target_path = db_path or os.getenv("VAZUS_DB_PATH", DEFAULT_VAZUS_DB)
    return get_db_connection(target_path)


def sanitize_zettel_id(raw_id: str) -> str:
    """Sanitizes raw entity ID or title into a standard Zettel ID string: 'Zettel_<clean_identifier>'."""
    if not raw_id:
        raw_id = "entity_unknown"
    clean = re.sub(r'[^\w\-]', '_', str(raw_id).strip())
    clean = re.sub(r'_+', '_', clean).strip('_')
    if not clean:
        clean = "note"
    if clean.startswith("Zettel_"):
        return clean
    elif clean.startswith("zettel_"):
        return "Zettel_" + clean[7:]
    else:
        return f"Zettel_{clean}"


def recommend_wikilinks(
    text_or_query: str,
    threshold: float = 0.70,
    top_k: int = 5,
    exclude_id: str | None = None,
    db_path: str | None = None,
    conn: sqlite3.Connection | None = None
) -> list[dict[str, Any]]:
    """
    Computes 768D vector similarity and generates [[Wikilink]] recommendations
    for notes/nodes in Karpathy Memory Wiki and Knowledge Graph matching similarity > threshold (default 0.70).
    """
    close_conn = False
    if conn is None:
        target_path = db_path or os.getenv("VAZUS_DB_PATH", DEFAULT_VAZUS_DB)
        if not os.path.exists(target_path):
            return []
        conn = get_db_connection(target_path)
        close_conn = True

    embedder = get_embedding_manager()
    query_vec = embedder.get_embedding(text_or_query)
    if not query_vec:
        if close_conn:
            conn.close()
        return []

    cur = conn.cursor()
    try:
        # Query up to 100 recent kg_nodes with embeddings to prevent memory growth
        cur.execute(
            "SELECT id, name, domain, node_type, description, properties, embedding_json FROM kg_nodes WHERE embedding_json IS NOT NULL AND embedding_json != '[]' ORDER BY ROWID DESC LIMIT 100"
        )
        rows = cur.fetchall()
    finally:
        cur.close()
        if close_conn:
            conn.close()

    if not rows:
        return []

    candidate_ids = []
    candidate_names = []
    candidate_descs = []
    candidate_domains = []
    candidate_types = []
    candidate_vecs = []

    for r in rows:
        nid = r[0]
        if exclude_id and nid == exclude_id:
            continue
        try:
            vec_raw = r[6]
            if vec_raw and vec_raw != '[]' and vec_raw != b'':
                if isinstance(vec_raw, str):
                    try:
                        vec = json.loads(vec_raw)
                    except Exception:
                        vec = np.fromstring(vec_raw.strip('[]'), sep=',', dtype=np.float32)
                elif isinstance(vec_raw, bytes):
                    vec = unpack_vector_f32(vec_raw)
                else:
                    vec = []
                if len(vec) == len(query_vec):
                    candidate_ids.append(nid)
                    candidate_names.append(r[1] or nid)
                    candidate_descs.append(r[4] or "")
                    candidate_domains.append(r[2] or "general")
                    candidate_types.append(r[3] or "Node")
                    candidate_vecs.append(vec)
        except Exception:
            continue

    if not candidate_vecs:
        return []

    # Compute batch cosine similarities via 2D NumPy dot product
    sims = embedder.compute_batch_similarity(query_vec, candidate_vecs)

    query_words = set(w.lower() for w in re.findall(r'\w+', text_or_query) if len(w) > 2)

    recommendations = []
    for idx, vec_sim in enumerate(sims):
        nid = candidate_ids[idx]
        name = candidate_names[idx]
        desc = candidate_descs[idx]
        cand_text = f"{name} {desc} {candidate_domains[idx]} {candidate_types[idx]}".lower()
        cand_words = set(w.lower() for w in re.findall(r'\w+', cand_text) if len(w) > 2)

        kw_score = 0.0
        if query_words and cand_words:
            overlap = query_words.intersection(cand_words)
            kw_score = len(overlap) / len(query_words)

        final_score = max(float(vec_sim), float(kw_score)) if kw_score > 0 else float(vec_sim)

        if final_score >= threshold:
            z_id = sanitize_zettel_id(nid)
            wikilink_clean = f"[[{z_id}|{name}]]"
            wikilink_annotated = f"[[{z_id}|{name} ({int(final_score * 100)}% match)]]"
            recommendations.append({
                "node_id": nid,
                "zettel_id": z_id,
                "name": name,
                "domain": candidate_domains[idx],
                "node_type": candidate_types[idx],
                "similarity": round(final_score, 4),
                "wikilink": wikilink_clean,
                "wikilink_annotated": wikilink_annotated
            })

    # Sort descending by similarity score
    recommendations.sort(key=lambda x: x["similarity"], reverse=True)
    return recommendations[:top_k]


def recommend_wikilinks_for_insight(
    insight_text: str,
    category: str = "",
    threshold: float = 0.70,
    top_k: int = 5,
    db_path: str | None = None
) -> list[str]:
    """Returns a list of clean [[Wikilink]] strings matching similarity > threshold (default 0.70)."""
    full_text = f"[{category}] {insight_text}" if category else insight_text
    recs = recommend_wikilinks(full_text, threshold=threshold, top_k=top_k, db_path=db_path)
    return [r["wikilink"] for r in recs]


def record_insight(
    category: str,
    insight: str | None = None,
    content: str | None = None,
    metadata: dict[str, Any] | None = None,
    db_path: str | None = None,
    auto_wikilink_threshold: float = 0.70
) -> dict[str, Any]:
    """Records a general memory insight into organic_insights, kg_nodes, and SQLite-vec vector index with automatic [[Wikilink]] recommendations."""
    text_content = insight or content or ""
    if not text_content:
        raise ValueError("Either 'insight' or 'content' must be provided.")

    target_path = db_path or os.getenv("VAZUS_DB_PATH", DEFAULT_VAZUS_DB)
    now = time.time()
    
    # 1. Deterministic node_id generated OUTSIDE the retry loop
    if metadata and metadata.get("node_id"):
        node_id = str(metadata["node_id"])
    else:
        # Compute deterministic node_id based on category and text_content SHA-256 hash
        content_key = f"{category}:{text_content}".encode('utf-8')
        content_hash = hashlib.sha256(content_key).hexdigest()[:16]
        node_id = f"insight_{content_hash}"

    # Pre-compute embedding and JSON payload outside retry loop
    try:
        vec = get_embedding(text_content)
        vec_json = json.dumps(list(vec)) if vec else "[]"
    except Exception:
        vec = []
        vec_json = "[]"

    # 2. Retrieve Wikilink recommendations using separate read connection before write loop
    wikilink_recs = []
    try:
        rec_fn = globals().get("recommend_wikilinks", recommend_wikilinks)
        wikilink_recs = rec_fn(text_content, threshold=auto_wikilink_threshold, top_k=5, exclude_id=node_id, db_path=target_path)
    except Exception:
        pass

    max_retries = 15
    now = time.time()
    props_dict = {"category": category, "text": text_content, "timestamp": now, "node_id": node_id}
    if metadata:
        props_dict.update(metadata)
    props = json.dumps(props_dict)

    # 3. SQLite Database Transaction Retry Loop
    db_committed = False
    for attempt in range(max_retries):
        conn = None
        try:
            conn = get_db_connection(target_path, timeout=60.0, use_cache=False)
            conn.execute("BEGIN IMMEDIATE;")
            cur = conn.cursor()
            
            # Idempotent insert into organic_insights
            cur.execute(
                "INSERT OR IGNORE INTO organic_insights (node_id, category, insight, timestamp) VALUES (?, ?, ?, ?)",
                (node_id, category, text_content, now)
            )
            
            # Idempotent upsert into kg_nodes
            cur.execute(
                """INSERT OR REPLACE INTO kg_nodes 
                   (id, name, domain, node_type, description, tags, properties, embedding_json) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (node_id, text_content[:50], "organic_memory", "insight", text_content, category, props, vec_json)
            )

            if wikilink_recs:
                for rec in wikilink_recs:
                    edge_props = json.dumps({"similarity": rec["similarity"], "wikilink": rec["wikilink"]})
                    cur.execute(
                        "INSERT OR REPLACE INTO kg_edges (source_id, target_id, relation, strength, properties) VALUES (?, ?, ?, ?, ?)",
                        (node_id, rec["node_id"], "RECOMMENDED_WIKILINK", rec["similarity"], edge_props)
                    )

            conn.commit()
            cur.close()
            db_committed = True
            break
        except Exception as exc:
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            is_retryable = isinstance(exc, (sqlite3.OperationalError, PermissionError, OSError))
            if is_retryable and attempt < max_retries - 1:
                import threading
                threading.Event().wait(timeout=0.05 * (1.5 ** attempt))
                continue
            raise
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    if not db_committed:
        raise RuntimeError("Failed to commit database insight after maximum retries.")

    if os.getenv("VAZUS_VERBOSE") == "1":
        print(f"[+] Memory Insight recorded [{category}]: {text_content[:60]}... ({len(wikilink_recs)} [[Wikilink]] recommendations > {auto_wikilink_threshold})")
    return {
        "status": "SUCCESS",
        "node_id": node_id,
        "category": category,
        "insight": text_content,
        "content": text_content,
        "metadata": metadata or {},
        "timestamp": now,
        "wikilink_recommendations": [r["wikilink"] for r in wikilink_recs],
        "recommendations_detail": wikilink_recs
    }


def query_vector_memory(
    query_text: str,
    top_k: int = 5,
    domain_filter: str | None = None,
    db_path: str | None = None
) -> list[dict[str, Any]]:
    """
    Contractual query function for LEANN 768D vector memory space.
    Retrieves matching memory nodes sorted descending by vector similarity.
    """
    target_path = db_path or os.getenv("VAZUS_DB_PATH", DEFAULT_VAZUS_DB)
    mgr = get_embedding_manager()
    return mgr.search_unified_vector_space(
        query=query_text,
        db_path=target_path,
        top_k=top_k,
        domain_filter=domain_filter
    )


def search_memory_semantic(query: str, threshold: float = 0.70, limit: int = 5, db_path: str | None = None) -> list:
    """Performs semantic 768D vector search across memory insights and Karpathy wiki nodes with similarity filtering."""
    recs = recommend_wikilinks(query, threshold=threshold, top_k=limit, db_path=db_path)
    return recs


def record_code_optimization(
    module_name: str,
    optimization_type: str,
    before_metrics: dict,
    after_metrics: dict,
    ast_reduction_pct: float,
    speedup_pct: float,
    memory_reduction_bytes: int,
    db_path: str | None = None
) -> dict:
    """
    Logs an empirically verified code optimization into organic_insights and kg_nodes
    with exact metrics and a 768-dim float vector embedding in vazus.db.
    """
    target_path = db_path or os.getenv("VAZUS_DB_PATH", DEFAULT_VAZUS_DB)
    now = time.time()

    payload = {
        "module_name": module_name,
        "optimization_type": optimization_type,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "ast_reduction_pct": float(ast_reduction_pct),
        "speedup_pct": float(speedup_pct),
        "memory_reduction_bytes": int(memory_reduction_bytes),
        "timestamp": now
    }
    insight_json = json.dumps(payload)

    # Generate 768-dim float vector embedding via vazus_core.embeddings.get_embedding
    insight_desc = (
        f"Verified code optimization ({optimization_type}) for {module_name}: "
        f"AST reduction {ast_reduction_pct:.2f}%, speedup {speedup_pct:.2f}%, "
        f"memory reduction {memory_reduction_bytes} bytes."
    )
    vec = get_embedding(insight_json)
    embedding_json = json.dumps(list(vec)) if vec else "[]"

    node_id = f"opt:{module_name}:{int(now * 1000)}"

    conn = get_db_connection(target_path)
    cur = None
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT OR IGNORE INTO organic_insights (node_id, category, insight, timestamp) VALUES (?, ?, ?, ?)",
            (node_id, "code_optimization", insight_json, now)
        )
        cur.execute(
            """INSERT OR REPLACE INTO kg_nodes 
               (id, name, domain, node_type, description, tags, properties, embedding_json) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                node_id,
                module_name,
                "code_optimization",
                "verified_refactor",
                insight_desc,
                "code_optimization,verified_refactor,empirical",
                insight_json,
                embedding_json
            )
        )
        conn.commit()
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        raise exc
    finally:
        if cur is not None:
            try:
                cur.close()
            except Exception:
                pass
        try:
            conn.close()
        except Exception:
            pass

    return {
        "status": "SUCCESS",
        "node_id": node_id,
        "module_name": module_name,
        "optimization_type": optimization_type,
        "ast_reduction_pct": ast_reduction_pct,
        "speedup_pct": speedup_pct,
        "memory_reduction_bytes": memory_reduction_bytes,
        "timestamp": now
    }


def get_recent_optimizations(limit: int = 50, db_path: str | None = None) -> list:
    """Retrieves up to limit recent code optimization records from organic_insights."""
    target_path = db_path or os.getenv("VAZUS_DB_PATH", DEFAULT_VAZUS_DB)
    conn = get_db_connection(target_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, category, insight, timestamp FROM organic_insights WHERE category = 'code_optimization' ORDER BY timestamp DESC LIMIT ?",
        (limit,)
    )
    rows = cur.fetchall()
    conn.close()
    
    results = []
    for r in rows:
        try:
            data = json.loads(r["insight"])
            data["insight_id"] = r["id"]
            results.append(data)
        except Exception:
            results.append({
                "insight_id": r["id"],
                "category": r["category"],
                "raw_insight": r["insight"],
                "timestamp": r["timestamp"]
            })
    return results


def search_optimization_insights(query: str, top_k: int = 5, db_path: str | None = None) -> list:
    """Searches code optimization insights using 768-dim vector space matching."""
    target_path = db_path or os.getenv("VAZUS_DB_PATH", DEFAULT_VAZUS_DB)
    embedder = UnifiedEmbeddingManager()
    return embedder.search_unified_vector_space(
        query=query,
        db_path=target_path,
        top_k=top_k,
        domain_filter="code_optimization"
    )


def search_memory(query: str, limit: int = 5, db_path: str | None = None) -> list:
    """Searches memory insights via FTS5 full-text index (fast) with LIKE fallback."""
    target_path = db_path or os.getenv("VAZUS_DB_PATH", DEFAULT_VAZUS_DB)
    conn = get_db_connection(target_path)
    cur = conn.cursor()
    try:
        # Fast path: FTS5 full-text index
        cur.execute(
            "SELECT category, insight, timestamp FROM organic_insights_fts"
            " WHERE organic_insights_fts MATCH ? ORDER BY rank LIMIT ?",
            (query, limit)
        )
    except Exception:
        # Fallback: LIKE scan (if FTS5 table not yet created)
        pattern = f"%{query}%"
        cur.execute(
            "SELECT category, insight, timestamp FROM organic_insights"
            " WHERE insight LIKE ? OR category LIKE ? ORDER BY timestamp DESC LIMIT ?",
            (pattern, pattern, limit)
        )
    results = cur.fetchall()
    conn.close()
    return [{"category": r[0], "insight": r[1], "timestamp": r[2]} for r in results]



def get_organic_summary(db_path: str | None = None) -> dict:
    """Returns summary stats of kg_nodes and organic_insights."""
    target_path = db_path or os.getenv("VAZUS_DB_PATH", DEFAULT_VAZUS_DB)
    conn = get_db_connection(target_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM kg_nodes")
    node_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM organic_insights")
    insight_count = cur.fetchone()[0]
    conn.close()

    soul = ""
    if os.path.exists(SOUL_PATH):
        with open(SOUL_PATH, "r", encoding="utf-8") as f:
            soul = f.read()[:300]

    return {
        "node_count": node_count,
        "insight_count": insight_count,
        "soul_preview": soul
    }


def record_harness_blueprint(
    harness_id: str,
    name: str,
    domain: str,
    description: str,
    metadata: dict[str, Any],
    db_path: str | None = None
) -> dict[str, Any]:
    """
    Persists a research lab harness blueprint into vazus.db tables:
    - kg_nodes (node_type="research_harness_blueprint", domain="harness_blueprint", 768D float vector JSON)
    - organic_insights (category="harness_blueprint")
    """
    target_path = db_path or os.getenv("VAZUS_DB_PATH", DEFAULT_VAZUS_DB)
    now = time.time()

    insight_payload = json.dumps({
        "harness_id": harness_id,
        "name": name,
        "domain": domain,
        "description": description,
        "metadata": metadata
    })

    node_id = f"harness:{harness_id}"

    conn = get_db_connection(target_path)
    cur = None
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT OR IGNORE INTO organic_insights (node_id, category, insight, timestamp) VALUES (?, ?, ?, ?)",
            (node_id, "harness_blueprint", insight_payload, now)
        )

        embed_text = f"{name} - {description} ({domain})"
        try:
            vec = get_embedding(embed_text)
            vec_json = json.dumps(list(vec)) if vec else "[]"
        except Exception:
            vec_json = "[]"

        node_id = f"harness:{harness_id}"
        tags = f"harness_blueprint,research_lab,{domain},{harness_id}"
        props_json = json.dumps(metadata)

        cur.execute(
            """INSERT OR REPLACE INTO kg_nodes 
               (id, name, domain, node_type, description, tags, properties, embedding_json) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                node_id,
                name,
                "harness_blueprint",
                "research_harness_blueprint",
                description,
                tags,
                props_json,
                vec_json
            )
        )
        conn.commit()
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        raise exc
    finally:
        if cur is not None:
            try:
                cur.close()
            except Exception:
                pass
        try:
            conn.close()
        except Exception:
            pass

    print(f"[+] Harness Blueprint recorded [{harness_id}]: {name}")
    return {
        "status": "SUCCESS",
        "node_id": node_id,
        "harness_id": harness_id,
        "name": name,
        "domain": domain,
        "description": description,
        "metadata": metadata,
        "timestamp": now
    }


def sync_all_harness_blueprints(db_path: str | None = None) -> list[dict[str, Any]]:
    """
    Instantiates all 7 research lab harness blueprints from labs/harness_expansion/,
    extracts metadata, computes 768D float vector embeddings via get_embedding(),
    and persists into vazus.db tables kg_nodes and organic_insights.
    """
    from labs.harness_expansion.nous_hermes.hermes_blueprint import HermesHarnessBlueprint
    from labs.harness_expansion.deepmind_odr.odr_blueprint import OpenDeepResearchBlueprint
    from labs.harness_expansion.anthropic_thinking.thinking_blueprint import AnthropicThinkingBlueprint
    from labs.harness_expansion.mit_rlm.rlm_blueprint import MITRLMBlueprint
    from labs.harness_expansion.openai_swarm_jury.swarm_jury_blueprint import OpenAISwarmJuryBlueprint
    from labs.harness_expansion.graphify_ast.graphify_blueprint import GraphifyASTBlueprint
    from labs.harness_expansion.concordia_jury.concordia_blueprint import ConcordiaJuryBlueprint

    blueprints = [
        HermesHarnessBlueprint(),
        OpenDeepResearchBlueprint(),
        AnthropicThinkingBlueprint(),
        MITRLMBlueprint(),
        OpenAISwarmJuryBlueprint(),
        GraphifyASTBlueprint(),
        ConcordiaJuryBlueprint(),
    ]

    results = []
    for bp in blueprints:
        meta = bp.get_metadata()
        harness_id = meta.get("harness_id", "")
        name = meta.get("name", "")
        domain = meta.get("domain", "harness_blueprint")
        description = meta.get("description", "")
        res = record_harness_blueprint(
            harness_id=harness_id,
            name=name,
            domain=domain,
            description=description,
            metadata=meta,
            db_path=db_path
        )
        results.append(res)

    print(f"[+] Synchronized {len(results)} research lab harness blueprints into vazus.db")
    return results


if __name__ == "__main__":
    init_db()
    record_insight("architecture", "NousResearch Hermes Skills & Harness integrated into Antigravity CLI")
    sync_all_harness_blueprints()
    summary = get_organic_summary()
    print("[+] Organic Memory Engine Ready:", summary)

