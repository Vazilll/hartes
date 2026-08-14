"""
tests/test_hyde_retrieval.py — Verification suite for Hypothetical Document Embeddings (HyDE).
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, "C:/vazus")

from vazus_core.hyde_retrieval import HyDERetriever
from vazus_core.memory.db import get_db_connection


def test_hyde_generate_hypothetical_document():
    retriever = HyDERetriever()
    
    # Code query
    doc_code = retriever.generate_hypothetical_document("def calculate_ast_pagerank")
    assert "Technical Specification" in doc_code
    assert "```python" in doc_code

    # ADR query
    doc_adr = retriever.generate_hypothetical_document("ADR for SQLite-vec vs Qdrant")
    assert "Architectural Decision Record" in doc_adr
    assert "Status: ACCEPTED" in doc_adr

    # General query
    doc_gen = retriever.generate_hypothetical_document("How does organic memory persist?")
    assert "Knowledge Insight" in doc_gen


def test_hyde_retrieval_flow(tmp_path):
    test_db = tmp_path / "test_hyde_vazus.db"
    conn = get_db_connection(test_db)
    
    # Populate dummy kg_nodes with 768D embeddings
    conn.execute("""
        CREATE TABLE IF NOT EXISTS kg_nodes (
            id TEXT PRIMARY KEY,
            name TEXT,
            domain TEXT,
            node_type TEXT,
            description TEXT,
            tags TEXT,
            properties TEXT,
            embedding_json TEXT
        )
    """)
    dummy_vec = [0.01] * 768
    conn.execute(
        "INSERT INTO kg_nodes (id, name, domain, node_type, description, tags, properties, embedding_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("node_ast_pagerank", "ASTRepoMapper", "code", "ASTModule", "Computes personalized PageRank on AST", "ast,pagerank", "{}", json.dumps(dummy_vec))
    )
    conn.commit()
    conn.close()

    retriever = HyDERetriever(db_path=test_db)
    results = retriever.retrieve("AST PageRank code map", top_k=5)
    
    assert isinstance(results, list)
    assert len(results) >= 1
    assert results[0]["id"] == "node_ast_pagerank"
    assert "hyde_dense_score" in results[0]
    assert results[0]["similarity"] > 0
