"""
tests.unit.test_j_space_tool_indexer
====================================
Модульные тесты для J-Space Tool Indexer (vazus_core.memory.j_space_tool_indexer):
- Проверка сканирования MCP схем и каталога нативных модулей Vazus OS.
- Проверка индексации 768D L2-векторов в j_space_vectors и метаданных.
- Проверка семантического поиска инструментов по запросам:
  * "запусти изолированную песочницу" -> vazus-sandbox
  * "сделай бэкап базы" -> db_backup
"""

import pytest
import sqlite3
import numpy as np
from pathlib import Path

from vazus_core.memory.j_space_vector_index import JSpaceVectorIndex
from vazus_core.memory.j_space_tool_indexer import (
    JSpaceToolIndexer,
    ToolSpec,
    stem_word,
    NATIVE_MODULES_CATALOG,
)


@pytest.fixture
def isolated_db(tmp_path):
    """Изолированная база данных SQLite для тестирования."""
    db_file = tmp_path / "test_vazus.db"
    return str(db_file)


@pytest.fixture
def mock_mcp_dir(tmp_path):
    """Создает временную структуру MCP схем для тестов."""
    mcp_root = tmp_path / "mcp"
    server_dir = mcp_root / "test-server"
    server_dir.mkdir(parents=True, exist_ok=True)

    tool_json = server_dir / "test_action.json"
    tool_json.write_text(
        '{"name": "test_action", "description": "Тестовое действие для валидации схемы.", "parameters": {"properties": {"target": {"type": "string"}}}}',
        encoding="utf-8",
    )
    return mcp_root


class DummyEmbeddingManager:
    """Детерминированный легковесный менеджер эмбеддингов для быстрых unit-тестов."""

    def __init__(self, dimension: int = 768):
        self.dimension = dimension

    def get_embedding(self, text: str) -> list[float]:
        if not text or not text.strip():
            return [0.0] * self.dimension
        import hashlib
        import re
        vec = np.zeros(self.dimension, dtype=np.float32)
        words = [stem_word(w.lower()) for w in re.findall(r"\w+", text) if w]
        for w in words:
            if not w:
                continue
            h = int(hashlib.md5(w.encode("utf-8")).hexdigest()[:8], 16) % self.dimension
            vec[h] += 1.0
        norm = np.linalg.norm(vec)
        if norm > 1e-6:
            vec = vec / norm
        return vec.tolist()

    def compute_similarity(self, v1: list[float], v2: list[float]) -> float:
        a = np.asarray(v1, dtype=np.float32)
        b = np.asarray(v2, dtype=np.float32)
        na = np.linalg.norm(a)
        nb = np.linalg.norm(b)
        if na == 0 or nb == 0:
            return 0.0
        return float(np.dot(a, b) / (na * nb))


def test_stem_word():
    assert stem_word("песочницу") == "песочн"
    assert stem_word("песочница") == "песочн"
    assert stem_word("базы") == "баз"
    assert stem_word("база") == "баз"
    assert stem_word("изолированную") == "изолирован"
    assert stem_word("running") == "runn"
    assert stem_word("") == ""


def test_native_catalog_contains_required_modules():
    native_names = {t.name for t in NATIVE_MODULES_CATALOG}
    required_tools = [
        "vazus-sandbox",
        "sandbox_launch",
        "sandbox_action",
        "sandbox_capture",
        "sandbox_terminate",
        "wsb_sandbox_controller",
        "vazus-organic",
        "vazus_record_insight",
        "vazus_update_reactive_parameter",
        "vazus_mem0_add_fact",
        "vazus_mem0_search",
        "cbm",
        "get_code_snippet",
        "search_graph",
        "get_architecture",
        "code-quality",
        "ast_grep_search",
        "pyinstrument_profile",
        "radon_complexity",
        "db_backup",
        "run_backup",
        "get_backup_status",
        "dream_consolidator",
        "run_dream_consolidation",
        "desktop-commander",
        "list_processes",
        "start_process",
        "read_process_output",
        "interact_with_process",
        "telegram-mcp",
        "tg_search_dialogs",
        "tg_get_history",
        "tg_download_media",
    ]
    for req in required_tools:
        assert req in native_names, f"Tool {req} must be in NATIVE_MODULES_CATALOG"


def test_indexer_initialization(isolated_db, mock_mcp_dir):
    dummy_mgr = DummyEmbeddingManager()
    indexer = JSpaceToolIndexer(db_path=isolated_db, mcp_dir=str(mock_mcp_dir), embedding_manager=dummy_mgr)

    conn = sqlite3.connect(isolated_db)
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    conn.close()

    assert "j_space_vectors" in tables
    assert "j_space_tool_metadata" in tables


def test_mcp_scanning_and_collecting(isolated_db, mock_mcp_dir):
    dummy_mgr = DummyEmbeddingManager()
    indexer = JSpaceToolIndexer(db_path=isolated_db, mcp_dir=str(mock_mcp_dir), embedding_manager=dummy_mgr)

    tools = indexer.collect_all_tools()
    tool_names = [t.name for t in tools]

    assert "test_action" in tool_names
    assert "vazus-sandbox" in tool_names
    assert "db_backup" in tool_names


def test_indexing_and_vector_count(isolated_db, mock_mcp_dir):
    dummy_mgr = DummyEmbeddingManager()
    indexer = JSpaceToolIndexer(db_path=isolated_db, mcp_dir=str(mock_mcp_dir), embedding_manager=dummy_mgr)

    stats = indexer.index_tools(force_reindex=True)
    assert stats["indexed_count"] > 0

    count = indexer.vector_index.count(source="tool_catalog")
    assert count == stats["indexed_count"]


def test_find_tools_for_query_sandbox(isolated_db, mock_mcp_dir):
    dummy_mgr = DummyEmbeddingManager()
    indexer = JSpaceToolIndexer(db_path=isolated_db, mcp_dir=str(mock_mcp_dir), embedding_manager=dummy_mgr)
    indexer.index_tools(force_reindex=True)

    results = indexer.find_tools_for_query("запусти изолированную песочницу", top_k=3, min_similarity=0.35)
    assert len(results) > 0

    top_modules = [r["module"] for r in results]
    top_tools = [r["tool_name"] for r in results]

    assert "vazus-sandbox" in top_modules or any("sandbox" in t for t in top_tools)
    assert results[0]["similarity"] >= 0.35


def test_find_tools_for_query_backup(isolated_db, mock_mcp_dir):
    dummy_mgr = DummyEmbeddingManager()
    indexer = JSpaceToolIndexer(db_path=isolated_db, mcp_dir=str(mock_mcp_dir), embedding_manager=dummy_mgr)
    indexer.index_tools(force_reindex=True)

    results = indexer.find_tools_for_query("сделай бэкап базы", top_k=3, min_similarity=0.35)
    assert len(results) > 0

    top_modules = [r["module"] for r in results]
    top_tools = [r["tool_name"] for r in results]

    assert "db_backup" in top_modules or any("backup" in t for t in top_tools)
    assert results[0]["similarity"] >= 0.35


def test_empty_query_returns_empty(isolated_db, mock_mcp_dir):
    dummy_mgr = DummyEmbeddingManager()
    indexer = JSpaceToolIndexer(db_path=isolated_db, mcp_dir=str(mock_mcp_dir), embedding_manager=dummy_mgr)
    indexer.index_tools(force_reindex=True)

    assert indexer.find_tools_for_query("") == []
    assert indexer.find_tools_for_query("   ") == []
