"""
vazus_core.rust_embedder_bridge — PyO3 Rust embedding bridge with Python fallback.
Drops GIL during inference for true parallelism.
"""
from typing import List, Tuple
from vazus_core.memory.embeddings import UnifiedEmbeddingManager as _mgr

try:
    from vazus_embedder import embed_texts, cosine_similarity, batch_top_k
    RUST_AVAILABLE = True
except ImportError:
    embed_texts = None
    RUST_AVAILABLE = False

try:
    import cosine_simd_rs
    SIMD_AVAILABLE = True
except ImportError:
    cosine_simd_rs = None
    SIMD_AVAILABLE = False


class EmbedderBridge:
    def __init__(self):
        self._python_mgr = _mgr(dimension=768)

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if RUST_AVAILABLE and embed_texts is not None:
            return embed_texts(texts)
        return [self._python_mgr.get_embedding(t) for t in texts]

    def cosine_similarity(self, a: List[float], b: List[float]) -> float:
        if RUST_AVAILABLE:
            return cosine_similarity(a, b)
        if SIMD_AVAILABLE and cosine_simd_rs is not None:
            try:
                return float(cosine_simd_rs.cosine_similarity(a, b))
            except Exception:
                pass
        return self._python_mgr.compute_similarity(a, b)

    def batch_top_k(self, query: List[float], corpus: List[List[float]], k: int) -> List[Tuple[int, float]]:
        if RUST_AVAILABLE:
            return batch_top_k(query, corpus, k)
        if SIMD_AVAILABLE and cosine_simd_rs is not None:
            try:
                return [(int(idx), float(score)) for idx, score in cosine_simd_rs.batch_top_k(query, corpus, k)]
            except Exception:
                pass
        
        scores = [(i, self._python_mgr.compute_similarity(query, c)) for i, c in enumerate(corpus)]
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:k]

