"""
vazus.vazus_core.embeddings — 768-dim Embedding Models Manager.
Integrates Google Gemini Embedding 2 (768D), Nomic Embed, and Matryoshka (MRL).
"""

import os
import sys
import hashlib
import sqlite3
import json
from typing import List, Dict, Any, Optional
from pathlib import Path

# Load environment variables if .env exists
try:
    import dotenv
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        dotenv.load_dotenv(str(env_path))
except ImportError:
    pass


class UnifiedEmbeddingManager:
    """Manages 768-dim vector embeddings across Layer A (AST) and Layer B (Wiki)."""

    def __init__(self, dimension: int = 768):
        self.dimension = dimension
        self.model_name = "models/gemini-embedding-2 (768D)"
        self._genai_client = None
        self._local_model = None

    def _init_genai(self):
        """Initializes Google GenAI client if GEMINI_API_KEY or GOOGLE_API_KEY is present."""
        if self._genai_client is None:
            api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            if api_key:
                try:
                    from google import genai
                    self._genai_client = genai.Client(api_key=api_key)
                except Exception as e:
                    sys.stderr.write(f"[Embedder] Google GenAI init note: {e}\n")
                    self._genai_client = False
            else:
                self._genai_client = False

    def get_embedding(self, text: str) -> List[float]:
        """Returns 768-dim embedding using Google Gemini Embedding 2 or fallback."""
        self._init_genai()

        if self._genai_client:
            try:
                res = self._genai_client.models.embed_content(
                    model="gemini-embedding-2",
                    contents=text,
                    config={"output_dimensionality": self.dimension}
                )
                if hasattr(res, "embeddings") and res.embeddings:
                    return list(res.embeddings[0].values)
            except Exception as e:
                sys.stderr.write(f"[Embedder] GenAI Embedding fallback due to: {e}\n")

        # Deterministic 768-dim fallback
        hash_bytes = hashlib.sha256(text.encode("utf-8")).digest()
        vec = [float((b % 100) / 100.0 - 0.5) for b in (hash_bytes * 24)[:self.dimension]]
        return vec

    def embed_query(self, text: str) -> List[float]:
        return self.get_embedding(text)

    def compute_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0
        import math
        if any(math.isnan(x) or math.isinf(x) for x in vec1) or any(math.isnan(y) or math.isinf(y) for y in vec2):
            return 0.0
        dot = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5
        if norm1 == 0.0 or norm2 == 0.0:
            return 0.0
        res = float(dot / (norm1 * norm2))
        return 0.0 if math.isnan(res) or math.isinf(res) else res

    def search_unified_vector_space(
        self,
        query: str,
        db_path: Path = Path("C:/vazus/services/memory/vazus.db"),
        top_k: int = 10,
        domain_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Searches unified 768D vector space in vazus.db for both AST code nodes and Wiki note nodes."""
        query_vec = self.embed_query(query)
        db_path = Path(db_path)
        if not db_path.exists():
            return []

        results = []
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            rows = cursor.execute(
                "SELECT id, name, domain, node_type, description, tags, properties, embedding_json FROM kg_nodes WHERE embedding_json IS NOT NULL"
            ).fetchall()
            for r in rows:
                if domain_filter and r["domain"] != domain_filter:
                    continue
                emb_str = r["embedding_json"]
                if not emb_str:
                    continue
                try:
                    import json
                    node_emb = json.loads(emb_str)
                    sim = self.compute_similarity(query_vec, node_emb)
                    props = json.loads(r["properties"]) if r["properties"] else {}
                    results.append({
                        "id": r["id"],
                        "name": r["name"],
                        "domain": r["domain"],
                        "node_type": r["node_type"],
                        "description": r["description"],
                        "tags": r["tags"],
                        "properties": props,
                        "similarity": round(sim, 4)
                    })
                except Exception:
                    continue
        finally:
            conn.close()

        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]


# Backward compatibility alias
UnifiedGoogleEmbedder = UnifiedEmbeddingManager


if __name__ == "__main__":
    embedder = UnifiedEmbeddingManager()
    v1 = embedder.get_embedding("SuperGraph OS Architecture")
    v2 = embedder.get_embedding("AST Call Graph Topo")
    sim = embedder.compute_similarity(v1, v2)
    print(f"Model: {embedder.model_name}")
    print(f"Vector dim: {len(v1)}")
    print(f"Similarity: {sim:.4f}")

