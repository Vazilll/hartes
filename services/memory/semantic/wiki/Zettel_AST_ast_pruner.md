---
id: Zettel_AST_ast_pruner
title: AST Pruned Skeleton - ast_pruner.py
date: 2026-08-09
domain: ast_code
tags: [ast, code, ast_pruner, ast_pruner]
status: VERIFIED
sources: [ASTPruner, SuperGraph OS]
---

# AST Pruned Skeleton for `ast_pruner.py`

## Core Metrics
- **Total AST Nodes**: 2483
- **Pruned AST Nodes**: 282
- **Token Reduction**: 88.64%
- **Syntax Valid**: `True`

## Pruned Signatures
```python
"""
vazus_core.ast_pruner — AST Pruning and Signature Validation Engine.
Provides high-efficiency AST node pruning, docstring compression, signature extraction,
and token reduction (>75%) for Vazus SuperGraph OS v4.0.
"""
import ast
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

class DocstringAndBodyPruner(ast.NodeTransformer):
    """AST Transformer to strip docstrings according to docstring_mode"""

    def __init__(self, docstring_mode: str='summary'):
        ...

    def _process_docstring(self, doc_str: Optional[str]) -> Optional[str]:
        ...

    def _prune_body(self, body: List[ast.stmt], is_module: bool=False) -> List[ast.stmt]:
        ...

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        ...

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AsyncFunctionDef:
        ...

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.ClassDef:
        ...

class ASTPruner:
    """Analyzes, prunes, and validates Python AST signatures for RLM rollout optimizations."""

    @classmethod
    def prune_ast(cls, source_code: str, docstring_mode: str='summary') -> str:
        """Parses and prunes function/method bodies to signature skeletons for token reduction."""
        ...

    @staticmethod
    def validate_signatures(source_code: str) -> bool:
        """Validates AST syntax compliance."""
        ...

    @classmethod
    def prune_code_string(cls, source_code: str, docstring_mode: str='summary') -> Tuple[str, Dict[str, Any]]:
        """Prunes Python source code AST by removing function bodies and handling docstrings."""
        ...

    @classmethod
    def _log_pruning_to_db_and_memory(cls, path: Path, pruned_code: str, stats: Dict[str, Any], docstring_mode: str='summary') -> None:
        """Records pruning metadata into SQLite vazus.db (organic_insights & kg_nodes domain='ast_code')"""
        ...

    @classmethod
    def prune_file(cls, file_path: Union[st
```

## Related Notes & Wikilinks
- [[Research_SuperGraph_Memory_Wiki_and_AST|SuperGraph Memory & AST Integration]]
- [[RLM_Code_Task_Refactor_AST_pruner|AST Pruner Refactor Task]]
- [[Zettel_AST_ast_pruner|Self Reference]]
