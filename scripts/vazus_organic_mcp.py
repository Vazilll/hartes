#!/usr/bin/env python3
"""
vazus_core.vazus_organic_mcp — FastMCP Server providing session auto-recall, organic memory logging, AST pruning, SMT Z3 verification, and Darwinian evolution.
"""

import sys
import json
import os
import logging

os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr = open(os.devnull, "w", encoding="utf-8")
sys.path.insert(0, "C:/vazus")


logging.getLogger("fastmcp").setLevel(logging.ERROR)
logging.getLogger("mcp").setLevel(logging.ERROR)

from fastmcp import FastMCP
from vazus_core.memory.organic_memory_bridge import search_memory, record_insight
from vazus_core.memory.embeddings import get_embedding_manager
from vazus_core.verification.ast_pruner import ASTPruner
from vazus_core.evolution.darwinian_evolver import run_evolution_cycle
from vazus_core.verification.smt_z3_verifier import SMTZ3Verifier

MCP = FastMCP("vazus-organic")


@MCP.tool(description="Search 768D vector space and FTS5 knowledge graph in vazus.db for past memory insights, ADRs, and code benchmarks.")
def vazus_organic_recall(query: str, top_k: int = 5) -> str:
    mgr = get_embedding_manager()
    results = mgr.search_unified_vector_space(query, top_k=top_k)
    if not results:
        mem_results = search_memory(query, limit=top_k)
        return json.dumps(mem_results, ensure_ascii=False, indent=2, default=str)
    return json.dumps(results, ensure_ascii=False, indent=2, default=str)

@MCP.tool(description="Record a verified memory insight, code optimization, or architectural lesson into vazus.db organic memory.")
def vazus_record_insight(category: str, insight: str) -> str:
    res = record_insight(category, insight)
    return json.dumps(res, ensure_ascii=False, indent=2, default=str)

@MCP.tool(description="Prune Python file or code string AST bodies, returning compressed code signatures with docstrings (>75% token reduction).")
def vazus_ast_prune(code_or_file: str, docstring_mode: str = "summary") -> str:
    if os.path.exists(code_or_file):
        pruned_code, stats = ASTPruner.prune_file(code_or_file, log_memory=True, docstring_mode=docstring_mode)
    else:
        pruned_code, stats = ASTPruner.prune_code_string(code_or_file, docstring_mode=docstring_mode)
    return json.dumps({"pruned_code": pruned_code, "stats": stats}, ensure_ascii=False, indent=2, default=str)

@MCP.tool(description="Run a Darwinian evolution cycle on a codebase module: genetic mutation, pytest fitness scoring, crossover, and memory update.")
def vazus_darwinian_evolve(target_module: str = "vazus_core", generations: int = 2) -> str:
    res = run_evolution_cycle(target_module, generations=generations)
    return json.dumps(res, ensure_ascii=False, indent=2, default=str)

@MCP.tool(description="Perform formal SMT Z3 contract verification and memory safety bounds checking on Python code proposals.")
def vazus_smt_z3_verify(code: str, depth: int = 10) -> str:
    verifier = SMTZ3Verifier(depth=depth)
    res = verifier.verify_code_contracts(code=code, depth=depth)
    return json.dumps(res, ensure_ascii=False, indent=2, default=str)


# ── mem0 Persistent Fact Memory ─────────────────────────────────────────────

from vazus_core.memory.mem0_memory_engine import Mem0Engine

@MCP.tool(description="Add or update a persistent user fact/preference/entity into mem0 memory (vazus.db mem0_facts table). Supports deduplication.")
def vazus_mem0_add_fact(fact_text: str, category: str = "user_preference", entity: str = "user") -> str:
    mem0 = Mem0Engine()
    res = mem0.add_fact(fact_text, category=category, entity=entity)
    return json.dumps(res, ensure_ascii=False, indent=2, default=str)

@MCP.tool(description="Search mem0 persistent facts by 768D vector similarity. Returns top-k matching user preferences, entities, and contextual facts.")
def vazus_mem0_search(query: str, top_k: int = 5) -> str:
    mem0 = Mem0Engine()
    results = mem0.search_facts(query, top_k=top_k)
    return json.dumps(results, ensure_ascii=False, indent=2, default=str)


# ── Autonomous Skill Authoring ──────────────────────────────────────────────

from vazus_core.integrations.skill_author import create_autonomous_skill

@MCP.tool(description="Autonomously create a new SKILL.md file and register it in vazus.db skill_registry. Use after solving a complex problem to persist the workflow as a reusable skill.")
def vazus_author_skill(skill_name: str, description: str, instructions_markdown: str, category: str = "Vazus Auto-Extracted") -> str:
    res = create_autonomous_skill(skill_name, description, instructions_markdown, category)
    return json.dumps(res, ensure_ascii=False, indent=2, default=str)


# ── Codebase & Repository Vector Indexing ───────────────────────────────────

from vazus_core.integrations.repo_indexer import index_repository

@MCP.tool(description="Index a repository or codebase directory into Vazus OS 768D vector space and AST memory (workspace_ast_nodes, kg_nodes in vazus.db). Scans files, prunes AST signatures, and computes vector embeddings.")
def vazus_index_repository(directory_path: str, project_name: str = "vazus", max_files: int = 500) -> str:
    res = index_repository(directory_path=directory_path, project_name=project_name, max_files=max_files)
    return json.dumps(res, ensure_ascii=False, indent=2, default=str)


if __name__ == "__main__":
    MCP.run(transport="stdio", show_banner=False)
