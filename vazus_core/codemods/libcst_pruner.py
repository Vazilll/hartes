"""
vazus_core.codemods.libcst_pruner
Layer 3 Component: Precision Python Concrete Syntax Tree (CST) Pruning & Transformation.

Guarantees 100% preservation of comments, whitespace, docstrings, and custom formatting.
"""

import logging
from typing import Set

import libcst as cst

logger = logging.getLogger("vazus_core.codemods")


class DeadFunctionExcisionTransformer(cst.CSTTransformer):
    """CST Transformer that removes target top-level and class-level functions."""

    def __init__(self, target_function_names: Set[str]):
        self.target_function_names = set(target_function_names)
        self.removed_count = 0

    def leave_FunctionDef(
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> cst.RemovalSentinel | cst.FunctionDef:
        if original_node.name.value in self.target_function_names:
            self.removed_count += 1
            return cst.RemoveFromParent()
        return updated_node


class FunctionCallRenameTransformer(cst.CSTTransformer):
    """CST Transformer that renames function calls while preserving formatting & arguments."""

    def __init__(self, old_name: str, new_name: str):
        self.old_name = old_name
        self.new_name = new_name
        self.renamed_count = 0

    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.Call:
        if isinstance(original_node.func, cst.Name) and original_node.func.value == self.old_name:
            self.renamed_count += 1
            return updated_node.with_changes(func=cst.Name(self.new_name))
        return updated_node


class LibCSTPruner:
    """
    High-level API for precision CST transformations on Python files.
    """

    @staticmethod
    def excise_dead_functions(source_code: str, function_names: Set[str]) -> tuple[str, int]:
        """
        Removes functions from Python source code, preserving surrounding comments and whitespace.
        Returns (transformed_code, removed_count).
        """
        try:
            tree = cst.parse_module(source_code)
            transformer = DeadFunctionExcisionTransformer(function_names)
            modified_tree = tree.visit(transformer)
            return modified_tree.code, transformer.removed_count
        except Exception as e:
            logger.error(f"Error excising functions via LibCST: {e}")
            return source_code, 0

    @staticmethod
    def rename_function_calls(source_code: str, old_name: str, new_name: str) -> tuple[str, int]:
        """
        Renames calls to a specific function across source code.
        Returns (transformed_code, renamed_count).
        """
        try:
            tree = cst.parse_module(source_code)
            transformer = FunctionCallRenameTransformer(old_name, new_name)
            modified_tree = tree.visit(transformer)
            return modified_tree.code, transformer.renamed_count
        except Exception as e:
            logger.error(f"Error renaming function calls via LibCST: {e}")
            return source_code, 0
