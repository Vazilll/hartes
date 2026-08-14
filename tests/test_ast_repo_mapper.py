"""
tests/test_ast_repo_mapper.py — Verification suite for PageRank ASTRepoMapper and Bi-temporal Mem0.
"""

import sys
from pathlib import Path

sys.path.insert(0, "C:/vazus")

from vazus_core.engine.ast_repo_mapper import ASTRepoMapper
from vazus_core.memory.mem0_memory_engine import Mem0Engine


def test_ast_repo_mapper_extract_symbols(tmp_path):
    sample_file = tmp_path / "sample.py"
    sample_file.write_text("""
class SampleService:
    def process_data(self, item: str) -> bool:
        return True

def standalone_helper(x, y):
    return x + y
""", encoding="utf-8")

    mapper = ASTRepoMapper(root_dir=tmp_path)
    defs, refs, skel = mapper.extract_symbols(sample_file)

    assert "SampleService" in defs
    assert "standalone_helper" in defs
    assert "SampleService.process_data" in defs
    assert "def standalone_helper" in skel


def test_ast_repo_mapper_build_repo_map():
    mapper = ASTRepoMapper()
    repo_map = mapper.build_repo_map(active_files=["vazus_core/memory"], max_tokens=1500)

    assert "Active AST Repo Map" in repo_map
    assert "vazus_core" in repo_map
    assert len(repo_map) <= 1500 * 4


def test_mem0_bitemporal_and_rrf(tmp_path):
    test_db = str(tmp_path / "test_mem0.db")
    mem0 = Mem0Engine(db_path=test_db)

    # 1. Add initial fact
    r1 = mem0.add_fact("User prefers dark theme", category="ui_pref", entity="user")
    assert r1["status"] in ("ADDED", "UPDATED")

    # 2. Add contradictory / updated fact
    r2 = mem0.add_fact("User prefers dark theme with high contrast", category="ui_pref", entity="user")
    assert r2["status"] in ("ADDED", "UPDATED")

    # 3. Search facts with RRF
    results = mem0.search_facts("dark theme contrast", top_k=3)
    assert len(results) >= 1
    assert "dark theme" in results[0]["fact_text"].lower()
    assert "rrf_score" in results[0]
