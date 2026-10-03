"""
vazus_core/embeddings.py — 768-dim Vector Embeddings Facade.
Re-exports canonical implementations from vazus_core.memory.embeddings.
"""

from vazus_core.memory.embeddings import (
    EmbeddingMicroBatcher,
    OpenVINONPUEmbedder,
    UnifiedEmbeddingManager,
    compute_similarity,
    get_embedding,
    get_embedding_manager,
)

__all__ = [
    "UnifiedEmbeddingManager",
    "OpenVINONPUEmbedder",
    "EmbeddingMicroBatcher",
    "get_embedding_manager",
    "get_embedding",
    "compute_similarity",
]
