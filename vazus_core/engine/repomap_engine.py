#!/usr/bin/env python3
"""
vazus_core.engine.repomap_engine — Aider RepoMap & Structural PageRank Tag Indexer.
==================================================================================

Implements Aider's SOTA RepoMap pattern:
  - Extracts definitions and references using AST / tree-sitter.
  - Builds a dependency graph between files and symbols.
  - Calculates PageRank scores to identify the most structurally important symbols.
  - Generates compact, token-capped (512-1024 tokens) structural repository maps.
"""

import ast
import logging
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger("vazus_core.engine.repomap")


class RepoMapEngine:
    """
    Constructs PageRank-weighted structural repository maps.
    """

    def __init__(self, workspace_root: str = r"C:\vazus", max_tokens: int = 1024):
        self.workspace_root = Path(workspace_root).resolve()
        self.max_tokens = max_tokens
        self.definitions: Dict[str, Set[str]] = defaultdict(set)
        self.references: Dict[str, Set[str]] = defaultdict(set)
        self.file_symbols: Dict[str, List[Tuple[str, str, int]]] = defaultdict(list)

    def scan_repository(self, target_dir: Optional[str] = None) -> None:
        """Parses AST of all Python files to extract symbols and cross-file references."""
        base_dir = self.workspace_root / (target_dir or "vazus_core")
        self.definitions.clear()
        self.references.clear()
        self.file_symbols.clear()

        for p in base_dir.rglob("*.py"):
            if any(part in p.parts for part in [".venv", "__pycache__", ".git", "build"]):
                continue
            rel = str(p.relative_to(self.workspace_root)).replace("\\", "/")
            try:
                content = p.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(content, filename=str(p))
                self._extract_ast_tags(rel, tree)
            except Exception as exc:
                logger.debug("Failed to parse AST for %s: %s", rel, exc)
                continue

    def _extract_ast_tags(self, rel_path: str, tree: ast.AST) -> None:
        """Extracts class/function definitions and identifier references."""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                self.definitions[node.name].add(rel_path)
                self.file_symbols[rel_path].append(("class", node.name, node.lineno))
            elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                self.definitions[node.name].add(rel_path)
                self.file_symbols[rel_path].append(("def", node.name, node.lineno))
            elif isinstance(node, ast.Name):
                self.references[rel_path].add(node.id)

    def compute_pagerank(self, iterations: int = 20, damping: float = 0.85) -> Dict[str, float]:
        """Calculates PageRank score for each file based on cross-file symbol references."""
        files = list(self.file_symbols.keys())
        if not files:
            return {}

        num_files = len(files)
        ranks = {f: 1.0 / num_files for f in files}

        # Build file-to-file reference graph
        out_edges: Dict[str, Set[str]] = defaultdict(set)
        in_edges: Dict[str, Set[str]] = defaultdict(set)

        for src_file, refs in self.references.items():
            for sym in refs:
                for target_file in self.definitions.get(sym, set()):
                    if target_file != src_file:
                        out_edges[src_file].add(target_file)
                        in_edges[target_file].add(src_file)

        for _ in range(iterations):
            new_ranks = {}
            for f in files:
                rank_sum = sum(ranks[incoming] / max(1, len(out_edges[incoming])) for incoming in in_edges[f])
                new_ranks[f] = (1.0 - damping) / num_files + damping * rank_sum
            ranks = new_ranks

        return ranks

    def generate_repomap(self, target_dir: Optional[str] = None, focus_files: Optional[List[str]] = None) -> str:
        """
        Generates a ranked structural repository map string within the token budget.
        """
        self.scan_repository(target_dir)
        ranks = self.compute_pagerank()

        sorted_files = sorted(
            self.file_symbols.keys(), key=lambda f: (f in (focus_files or []), ranks.get(f, 0.0)), reverse=True
        )

        lines = ["# REPOSITORY STRUCTURAL MAP (Ranked by Importance):"]
        token_estimate = 10

        for f in sorted_files:
            syms = self.file_symbols[f]
            if not syms:
                continue

            file_header = f"\n{f}:"
            sym_lines = []
            for kind, name, line in syms[:8]:  # Top symbols per file
                sym_lines.append(f"  {kind} {name} (L{line})")

            chunk = file_header + "\n" + "\n".join(sym_lines)
            chunk_tokens = len(chunk) // 4

            if token_estimate + chunk_tokens > self.max_tokens:
                break

            lines.append(chunk)
            token_estimate += chunk_tokens

        return "\n".join(lines)
