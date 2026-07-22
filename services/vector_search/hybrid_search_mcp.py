#!/usr/bin/env python3
"""dnts-hybrid-search MCP — Fast hybrid search server.

Combines three signals:
  • SQLite FTS5      — keyword search over all indexed documents
  • CBM graph        — AST/semantic code graph from codebase-memory-mcp
  • LEANN daemon     — sentence-transformers semantic search via HTTP :5010

Result is multi-signal reranked and deduplicated.
"""
import sys
import json

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
sys.path.insert(0, "C:/vazus/pyenv")

from fastmcp import FastMCP
from vazus_core.workers import hybrid

MCP = FastMCP("dnts-hybrid-search")


@MCP.tool(description=(
    "Full hybrid search: SQLite FTS5 + CBM code graph + LEANN semantic (daemon :5010). "
    "Multi-signal reranked. Best general-purpose search tool."
))
def hybrid_search(query: str, limit: int = 10) -> str:
    result = hybrid.run(query, limit=limit)
    return result["result"]


@MCP.tool(description=(
    "SQLite FTS5 keyword search only. Fast, no ML. "
    "Good for exact term matching across all indexed documents."
))
def fts_search(query: str, limit: int = 10) -> str:
    results = hybrid.sqlite_search(query, limit)
    if not results:
        return f"No FTS results for: {query!r}"
    lines = [f"FTS results for: {query!r}\n"]
    for i, r in enumerate(results, 1):
        txt = r.get("text", "")[:300]
        src = r.get("source", "?")
        lines.append(f"{i}. [{src}] {txt}\n")
    return "\n".join(lines)


@MCP.tool(description=(
    "LEANN semantic search only via HTTP daemon (:5010). "
    "Understands meaning, not just keywords. ~2s response time."
))
def leann_search(query: str, top_k: int = 5) -> str:
    results = hybrid.leann_search(query, top_k)
    if not results:
        return f"No semantic results for: {query!r}"
    lines = [f"Semantic results for: {query!r}\n"]
    for i, r in enumerate(results, 1):
        txt = r.get("text", "")[:300]
        score = r.get("score", 0.0)
        lines.append(f"{i}. [score={score:.3f}] {txt}\n")
    return "\n".join(lines)


if __name__ == "__main__":
    MCP.run()
