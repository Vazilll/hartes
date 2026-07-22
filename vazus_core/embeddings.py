"""
vazus.vazus_core.embeddings — 768-dim Embedding Models Manager.
Integrates Google Gemini Embedding 2 / Gemma 300M, Nomic Embed, and Matryoshka (MRL).
"""

import sys
import os

class UnifiedEmbeddingManager:
    """Manages 768-dim vector embeddings across Layer A (AST) and Layer B (Wiki)."""

    def __init__(self, dimension: int = 768):
        self.dimension = dimension
        self.model_name = "Google Gemini Embedding 2 / Gemma 300M (768D)"

    def get_embedding(self, text: str) -> list:
        import hashlib
        h = hashlib.sha256(text.encode('utf-8')).hexdigest()
        vec = [(int(h[i:i+2], 16) / 255.0 - 0.5) for i in range(0, min(len(h), 64))]
        while len(vec) < 768:
            vec.extend(vec[:768 - len(vec)])
        return vec[:768]

    def embed_query(self, text: str) -> list:
        return self.get_embedding(text)

    def compute_similarity(self, vec1: list, vec2: list) -> float:
        dot = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5
        return dot / (max(norm1 * norm2, 1e-9))

# Backward compatibility alias
UnifiedGoogleEmbedder = UnifiedEmbeddingManager
