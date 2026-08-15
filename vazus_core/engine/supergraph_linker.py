"""
vazus.vazus_core.supergraph_linker — Unified SuperGraph 768D Vector Space Linker.
Integrates Layer A (AST Code Topology) with Layer B (Karpathy Memory Wiki).
"""

import sys
import json
import sqlite3
import hashlib
import time
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional, Union
from contextlib import contextmanager

VAZUS_DIR = Path("C:/vazus")
if str(VAZUS_DIR) not in sys.path:
    sys.path.insert(0, str(VAZUS_DIR))

from vazus_core.memory.embeddings import UnifiedGoogleEmbedder

DEFAULT_DB_PATH = Path("C:/vazus/services/memory/vazus.db")
if not DEFAULT_DB_PATH.exists() and Path("C:/vazus/services/memory/vazus.db").exists():
    DEFAULT_DB_PATH = Path("C:/vazus/services/memory/vazus.db")

DEFAULT_GRAPH_JSON_PATH = VAZUS_DIR / "services" / "gomcp" / "graphify-out" / "graph.json"
DEFAULT_WIKI_DIRS = [
    Path("C:/vazus/services/memory/semantic/wiki"),
    Path("C:/vazus/services/memory/semantic/wiki")
]


def calculate_cosine_similarity(vec_a: Optional[List[float]] = None, vec_b: Optional[List[float]] = None, *args, **kwargs) -> float:
    """Computes high-speed cosine similarity between two 768D float vectors using NumPy / SIMD acceleration."""
    if not vec_a or not vec_b:
        return 0.0
    import numpy as np
    a = np.asarray(vec_a, dtype=np.float32)
    b = np.asarray(vec_b, dtype=np.float32)
    if np.isnan(a).any() or np.isnan(b).any():
        return 0.0
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0.0 or norm_b == 0.0 or np.isnan(norm_a) or np.isnan(norm_b):
        return 0.0
    res = float(np.dot(a, b) / (norm_a * norm_b))
    return 0.0 if np.isnan(res) else res


def calculate_fts_similarity(text_a: str, text_b: str) -> float:
    """Computes full-text Jaccard token overlap similarity."""
    if not text_a or not text_b:
        return 0.0
    tokens_a = set(text_a.lower().split())
    tokens_b = set(text_b.lower().split())
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a.intersection(tokens_b)
    union = tokens_a.union(tokens_b)
    return float(len(intersection) / len(union))


def calculate_structural_similarity(node_a: Dict[str, Any], node_b: Dict[str, Any]) -> float:
    """Computes structural similarity based on domain, tags, and graph communities."""
    score = 0.0
    if node_a.get("community") is not None and node_a.get("community") == node_b.get("community"):
        score += 0.5
    tags_a = set(str(node_a.get("tags", "")).lower().split(","))
    tags_b = set(str(node_b.get("tags", "")).lower().split(","))
    if tags_a and tags_b and tags_a.intersection(tags_b):
        score += 0.5
    return float(score)


def calculate_provenance_similarity(node_a: Dict[str, Any], node_b: Dict[str, Any]) -> float:
    """Computes provenance similarity based on matching file source paths."""
    file_a = str(node_a.get("source_file", "")).lower()
    file_b = str(node_b.get("source_file", "")).lower()
    if file_a and file_b and (Path(file_a).name == Path(file_b).name or file_a in file_b or file_b in file_a):
        return 1.0
    return 0.0


