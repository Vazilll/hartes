"""
Hierarchical Capability Tree & Progressive Skill/MCP Resolver for Vazus OS.
Organizes skills and MCP tools into an ontology forest with multi-tier JIT (Just-in-Time) progressive loading.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class CapabilityNode:
    id: str
    name: str
    description: str
    node_type: str  # "domain", "subdomain", "skill", "mcp_tool"
    children: List["CapabilityNode"] = field(default_factory=list)
    keywords: Set[str] = field(default_factory=set)
    schema_payload: Optional[Dict[str, Any]] = None
    is_active: bool = False
    tokens_estimate: int = 10


class HierarchicalCapabilityForest:
    """
    4-Tier Hierarchical Tree for on-demand progressive disclosure of Skills and MCP tools:
    Level 0: Root Categories (Code, Cloud, Memory, Productivity)
    Level 1: Domain Clusters (SMT, AST, Databases, GKE, Wiki)
    Level 2: Skill Bundles (SKILL.md descriptors)
    Level 3: Leaf MCP Tools (Concrete JSON-RPC schemas)
    """

    def __init__(self):
        self.root_domains: Dict[str, CapabilityNode] = {}
        self.node_registry: Dict[str, CapabilityNode] = {}
        self._build_default_ontology()

    def _build_default_ontology(self):
        """Builds default 4-tier capability hierarchy."""
        # 1. Domain: Code & Verification
        code_domain = CapabilityNode(
            id="domain:code",
            name="Code & Formal Verification",
            description="Code editing, AST transformations, SMT verification, REPL, and testing",
            node_type="domain",
            keywords={"code", "python", "go", "ast", "verify", "smt", "z3", "test", "repl", "refactor"},
        )

        # Subdomains under Code
        smt_subdomain = CapabilityNode(
            id="subdomain:smt",
            name="SMT Solvers & Proofs",
            description="Formal logic proofs, CEGIS, and constraint resolution",
            node_type="subdomain",
            keywords={"smt", "z3", "cvc5", "proof", "contract", "invariant", "angelic", "unsat"},
        )
        ast_subdomain = CapabilityNode(
            id="subdomain:ast",
            name="AST & Structural Codemods",
            description="Tree-sitter AST pruning, GritQL rewrites, and structural search",
            node_type="subdomain",
            keywords={"ast", "tree_sitter", "gritql", "ast_grep", "prune", "codemod"},
        )
        code_domain.children.extend([smt_subdomain, ast_subdomain])

        # 2. Domain: Infrastructure & Storage
        infra_domain = CapabilityNode(
            id="domain:infra",
            name="Infrastructure & Storage",
            description="Databases, SQLite WAL, sandboxes, process isolation, and cloud tools",
            node_type="domain",
            keywords={"db", "sqlite", "wal", "job", "sandbox", "gcp", "gke", "cloud", "process", "ipc"},
        )

        # 3. Domain: Memory & Knowledge
        memory_domain = CapabilityNode(
            id="domain:memory",
            name="Memory & Knowledge Graph",
            description="Karpathy LLM Wiki, embeddings, vector search, and episodic memory",
            node_type="domain",
            keywords={"memory", "wiki", "embedding", "vector", "npu", "knowledge", "graph", "karpathy"},
        )

        # Register root domains
        for dom in [code_domain, infra_domain, memory_domain]:
            self.root_domains[dom.id] = dom
            self._index_nodes(dom)

    def _index_nodes(self, node: CapabilityNode):
        self.node_registry[node.id] = node
        for child in node.children:
            self._index_nodes(child)

    def register_mcp_tool(self, tool_name: str, domain_id: str, schema: Dict[str, Any], description: str = ""):
        """Attaches a concrete MCP tool as a leaf node in the hierarchy."""
        target_domain = self.node_registry.get(domain_id)
        if not target_domain:
            target_domain = self.root_domains.get("domain:code")

        corpus = (tool_name + " " + description).lower()
        keywords = set(re.findall(r"\b[a-zA-Z0-9_]{2,}\b", corpus))
        token_cost = max(1, len(str(schema)) // 4)

        leaf = CapabilityNode(
            id=f"tool:{tool_name}",
            name=tool_name,
            description=description,
            node_type="mcp_tool",
            keywords=keywords,
            schema_payload=schema,
            tokens_estimate=token_cost,
        )
        target_domain.children.append(leaf)
        self.node_registry[leaf.id] = leaf

    def resolve_progressive_context(self, user_query: str, max_leaf_tools: int = 4) -> Dict[str, Any]:
        """
        Multi-tier progressive resolver:
        1. Selects Top-1 or Top-2 matching Domain Branches (Cost: 0 prompt tokens).
        2. Traverses Subdomains and Skills.
        3. Promotes ONLY top-K leaf MCP tool schemas matching the query.
        """
        query_terms = set(re.findall(r"\b[a-zA-Z0-9_]{2,}\b", user_query.lower()))

        # Step 1: Match Domains
        active_domains = []
        for dom_id, dom in self.root_domains.items():
            overlap = query_terms.intersection(dom.keywords)
            if overlap:
                score = len(overlap) / float(len(query_terms.union(dom.keywords)))
                active_domains.append((score, dom))

        active_domains.sort(key=lambda x: x[0], reverse=True)
        selected_domains = (
            [d for _, d in active_domains[:2]] if active_domains else list(self.root_domains.values())[:1]
        )

        # Step 2: Traverse active branches to find leaf MCP tools
        candidate_tools = []

        def _collect_leaves(node: CapabilityNode):
            if node.node_type == "mcp_tool" and node.schema_payload:
                overlap = query_terms.intersection(node.keywords)
                score = len(overlap) / float(len(query_terms.union(node.keywords))) if overlap else 0.0
                if any(t in node.name.lower() for t in query_terms):
                    score += 1.5
                if score > 0.01:
                    candidate_tools.append((score, node))
            for c in node.children:
                _collect_leaves(c)

        for dom in selected_domains:
            _collect_leaves(dom)

        candidate_tools.sort(key=lambda x: x[0], reverse=True)
        promoted_tools = [node.schema_payload for _, node in candidate_tools[:max_leaf_tools]]

        # Telemetry
        active_tokens = sum(node.tokens_estimate for _, node in candidate_tools[:max_leaf_tools])
        total_tree_tokens = sum(n.tokens_estimate for n in self.node_registry.values() if n.node_type == "mcp_tool")

        return {
            "active_domains": [d.name for d in selected_domains],
            "promoted_tools": promoted_tools,
            "promoted_count": len(promoted_tools),
            "tokens_disclosed": active_tokens,
            "total_catalog_tokens": total_tree_tokens,
            "savings_percent": round((1.0 - active_tokens / max(1, total_tree_tokens)) * 100.0, 2)
            if total_tree_tokens > 0
            else 0.0,
        }
