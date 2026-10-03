"""
vazus_core.ast_pruner — Top-level alias and interface for Universal AST Pruner.
Re-exports ASTPruner, GoASTPruner, GoTreeSitterPruner, CTreeSitterPruner, and UniversalASTPruner
from vazus_core.verification.ast_pruner for backward compatibility and clean namespace access.
"""

from vazus_core.verification.ast_pruner import (
    ASTPruner,
    CTreeSitterPruner,
    DocstringAndBodyPruner,
    GoASTPruner,
    GoTreeSitterPruner,
    UniversalASTPruner,
    prune_c_code,
    prune_go_code,
    prune_universal_code,
    prune_universal_file,
)

def prune_code_string(source_code: str, docstring_mode: str = "summary"):
    """
    Prunes Python source code AST by removing function bodies and handling docstrings.
    Accelerated by native Rust engine with automatic Python fallback.
    Returns (pruned_code, stats_dict).
    """
    return ASTPruner.prune_code_string(source_code, docstring_mode=docstring_mode)


__all__ = [
    "ASTPruner",
    "DocstringAndBodyPruner",
    "GoTreeSitterPruner",
    "GoASTPruner",
    "CTreeSitterPruner",
    "UniversalASTPruner",
    "prune_go_code",
    "prune_c_code",
    "prune_universal_code",
    "prune_universal_file",
    "prune_code_string",
]

