"""
vazus_core.routing.dynamic_tool_router — Dynamic Tool Router & Payload Projection.
Solves 'MCP Token Bloat' by progressively exposing only top-k relevant tool schemas
and filtering response JSON payloads server-side before feeding into LLM context.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

from vazus_core.memory.embeddings import get_embedding

logger = logging.getLogger("ToolRouter")


@dataclass
class ToolDescriptor:
    """Metadata descriptor for a single registered MCP / local tool."""

    name: str
    category: str
    description: str
    schema: Dict[str, Any]
    tags: List[str] = field(default_factory=list)
    embedding: Optional[List[float]] = None


class DynamicToolRouter:
    """
    Progressive Tool Disclosure Router & Server-Side JSON Projector.
    """

    def __init__(self, auto_discover_mcp: bool = True, mcp_base_dir: Optional[str] = None):
        self.registry: Dict[str, ToolDescriptor] = {}
        self._bootstrap_default_tools()
        if auto_discover_mcp:
            self.auto_discover_mcp_tools(mcp_base_dir)

    def auto_discover_mcp_tools(self, mcp_base_dir: Optional[str] = None) -> int:
        """
        Scans all installed MCP server directories and registers all tool schemas dynamically.
        Enables lazy tool discovery without polluting LLM system prompt context with 200+ schemas.
        """
        import os
        from pathlib import Path

        base = mcp_base_dir or os.path.expanduser(r"~\.gemini\antigravity\mcp")
        base_path = Path(base)
        if not base_path.exists():
            return 0

        registered_count = 0
        for server_dir in base_path.iterdir():
            if not server_dir.is_dir():
                continue
            server_name = server_dir.name
            for schema_file in server_dir.glob("*.json"):
                try:
                    schema_data = json.loads(schema_file.read_text(encoding="utf-8", errors="ignore"))
                    tool_name = schema_data.get("name") or schema_file.stem
                    description = schema_data.get("description", f"MCP tool {tool_name} from {server_name}")
                    parameters = schema_data.get("parameters", {})
                    tags = [server_name] + [w.lower() for w in tool_name.split("_") if len(w) > 2]
                    self.register_tool(
                        name=f"{server_name}__{tool_name}",
                        category=f"mcp_{server_name}",
                        description=description,
                        schema=parameters,
                        tags=tags,
                    )
                    registered_count += 1
                except Exception as e:
                    logger.debug("Failed loading MCP schema %s: %s", schema_file, e)

        logger.info("Auto-discovered and registered %d MCP tools from %s", registered_count, base)
        return registered_count

    def _bootstrap_default_tools(self) -> None:
        """Populates common SOTA tools into the registry."""
        default_tools = [
            (
                "ast_prune",
                "code_intelligence",
                "Extracts signatures and prunes AST bodies for Go, C, Python to save 75% tokens.",
                {"target_file": "string", "log_memory": "boolean"},
                ["ast", "tree_sitter", "go", "python", "pruning"],
            ),
            (
                "smt_z3_verify",
                "verification",
                "Formally proves mathematical code contracts and invariant safety via Microsoft Z3.",
                {"invariants": "list", "code_snippet": "string"},
                ["z3", "formal", "smt", "contract", "proof"],
            ),
            (
                "magma_graph_traverse",
                "memory",
                "Traverses MAGMA 4-graph memory (entity, causal, temporal, semantic) based on query intent.",
                {"node_id": "string", "intent": "string", "max_depth": "integer"},
                ["magma", "graph", "memory", "hebbian", "causal"],
            ),
            (
                "pattern_mine",
                "code_intelligence",
                "Discovers design patterns (WorkerPool, RingBuffer, RAII) and measures Code Health 0-10.",
                {"file_path": "string"},
                ["pattern", "code_health", "smells", "refactor"],
            ),
            (
                "async_worktree_execute",
                "sandbox",
                "Runs speculative background code mutations inside Win32 Job isolated worktree sandboxes.",
                {"task_id": "string", "test_command": "list"},
                ["sandbox", "worktree", "win32", "isolation"],
            ),
            (
                "research_obsidian_sync",
                "knowledge",
                "Generates atomic Zettelkasten Obsidian notes with SymPy equation proof checks.",
                {"title": "string", "summary": "string", "latex_equations": "list"},
                ["obsidian", "zettel", "sympy", "latex", "wiki"],
            ),
        ]

        for name, cat, desc, schema, tags in default_tools:
            self.register_tool(name, cat, desc, schema, tags)

    def register_tool(
        self,
        name: str,
        category: str,
        description: str,
        schema: Dict[str, Any],
        tags: Optional[List[str]] = None,
    ) -> None:
        """Registers a tool with precomputed 768-D semantic vector."""
        emb = None
        try:
            emb_raw = get_embedding(f"{name}: {description} {' '.join(tags or [])}")
            if emb_raw and len(emb_raw) == 768:
                emb = list(emb_raw)
        except Exception as exc:
            logger.debug("Tool embedding calculation failed for %s: %s", name, exc)

        self.registry[name] = ToolDescriptor(
            name=name,
            category=category,
            description=description,
            schema=schema,
            tags=tags or [],
            embedding=emb,
        )

    def _calc_tool_relevance(self, desc: ToolDescriptor, query_lower: str, query_emb: Optional[List[float]]) -> float:
        """Calculates combined lexical and vector relevance score for a tool descriptor."""
        import re

        query_words = set(re.findall(r"\b\w+\b", query_lower))
        score = 0.0

        for tag in desc.tags:
            t_clean = tag.lower().strip()
            if t_clean in query_words:
                score += 0.4
            elif t_clean and t_clean in query_lower:
                score += 0.15

        d_name_clean = desc.name.lower()
        if d_name_clean in query_lower:
            score += 0.6
        else:
            name_parts = set(re.findall(r"\b\w+\b", d_name_clean))
            overlap = name_parts.intersection(query_words)
            if overlap:
                score += 0.3 * (len(overlap) / max(1, len(name_parts)))

        cat_clean = desc.category.lower()
        if cat_clean in query_words:
            score += 0.3

        if query_emb is not None and desc.embedding is not None:
            q_vec = np.array(query_emb, dtype=np.float32)
            d_vec = np.array(desc.embedding, dtype=np.float32)
            norm_q = np.linalg.norm(q_vec)
            norm_d = np.linalg.norm(d_vec)
            if norm_q > 1e-6 and norm_d > 1e-6:
                sim = float(np.dot(q_vec, d_vec) / (norm_q * norm_d))
                score += max(0.0, sim) * 0.5

        return score

    def find_tools(
        self,
        intent_query: str,
        top_k: int = 3,
        min_score: float = 0.1,
    ) -> List[Dict[str, Any]]:
        """Discovers and ranks top-k most relevant tools for the active subtask."""
        if not self.registry:
            return []

        query_lower = intent_query.lower()
        query_emb = None
        try:
            query_emb = get_embedding(intent_query)
        except Exception as exc:
            logger.debug("Intent query embedding computation skipped: %s", exc)

        scored_tools = []
        for desc in self.registry.values():
            score = self._calc_tool_relevance(desc, query_lower, query_emb)
            if score >= min_score:
                scored_tools.append((score, desc))

        scored_tools.sort(key=lambda x: x[0], reverse=True)
        top_matches = scored_tools[:top_k]

        return [
            {
                "name": t.name,
                "category": t.category,
                "description": t.description,
                "schema": t.schema,
                "relevance_score": round(sc, 4),
            }
            for sc, t in top_matches
        ]

    @classmethod
    def _project_dict_val(cls, val: Dict[str, Any]) -> Dict[str, Any]:
        """Filters out raw byte payloads or heavy embeddings from sub-dictionaries."""
        return {
            k: v
            for k, v in val.items()
            if not k.startswith("_") and k not in ("embedding", "embedding_json", "raw_bytes")
        }

    @classmethod
    def _project_list_val(cls, val: List[Any], max_array_items: int) -> List[Any]:
        """Truncates long list values in payload."""
        if len(val) > max_array_items:
            return val[:max_array_items] + [f"... truncated {len(val) - max_array_items} items"]
        return val

    @classmethod
    def project_payload(
        cls,
        payload: Dict[str, Any],
        whitelist_keys: Optional[List[str]] = None,
        max_array_items: int = 10,
    ) -> Dict[str, Any]:
        """
        Server-side projection: strips redundant metadata and truncates verbose lists
        to prevent LLM context exhaustion.
        """
        if not isinstance(payload, dict):
            return payload

        projected = {}
        target_keys = whitelist_keys if whitelist_keys is not None else list(payload.keys())

        for k in target_keys:
            if k not in payload:
                continue
            val = payload[k]

            if isinstance(val, list):
                projected[k] = cls._project_list_val(val, max_array_items)
            elif isinstance(val, dict):
                projected[k] = cls._project_dict_val(val)
            else:
                projected[k] = val

        return projected


# Global singleton router
dynamic_tool_router = DynamicToolRouter()

__all__ = [
    "ToolDescriptor",
    "DynamicToolRouter",
    "dynamic_tool_router",
]
