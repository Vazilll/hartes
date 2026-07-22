import sys
import os
sys.path.insert(0, r"C:\vazus")
sys.path.insert(0, r"C:\vazus\scripts")
#!/usr/bin/env python3
"""mem0 test with HuggingFace embeddings - safe local execution"""
import os, sys
from mem0 import Memory
from mem0.configs.base import MemoryConfig, LlmConfig, EmbedderConfig, VectorStoreConfig

# Get API key for LLM (opencode-go)
key = open(r'C:\vazus\pyenv\hermes-home\.env').read().split('OPENCODE_GO_API_KEY=')[1].split('\n')[0].strip()
os.environ['OPENAI_API_KEY'] = key

print("Creating mem0 with HuggingFace embedding...")
config = MemoryConfig(
    vector_store=VectorStoreConfig(
        provider="qdrant",
        config={
            "collection_name": "hermes_test",
            "path": "/c/dnts/pyenv/hermes-home/mem0_test",
            "embedding_model_dims": 384,
        }
    ),
    llm=LlmConfig(
        provider="openai",
        config={
            "model": "deepseek-v4-flash",
            "openai_base_url": "https://opencode.ai/zen/go/v1",
        }
    ),
    embedder=EmbedderConfig(
        provider="huggingface",
        config={"model": "sentence-transformers/all-MiniLM-L6-v2"}
    ),
    version="v1.1",
)

m = Memory(config=config)

# Write test data
print("\nWriting 7 test facts...")
facts = [
    "Vaz prefers concise responses with tables",
    "gomcp Go MCP servers at C:/vazus/gomcp",
    "VPS at 213.165.36.252 with Postgres Langfuse Redis OpenSearch",
    "Pixel 10 projects: PIT 2.0 Flutter, OfflineHookChat",
    "Agy CLI v1.1.1 OAuth-based no API key",
    "Google ULTRA subscription Gemini models",
    "Frankenstein assembly find GitHub components first",
]
for f in facts:
    result = m.add(f, user_id="Vaz")
    print(f"  + {f[:45]}...")

# Semantic search
print("\n=== SEMANTIC SEARCH ===")
queries = [
    ("what VPS setup", "vps"),
    ("how to use agy", "agy"),
    ("what about Pixel 10", "pixel"),  
    ("preferred development approach", "approach"),
]
for q, tag in queries:
    r = m.search(q, user_id="Vaz", limit=2)
    results = r.get('results', [])
    if results:
        best = results[0]
        print(f"  '{q}' → [{best.get('score',0):.3f}] {best.get('memory','')[:70]}")
    else:
        print(f"  '{q}' → (none)")

# Compare with exact match
print("\n=== EXACT MATCH ===")
for tag, fact in [("vps", "VPS"), ("agy", "Agy"), ("pixel", "Pixel")]:
    r = m.search(tag, user_id="Vaz", limit=2)
    results = r.get('results', [])
    if results:
        best = results[0]
        print(f"  '{tag}' → [{best.get('score',0):.3f}] {best.get('memory','')[:70]}")
    else:
        print(f"  '{tag}' → (none)")

# Total
print(f"\nTotal memories in store: {len(m.get_all(user_id='Vaz'))}")
m.close()
print("✅ DONE")
