#!/usr/bin/env python3
"""dnts-ldr MCP — Long-Distance Retrieval server.

Combines RAG, knowledge graph, and FTS for deep context retrieval.
"""
import sys
import json

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
sys.path.insert(0, "C:/vazus/pyenv")

from fastmcp import FastMCP
from vazus_core.workers import ldr as _ldr
from vazus_core.workers import hybrid as _hybrid

MCP = FastMCP("dnts-ldr")


@MCP.tool(description=(
    "Long-Distance Retrieval: deep context search across RAG store, "
    "knowledge graph, and document index. Returns rich context for complex queries."
))
def ldr_search(query: str, depth: int = 2) -> str:
    try:
        import asyncio
        result = asyncio.run(_ldr.run(query, depth=depth))
        if isinstance(result, dict):
            return result.get("result", json.dumps(result, ensure_ascii=False))
        return str(result)
    except Exception as e:
        return f"LDR error: {e}"


@MCP.tool(description=(
    "RAG search: retrieve semantically relevant documents from the knowledge store. "
    "Combines LEANN semantic + FTS keyword matching."
))
def rag_search(query: str, limit: int = 5) -> str:
    # Use hybrid search focused on document sources
    results = _hybrid.sqlite_search(query, limit)
    doc_results = [r for r in results if "document" in r.get("source", "").lower()]
    if not doc_results:
        doc_results = results  # fallback to all results
    if not doc_results:
        return f"No RAG results for: {query!r}"
    lines = [f"RAG results for: {query!r}\n"]
    for i, r in enumerate(doc_results, 1):
        txt = r.get("text", "")[:400]
        src = r.get("source", "?")
        lines.append(f"{i}. [{src}]\n{txt}\n")
    return "\n".join(lines)


@MCP.tool(description=(
    "Save a lesson or knowledge fragment to the knowledge base for future retrieval."
))
def save_lesson(content: str, tags: str = "") -> str:
    try:
        from vazus_core import database
        task_id = database.create_task(
            task_type="lesson",
            payload={"content": content, "tags": tags}
        )
        return f"Lesson saved (task_id: {task_id})"
    except Exception as e:
        return f"Error saving lesson: {e}"


if __name__ == "__main__":
    MCP.run()
