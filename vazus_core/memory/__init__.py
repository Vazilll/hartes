"""vazus_core.memory — SQLite and Embedding Layer for vazus.db."""
from vazus_core.memory.db import get_db_connection, DB_PATH
from vazus_core.memory.embeddings import UnifiedEmbeddingManager
__all__ = ["get_db_connection", "DB_PATH", "UnifiedEmbeddingManager"]
