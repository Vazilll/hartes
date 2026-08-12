import sys
import os
from pathlib import Path

sys.path.insert(0, r"C:\vazus")
sys.stdout.reconfigure(encoding='utf-8')

from vazus_core.embeddings import UnifiedEmbeddingManager

embedder = UnifiedEmbeddingManager()
results = embedder.search_unified_vector_space('тест', db_path=Path('C:/vazus/vazus.db'), top_k=5)
print(f"Found {len(results)} results:")
for r in results:
    print(f" - [{r['node_type']}] {r['name']} (similarity: {r['similarity']})")
    p = r.get('properties', {})
    if p:
        src = p.get('source_file') or p.get('message_id')
        print(f"   Source: {src}")
        if 'start_sec' in p:
            print(f"   Time: {p.get('start_sec')}s - {p.get('end_sec')}s | Thumb: {p.get('thumbnail_path')}")
        text = p.get('transcript') or p.get('text') or r.get('description', '')
        print(f"   Snippet: {text[:120]}...")
