"""
Dynamic MCP Tool Gateway & Intent-Schema Overlap (ISO) Router.
Implements Progressive Tool Disclosure, reducing tool schema token overhead by up to 95%.
"""

import re
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Set


class DynamicMCPGateway:
    """
    Dynamic Tool Disclosure Gateway implementing Intent-Schema Overlap (ISO) filtering
    and LRU tool promotion state machines.
    """

    def __init__(self, max_active_tools: int = 5, base_meta_tools: Optional[List[str]] = None):
        self.max_active_tools = max_active_tools
        self.meta_tools = set(base_meta_tools or ["search_tools", "call_mcp_tool"])
        self.tool_catalog: Dict[str, Dict[str, Any]] = {}
        self.active_lru_cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self.total_eager_tokens = 0
        self.active_disclosed_tokens = 0

    def register_tool(self, tool_name: str, schema: Dict[str, Any], server_name: str = "default"):
        """Registers a tool in the lazy-loaded catalog."""
        schema_str = str(schema)
        token_estimate = max(1, len(schema_str) // 4)

        # Match tokens of length >= 2 to include terms like z3, go, ai, db
        text_corpus = (tool_name + " " + schema.get("description", "")).lower()
        keywords = set(re.findall(r"\b[a-zA-Z0-9_]{2,}\b", text_corpus))

        self.tool_catalog[tool_name] = {
            "name": tool_name,
            "server": server_name,
            "schema": schema,
            "description": schema.get("description", ""),
            "tokens": token_estimate,
            "keywords": keywords,
        }
        self.total_eager_tokens += token_estimate

    def compute_iso_score(
        self, query: str, tool_name: str, query_tokens: Optional[Set[str]] = None, lower_query: Optional[str] = None
    ) -> float:
        """
        Computes Intent-Schema Overlap (ISO) heuristic score between user query and tool definition.
        """
        tool_data = self.tool_catalog.get(tool_name)
        if not tool_data:
            return 0.0

        if lower_query is None:
            lower_query = (query[:10000] if query else "").lower()
        if query_tokens is None:
            query_tokens = set(re.findall(r"\b[a-zA-Z0-9_]{2,}\b", lower_query))
        if not query_tokens:
            return 0.0

        tool_keywords = tool_data["keywords"]
        overlap = query_tokens.intersection(tool_keywords)

        if not overlap:
            # Check substring match in query
            if any(kw in lower_query for kw in tool_keywords if len(kw) >= 3):
                return 0.3
            return 0.0

        # Jaccard overlap
        jaccard = len(overlap) / float(len(query_tokens.union(tool_keywords)))
        boost = 2.0 if any(t in tool_name.lower() for t in query_tokens) else 1.0
        return jaccard * boost

    def resolve_active_tools(self, current_user_query: str) -> List[Dict[str, Any]]:
        """
        Discloses only the top-K relevant tools + meta tools, updating LRU promotion cache.
        """
        lower_query = (current_user_query[:10000] if current_user_query else "").lower()
        query_tokens = set(re.findall(r"\b[a-zA-Z0-9_]{2,}\b", lower_query))
        scored_tools = []
        for name in self.tool_catalog:
            if name in self.meta_tools:
                continue
            score = self.compute_iso_score(lower_query, name, query_tokens=query_tokens, lower_query=lower_query)
            if score > 0.01:
                scored_tools.append((score, name))

        scored_tools.sort(key=lambda x: x[0], reverse=True)
        top_selected = [name for _, name in scored_tools[: self.max_active_tools]]

        # Update LRU cache
        for name in top_selected:
            if name in self.active_lru_cache:
                self.active_lru_cache.move_to_end(name)
            else:
                self.active_lru_cache[name] = self.tool_catalog[name]

        # Evict stale tools exceeding limit
        while len(self.active_lru_cache) > self.max_active_tools:
            self.active_lru_cache.popitem(last=False)

        # Assemble final disclosed tool list (Meta tools + Promoted tools)
        disclosed = []
        for name in self.meta_tools:
            if name in self.tool_catalog:
                disclosed.append(self.tool_catalog[name]["schema"])

        for name, tool_data in self.active_lru_cache.items():
            if name not in self.meta_tools:
                disclosed.append(tool_data["schema"])

        self.active_disclosed_tokens = sum(
            self.tool_catalog[t.get("name", "")]["tokens"] for t in disclosed if t.get("name") in self.tool_catalog
        )

        return disclosed

    def get_token_savings_metric(self) -> Dict[str, Any]:
        """Returns empirical token reduction stats."""
        saved = max(0, self.total_eager_tokens - self.active_disclosed_tokens)
        reduction_pct = (saved / self.total_eager_tokens * 100.0) if self.total_eager_tokens > 0 else 0.0
        return {
            "total_registered_tools": len(self.tool_catalog),
            "eager_tokens": self.total_eager_tokens,
            "active_tokens": self.active_disclosed_tokens,
            "tokens_saved": saved,
            "reduction_percent": round(reduction_pct, 2),
        }
