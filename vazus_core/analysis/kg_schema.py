"""
vazus_core.analysis.kg_schema — Shared KG schema DDL (extracted from Type-1 clone).

Previously duplicated identically in:
  - vazus_core.integrations.telegram_indexer:467-489
  - vazus_core.memory.multimodal_knowledge:692-714

Both modules now import from here.
"""
from __future__ import annotations

KG_NODES_DDL = """
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
"""

KG_EDGES_DDL = """
CREATE TABLE IF NOT EXISTS kg_edges (
    source_id TEXT,
    target_id TEXT,
    relation TEXT,
    strength REAL,
    properties TEXT,
    PRIMARY KEY (source_id, target_id, relation)
);
"""

KG_INSERT_NODE_SQL = """
INSERT OR REPLACE INTO kg_nodes (
    id, name, domain, node_type, description, tags, properties, embedding_json
) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
"""

KG_INSERT_EDGE_SQL = """
INSERT OR REPLACE INTO kg_edges (
    source_id, target_id, relation, strength, properties
) VALUES (?, ?, ?, ?, ?)
"""


def ensure_kg_schema(cursor) -> None:
    """Create kg_nodes and kg_edges tables if they don't exist."""
    cursor.execute(KG_NODES_DDL)
    cursor.execute(KG_EDGES_DDL)
