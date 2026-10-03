"""
vazus_core/organic_memory_bridge.py — Organic memory bridge facade.
Re-exports canonical implementations from vazus_core.memory.organic_memory_bridge.
"""

from vazus_core.memory.organic_memory_bridge import (
    DB_PATH,
    get_organic_summary,
    query_vector_memory,
    recommend_wikilinks,
    record_code_optimization,
    record_insight,
    search_memory,
    search_memory_semantic,
)

__all__ = [
    "record_insight",
    "search_memory",
    "search_memory_semantic",
    "record_code_optimization",
    "get_organic_summary",
    "recommend_wikilinks",
    "query_vector_memory",
    "DB_PATH",
]
