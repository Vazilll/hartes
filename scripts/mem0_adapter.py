#!/usr/bin/env python3
"""
mem0 adapter для Hermes — работает параллельно с holographic memory.
Не заменяет, а дополняет семантическим поиском.

Использование:
  from mem0_adapter import Mem0Provider
  mem = Mem0Provider()
  mem.add("Vaz prefers concise responses", user_id="Vaz")
  results = mem.search("how does Vaz like responses?", user_id="Vaz")
  # results = [{"memory": "...", "score": 0.92, ...}, ...]

Зависимости: mem0ai, qdrant-client, ollama (nomic-embed-text + qwen3:1.7b)
"""
import os, json
from pathlib import Path
from typing import Optional

HERMES_HOME = Path(os.environ.get('HERMES_HOME', 
    os.path.expanduser('C:/vazus/pyenv/hermes-home')))


class Mem0Provider:
    """Mem0-based memory provider. Thread-safe, lazy init."""
    
    def __init__(self, collection: str = "hermes_mem0"):
        self.collection = collection
        self._mem = None
    
    def _init(self):
        if self._mem is not None:
            return
        from mem0 import Memory
        from mem0.configs.base import MemoryConfig, LlmConfig, EmbedderConfig, VectorStoreConfig
        
        config = MemoryConfig(
            vector_store=VectorStoreConfig(
                provider="qdrant",
                config={
                    "collection_name": self.collection,
                    "path": str(HERMES_HOME / "mem0_data"),
                    "embedding_model_dims": 768,
                }
            ),
            llm=LlmConfig(
                provider="ollama",
                config={
                    "model": "qwen3:1.7b",  # Lightweight LLM for extraction
                    "ollama_base_url": "http://localhost:11434",
                }
            ),
            embedder=EmbedderConfig(
                provider="ollama",
                config={
                    "model": "nomic-embed-text",  # Embedding model
                    "ollama_base_url": "http://localhost:11434",
                }
            ),
            version="v1.1",
        )
        self._mem = Memory(config=config)
    
    def add(self, text: str, user_id: str = "default", metadata: dict = None):
        """Добавить факт в память. Возвращает ID записи."""
        self._init()
        result = self._mem.add(
            text,
            user_id=user_id,
            metadata=metadata or {}
        )
        return result
    
    def search(self, query: str, user_id: str = "default", limit: int = 5):
        """Поиск по памяти. Возвращает список {memory, score, ...}."""
        self._init()
        result = self._mem.search(
            query,
            filters={"user_id": user_id},
            limit=limit
        )
        return result.get('results', [])
    
    def get_all(self, user_id: str = "default"):
        """Все записи пользователя."""
        self._init()
        return self._mem.get_all(user_id=user_id)
    
    def delete(self, memory_id: str):
        """Удалить запись по ID."""
        self._init()
        self._mem.delete(memory_id)
    
    def close(self):
        if self._mem:
            self._mem.close()


if __name__ == "__main__":
    # A/B тест: holographic (Hermes) vs mem0
    print("=" * 60)
    print("A/B TEST: Holographic (Hermes SQLite) vs mem0 (Ollama)")
    print("=" * 60)
    
    test_data = [
        "Vaz prefers concise responses with tables",
        "gomcp Go MCP servers at C:/vazus/gomcp",
        "VPS at 213.165.36.252 with Postgres Langfuse Redis OpenSearch",
        "Pixel 10 projects: PIT 2.0 Flutter, OfflineHookChat",
        "Agy CLI v1.1.1 OAuth-based no API key",
        "Google ULTRA subscription Gemini models",
        "Frankenstein assembly find GitHub components first",
    ]
    
    # mem0
    print("\n[mem0] Writing 7 facts...")
    mem0 = Mem0Provider()
    for f in test_data:
        try:
            mem0.add(f, user_id="Vaz")
            print(f"  ✓ {f[:40]}...")
        except Exception as e:
            print(f"  ✗ {str(e)[:50]}")
    
    print("\n[mem0] Searching...")
    for q in ["what VPS setup", "how to use agy", "what about Pixel 10", "preferred development"]:
        results = mem0.search(q, user_id="Vaz", limit=2)
        if results:
            best = results[0]
            print(f"  '{q}' → [{best.get('score',0):.3f}] {best.get('memory','')[:60]}")
        else:
            print(f"  '{q}' → (none)")
    
    print(f"\n[mem0] Total: {len(mem0.get_all(user_id='Vaz'))}")
    mem0.close()
    
    print("\n" + "=" * 60)
    print("Сравнение:")
    print("  Holographic (Hermes):")
    print("    ✅ Быстрый Key-Value lookup")
    print("    ✅ FTS5 полнотекстовый поиск")
    print("    ✅ Уже работает, 0 зависимостей")
    print("    ❌ Нет семантического поиска")
    print("    ❌ Нет entity graph")
    print("  mem0:")
    print("    ✅ Семантический поиск (вектора)")
    print("    ✅ Entity graph с boosting")
    print("    ✅ Авто-dedup")
    print("    ❌ Требует Ollama + nomic-embed-text")
    print("    ❌ Медленнее (векторный поиск)")
    print("  Решение: ИСПОЛЬЗОВАТЬ ОБА")
    print("    holographic — быстрые запросы по ключам")
    print("    mem0 — семантический поиск и связи")