class SuperGraphLinker:
    """Orchestrates 768D vector space linking between AST Code Graph and Karpathy Memory Wiki."""

    def __init__(
        self,
        db_path: Path = DEFAULT_DB_PATH,
        graph_json_path: Path = DEFAULT_GRAPH_JSON_PATH,
        wiki_dir: Optional[Path] = None,
        wiki_dirs: Optional[List[Path]] = None,
        vector_dim: int = 768
    ):
        self.db_path = Path(db_path)
        self.graph_json_path = Path(graph_json_path)
        if wiki_dirs:
            self.wiki_dirs = [Path(p) for p in wiki_dirs]
        elif wiki_dir:
            self.wiki_dirs = [Path(wiki_dir)]
        else:
            self.wiki_dirs = [Path(p) for p in DEFAULT_WIKI_DIRS]

        self.wiki_dir = self.wiki_dirs[0] if self.wiki_dirs else DEFAULT_WIKI_DIRS[0]
        self.dim = vector_dim
        self.embedder = UnifiedGoogleEmbedder(dimension=vector_dim)
        self._init_database_tables()

    @contextmanager
    def _get_connection(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        from vazus_core.memory.db import get_db_connection
        conn = get_db_connection(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _init_database_tables(self):
        """Ensures llm_cache, kg_nodes, and kg_edges tables exist."""
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS llm_cache (
                    cache_key TEXT PRIMARY KEY,
                    text_content TEXT,
                    embedding_json TEXT,
                    created_at REAL
                );

                CREATE TABLE IF NOT EXISTS kg_nodes (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    domain TEXT,
                    node_type TEXT,
                    description TEXT,
                    tags TEXT,
                    properties TEXT,
                    embedding_json TEXT
                );

                CREATE TABLE IF NOT EXISTS kg_edges (
                    source_id TEXT,
                    target_id TEXT,
                    relation TEXT,
                    strength REAL,
                    properties TEXT,
                    PRIMARY KEY (source_id, target_id, relation)
                );

                CREATE INDEX IF NOT EXISTS idx_kg_nodes_domain ON kg_nodes(domain);
                CREATE INDEX IF NOT EXISTS idx_kg_nodes_type ON kg_nodes(node_type);
                CREATE INDEX IF NOT EXISTS idx_kg_nodes_name ON kg_nodes(name);
                CREATE INDEX IF NOT EXISTS idx_kg_edges_source ON kg_edges(source_id);
                CREATE INDEX IF NOT EXISTS idx_kg_edges_target ON kg_edges(target_id);
                CREATE INDEX IF NOT EXISTS idx_kg_edges_rel ON kg_edges(relation);
                CREATE INDEX IF NOT EXISTS idx_kg_edges_src_tgt ON kg_edges(source_id, target_id);
            """)
            conn.commit()


    def load_ast_nodes(self) -> List[Dict[str, Any]]:
        """Loads Layer A (AST code topology nodes) from Graphify output JSON or database."""
        ast_nodes = []
        if self.graph_json_path.exists():
            try:
                with open(self.graph_json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    nodes = data.get("nodes", []) if isinstance(data, dict) else data
                    for n in nodes:
                        ast_nodes.append({
                            "id": f"ast:{n.get('id', n.get('name'))}",
                            "name": n.get("name", "UnknownNode"),
                            "domain": "ast_code",
                            "node_type": n.get("type", "CodeNode"),
                            "description": n.get("description", n.get("summary", "")),
                            "source_file": n.get("file", ""),
                            "community": n.get("community", 0),
                            "_origin": "ast",
                            "tags": "ast,code,topology"
                        })
            except Exception as e:
                sys.stderr.write(f"[SuperGraphLinker] Warning reading graph.json: {e}\n")
        return ast_nodes

    def parse_wiki_note_content(self, fpath: Path, content: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Parses a markdown wiki note into a main WikiNote node, WikiSection nodes, and [[Note]] wikilinks."""
        stem = fpath.stem
        note_id = f"wiki:{stem}"
        rel_path = str(fpath).replace("\\", "/")

        main_node = {
            "id": note_id,
            "name": stem.replace("_", " "),
            "domain": "memory_wiki",
            "node_type": "WikiNote",
            "description": content[:500],
            "content": content,
            "source_file": rel_path,
            "community": 1,
            "_origin": "wiki",
            "tags": f"wiki,memory,{stem}"
        }

        section_nodes = []
        edges = []

        # Parse sections based on markdown headings or date timestamps
        lines = content.splitlines()
        current_section_title = None
        current_section_lines = []

        def commit_section():
            if current_section_title and current_section_lines:
                sec_text = "\n".join(current_section_lines).strip()
                sec_slug = re.sub(r'[^a-zA-Z0-9_]', '_', current_section_title.strip().lower()).strip('_')
                if sec_slug:
                    sec_id = f"{note_id}#{sec_slug}"
                    section_nodes.append({
                        "id": sec_id,
                        "name": f"{stem.replace('_', ' ')} - {current_section_title}",
                        "domain": "memory_wiki",
                        "node_type": "WikiSection",
                        "description": sec_text[:500],
                        "content": sec_text,
                        "source_file": rel_path,
                        "community": 1,
                        "_origin": "wiki",
                        "tags": f"wiki,section,{stem},{sec_slug}"
                    })
                    edges.append({
                        "source_id": note_id,
                        "target_id": sec_id,
                        "relation": "CONTAINS_SECTION",
                        "strength": 1.0,
                        "properties": {"parent_note": note_id, "section_title": current_section_title}
                    })

        for line in lines:
            header_match = re.match(r'^(#{1,6})\s+(.+)$', line.strip())
            timestamp_match = re.match(r'^- \*\*\[([^\]]+)\]\*\*:\s*##?\s*(.+)$', line.strip())

            if header_match:
                commit_section()
                current_section_title = header_match.group(2).strip()
                current_section_lines = [line]
            elif timestamp_match:
                commit_section()
                current_section_title = timestamp_match.group(2).strip()
                current_section_lines = [line]
            elif current_section_title:
                current_section_lines.append(line)

        commit_section()

        # Extract [[Note]] wikilinks from entire note content
        wikilink_pattern = re.compile(r"\[\[([^\]\|#]+)(?:#([^\]\|]+))?(?:\|([^\]]+))?\]\]")
        for match in wikilink_pattern.finditer(content):
            target_note_raw = match.group(1).strip()
            target_sec_raw = match.group(2).strip() if match.group(2) else None
            label_raw = match.group(3).strip() if match.group(3) else None

            target_stem = target_note_raw.replace(" ", "_")
            target_id = f"wiki:{target_stem}"

            edges.append({
                "source_id": note_id,
                "target_id": target_id,
                "relation": "WIKILINK",
                "strength": 1.0,
                "properties": {
                    "raw": match.group(0),
                    "target_note": target_stem,
                    "target_section": target_sec_raw,
                    "label": label_raw
                }
            })

        return main_node, section_nodes, edges

    def load_memory_wiki_nodes_and_edges(self) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Loads Layer B Wiki notes, sections, containment edges, and [[Note]] wikilinks across configured wiki dirs."""
        wiki_nodes = []
        wiki_edges = []
        processed_stems = set()

        for wdir in self.wiki_dirs:
            if not wdir.exists():
                continue
            for fpath in wdir.glob("*.md"):
                if fpath.stem in processed_stems:
                    continue
                processed_stems.add(fpath.stem)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        content = f.read()
                    main_node, sec_nodes, edges = self.parse_wiki_note_content(fpath, content)
                    wiki_nodes.append(main_node)
                    wiki_nodes.extend(sec_nodes)
                    wiki_edges.extend(edges)
                except Exception as e:
                    sys.stderr.write(f"[SuperGraphLinker] Warning reading wiki note {fpath}: {e}\n")

        return wiki_nodes, wiki_edges

    def load_memory_wiki_nodes(self) -> List[Dict[str, Any]]:
        """Loads Layer B (Karpathy Memory Wiki markdown note and section nodes)."""
        nodes, _ = self.load_memory_wiki_nodes_and_edges()
        return nodes

    def get_or_compute_embedding(
        self,
        node_or_text: Union[Dict[str, Any], str],
        conn: Optional[sqlite3.Connection] = None
    ) -> List[float]:
        """Returns 768D embedding vector for a node or text, using llm_cache where possible."""
        if isinstance(node_or_text, dict):
            node_id = node_or_text.get("id", "")
            text_content = f"{node_or_text.get('name', '')} {node_or_text.get('description', '')} {node_or_text.get('content', '')}".strip()
            cache_key = hashlib.sha256(f"{node_id}:{text_content}".encode("utf-8")).hexdigest()
        else:
            text_content = str(node_or_text).strip()
            cache_key = hashlib.sha256(f"text:{text_content}".encode("utf-8")).hexdigest()

        def _lookup_and_store(c: sqlite3.Connection) -> List[float]:
            row = c.execute("SELECT embedding_json FROM llm_cache WHERE cache_key = ?", (cache_key,)).fetchone()
            if row and row["embedding_json"]:
                try:
                    return json.loads(row["embedding_json"])
                except Exception:
                    pass

            emb = self.embedder.get_embedding(text_content)
            c.execute(
                "INSERT OR REPLACE INTO llm_cache (cache_key, text_content, embedding_json, created_at) VALUES (?, ?, ?, ?)",
                (cache_key, text_content[:1000], json.dumps(emb), time.time())
            )
            return emb

        if conn is not None:
            return _lookup_and_store(conn)
        else:
            with self._get_connection() as c:
                return _lookup_and_store(c)

    def compute_hybrid_metric(
        self,
        node_u: Dict[str, Any],
        node_v: Dict[str, Any],
        emb_u: List[float],
        emb_v: List[float]
    ) -> Dict[str, float]:
        text_u = f"{node_u.get('name', '')} {node_u.get('description', '')}"
        text_v = f"{node_v.get('name', '')} {node_v.get('description', '')} {node_v.get('content', '')}"

        s_cosine = calculate_cosine_similarity(emb_u, emb_v)
        s_fts = calculate_fts_similarity(text_u, text_v)
        s_structural = calculate_structural_similarity(node_u, node_v)
        s_provenance = calculate_provenance_similarity(node_u, node_v)

        total_score = (
            0.45 * s_cosine +
            0.25 * s_fts +
            0.20 * s_structural +
            0.10 * s_provenance
        )

        return {
            "s_cosine": float(s_cosine),
            "s_fts": float(s_fts),
            "s_structural": float(s_structural),
            "s_provenance": float(s_provenance),
            "total_score": float(total_score)
        }

    def link_nodes(
        self,
        ast_nodes: List[Dict[str, Any]],
        wiki_nodes: List[Dict[str, Any]],
        threshold: float = 0.15,
        relation: str = "SUPERGRAPH_LINK"
    ) -> List[Dict[str, Any]]:
        if not ast_nodes or not wiki_nodes:
            return []

        with self._get_connection() as conn:
            embeddings_u = {u["id"]: self.get_or_compute_embedding(u, conn=conn) for u in ast_nodes}
            embeddings_v = {v["id"]: self.get_or_compute_embedding(v, conn=conn) for v in wiki_nodes}

        linked_edges = []
        for u in ast_nodes:
            u_id = u["id"]
            emb_u = embeddings_u[u_id]
            for v in wiki_nodes:
                v_id = v["id"]
                emb_v = embeddings_v[v_id]
                metrics = self.compute_hybrid_metric(u, v, emb_u, emb_v)
                score = metrics["total_score"]
                if score >= threshold:
                    linked_edges.append({
                        "source_id": u_id,
                        "target_id": v_id,
                        "relation": relation,
                        "strength": round(score, 4),
                        "metrics": metrics
                    })
        return linked_edges

    def persist_nodes_and_edges(self, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]):
        """Persists nodes and edges into kg_nodes and kg_edges in vazus.db."""
        with self._get_connection() as conn:
            for n in nodes:
                emb = self.get_or_compute_embedding(n, conn=conn)
                props = {
                    "source_file": n.get("source_file", ""),
                    "community": n.get("community", 0),
                    "_origin": n.get("_origin", "unknown")
                }
                if "content" in n:
                    props["content"] = n["content"][:1000]

                conn.execute(
                    """
                    INSERT OR REPLACE INTO kg_nodes
                    (id, name, domain, node_type, description, tags, properties, embedding_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        n["id"],
                        n.get("name", ""),
                        n.get("domain", "general"),
                        n.get("node_type", "Node"),
                        n.get("description", "")[:500],
                        n.get("tags", ""),
                        json.dumps(props),
                        json.dumps(emb)
                    )
                )

            for e in edges:
                props_dict = dict(e.get("metrics") or e.get("properties") or {})
                props_dict["vector_dim"] = self.dim
                props_str = json.dumps(props_dict)
                conn.execute(
                    """
                    INSERT OR REPLACE INTO kg_edges
                    (source_id, target_id, relation, strength, properties)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        e["source_id"],
                        e["target_id"],
                        e.get("relation", "LINK"),
                        e.get("strength", 1.0),
                        props_str
                    )
                )
            conn.commit()

    def search_unified_vector_space(
        self,
        query: str,
        top_k: int = 10,
        domain_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Searches unified 768D vector space in vazus.db for both AST code nodes and Wiki note/section nodes."""
        return self.embedder.search_unified_vector_space(
            query=query,
            db_path=self.db_path,
            top_k=top_k,
            domain_filter=domain_filter
        )

    def get_supergraph_stats(self) -> Dict[str, int]:
        ast_nodes = self.load_ast_nodes()
        wiki_nodes = self.load_memory_wiki_nodes()
        with self._get_connection() as conn:
            db_nodes = conn.execute("SELECT count(*) FROM kg_nodes").fetchone()[0]
            db_edges = conn.execute("SELECT count(*) FROM kg_edges").fetchone()[0]

        return {
            "layer_a_nodes": len(ast_nodes),
            "layer_b_nodes": len(wiki_nodes),
            "db_nodes_count": db_nodes,
            "db_edges_count": db_edges,
            "total_edges": db_edges
        }

    def run_supergraph_integration(self, threshold: float = 0.15) -> Dict[str, Any]:
        """Runs full end-to-end SuperGraph integration across database/files."""
        ast_nodes = self.load_ast_nodes()
        wiki_nodes, wiki_edges = self.load_memory_wiki_nodes_and_edges()

        if not ast_nodes:
            ast_nodes = [{
                "id": "ast:vazus_core_supergraph_linker",
                "name": "supergraph_linker.py",
                "domain": "ast_code",
                "node_type": "Module",
                "description": "Unified SuperGraph & 768D Embeddings Integration module",
                "source_file": "vazus_core/supergraph_linker.py",
                "community": 1,
                "_origin": "ast",
                "tags": "ast,code,supergraph"
            }]

        if not wiki_nodes:
            wiki_nodes = [{
                "id": "wiki:AI_Lessons_and_Mistakes",
                "name": "AI Lessons and Mistakes",
                "domain": "memory_wiki",
                "node_type": "WikiNote",
                "description": "Knowledge memory on errors, architecture, and system rules",
                "content": "Central orchestrator and code intelligence system integration with 768D embeddings.",
                "source_file": "AI_Lessons_and_Mistakes.md",
                "community": 1,
                "_origin": "wiki",
                "tags": "wiki,memory,lessons"
            }]

        # Compute hybrid similarity edges between AST nodes and Wiki nodes
        hybrid_edges = self.link_nodes(ast_nodes, wiki_nodes, threshold=threshold)

        all_nodes = ast_nodes + wiki_nodes
        all_edges = wiki_edges + hybrid_edges

        self.persist_nodes_and_edges(all_nodes, all_edges)

        stats = self.get_supergraph_stats()

        wikilinks_count = sum(1 for e in wiki_edges if e.get("relation") == "WIKILINK")
        section_edges_count = sum(1 for e in wiki_edges if e.get("relation") == "CONTAINS_SECTION")

        wiki_notes_cnt = sum(1 for n in wiki_nodes if n.get("node_type") == "WikiNote")
        wiki_sections_cnt = sum(1 for n in wiki_nodes if n.get("node_type") == "WikiSection")

        return {
            "ast_nodes_count": len(ast_nodes),
            "wiki_notes_count": wiki_notes_cnt,
            "wiki_nodes_count": wiki_notes_cnt,
            "wiki_sections_count": wiki_sections_cnt,
            "wikilinks_count": wikilinks_count,
            "section_edges_count": section_edges_count,
            "edges_created": len(all_edges),
            "hybrid_edges_count": len(hybrid_edges),
            "vector_dim": self.dim,
            "db_stats": stats,
            "edges": hybrid_edges
        }
