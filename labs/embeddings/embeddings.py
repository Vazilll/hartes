"""
vazus_core.embeddings — Двухуровневый векторный граф на технологиях Google DeepMind.
Чистая in-process архитектура без HTTP-серверов и сетевых портов.
Размерность: 768 dim.
"""
import json
import sys
import hashlib
from typing import List
from vazus_core.config import settings

class UnifiedGoogleEmbedder:
    """Универсальный векторизатор Google DeepMind (768-dim)."""

    def __init__(self):
        self.dim = settings.EMBEDDING_DIM
        self._local_model = None

    def _init_local(self):
        if self._local_model is None:
            try:
                from sentence_transformers import SentenceTransformer
                sys.stderr.write(f"[Embedder] Loading local DeepMind model: {settings.EMBEDDING_MODEL_LOCAL}...\n")
                self._local_model = SentenceTransformer(settings.EMBEDDING_MODEL_LOCAL)
            except Exception as e:
                sys.stderr.write(f"[Embedder] Notice: sentence-transformers not loaded ({e}). Using deterministic 768 vector.\n")
                self._local_model = "fallback"

    def embed_query(self, text: str) -> List[float]:
        """Возвращает вектор размерностью 768 без HTTP-вызовов."""
        self._init_local()
        if self._local_model != "fallback":
            try:
                vec = self._local_model.encode(text, normalize_embeddings=True)
                return vec.tolist()
            except Exception:
                pass
                
        # Deterministic 768-dim vector fallback
        hash_bytes = hashlib.sha256(text.encode("utf-8")).digest()
        vec = [float((b % 100) / 100.0) for b in (hash_bytes * 24)[:self.dim]]
        return vec
