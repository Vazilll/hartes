#!/usr/bin/env python3
"""mem0 test with Ollama embeddings — zero torch dependency"""
import os, sys
from mem0 import Memory
from mem0.configs.base import MemoryConfig, LlmConfig, EmbedderConfig, VectorStoreConfig

print("Creating mem0 with Ollama backend...")
config = MemoryConfig(
    vector_store=VectorStoreConfig(
        provider="qdrant",
        config={
            "collection_name": "hermes_ollama_test",  # Fresh collection
            "path": "/c/dnts/pyenv/hermes-home/mem0_test",
            "embedding_model_dims": 768,  # nomic-embed-text
        }
    ),
    llm=LlmConfig(
        provider="ollama",
        config={
            "model": "qwen3:1.7b",  # Lightweight for LLM extraction
            "ollama_base_url": "http://localhost:11434",
        }
    ),
    embedder=EmbedderConfig(
        provider="ollama",
        config={
            "model": "nomic-embed-text",  # Dedicated embedding model
            "ollama_base_url": "http://localhost:11434",
        }
    ),
    version="v1.1",
)

m = Memory(config=config)

# Write test facts
print("\nWriting test facts...")
facts = [
    "Vaz prefers concise responses with tables",
    "gomcp Go MCP servers at C:/dnts/gomcp",
    "VPS at 213.165.36.252 with Postgres Langfuse Redis OpenSearch",
    "Pixel 10 projects: PIT 2.0 Flutter, OfflineHookChat",
    "Agy CLI v1.1.1 OAuth-based no API key",
    "Google ULTRA subscription Gemini models",
    "Frankenstein assembly find GitHub components first",
]
for f in facts:
    try:
        result = m.add(f, user_id="Vaz")
        print(f"  + {f[:45]}...")
    except Exception as e:
        print(f"  ✗ {f[:45]}... {str(e)[:60]}")

# Semantic search
print("\n=== SEMANTIC SEARCH ===")
for q in ["what VPS setup", "how to use agy", "what about Pixel 10", "preferred development"]:
    r = m.search(q, filters={"user_id": "Vaz"}, limit=2)
    results = r.get('results', [])
    if results:
        best = results[0]
        print(f"  '{q}' → [{best.get('score',0):.3f}] {best.get('memory','')[:70]}")
    else:
        print(f"  '{q}' → (none)")

stats = m.get_all(user_id="Vaz")
print(f"\nTotal memories: {len(stats)}")
m.close()
print("✅ DONE")
