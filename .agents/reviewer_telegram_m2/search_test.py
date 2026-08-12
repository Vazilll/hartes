import sys
sys.path.insert(0, 'C:/vazus')
sys.stdout.reconfigure(encoding='utf-8')
from vazus_core.embeddings import UnifiedEmbeddingManager

embedder = UnifiedEmbeddingManager()
res = embedder.search_unified_vector_space('Покоритель Наташек', domain_filter='telegram_discussion', top_k=3)
print(f"Found {len(res)} results:")
for r in res:
    print(f"- ID: {r['id']} | Name: {r['name']} | Sim: {r['similarity']}")
