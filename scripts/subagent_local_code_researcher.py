"""
subagent_local_code_researcher.py — Local Codebase Deep Researcher.
Recursively inspects local files, parses AST call-graphs and imports, and traverses module dependency trees.

vazus SuperGraph OS Architecture
"""

import argparse
import ast
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Set

# Windows UTF-8 console output fix
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from vazus_core.verification.ast_pruner import ASTPruner
from vazus_core.memory.embeddings import UnifiedEmbeddingManager


class LocalCodeResearcher:
    """Recursively traverses local code dependencies, imports, and AST call graphs."""

    def __init__(self, root_path: str = "C:\\vazus"):
        self.root_path = Path(root_path).resolve()
        self.embedder = UnifiedEmbeddingManager()
        self.visited_files: Set[str] = set()

    def inspect_file(self, file_path: Path) -> Dict[str, Any]:
        """Parses AST for imports, function definitions, and class declarations."""
        if not file_path.exists() or not file_path.is_file():
            return {"error": f"File not found: {file_path}"}

        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content)

            functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
            classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]

            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module)

            # Generate 768-dim vector representation of file summary
            vector = self.embedder.get_embedding(f"{file_path.name}: {content[:500]}")

            return {
                "file_name": file_path.name,
                "abs_path": str(file_path),
                "rel_path": str(file_path.relative_to(self.root_path)) if file_path.is_relative_to(self.root_path) else str(file_path),
                "line_count": len(content.splitlines()),
                "classes": classes,
                "functions": functions,
                "imports": list(set(imports)),
                "embedding_dim": len(vector),
            }
        except Exception as e:
            return {"file_name": file_path.name, "abs_path": str(file_path), "error": str(e)}

    def resolve_import_path(self, import_name: str) -> Path | None:
        """Resolves Python module import to local file path inside root_path."""
        parts = import_name.split(".")
        candidate1 = self.root_path / Path(*parts).with_suffix(".py")
        candidate2 = self.root_path / Path(*parts) / "__init__.py"

        if candidate1.exists():
            return candidate1
        if candidate2.exists():
            return candidate2
        return None

    def recursive_code_research(self, start_file: str, max_depth: int = 2) -> Dict[str, Any]:
        """Recursively traverses code imports and dependencies up to max_depth."""
        start_path = Path(start_file).resolve()
        traversal_tree = []

        def traverse(current_path: Path, current_depth: int):
            str_path = str(current_path)
            if str_path in self.visited_files or current_depth > max_depth:
                return

            self.visited_files.add(str_path)
            file_info = self.inspect_file(current_path)
            file_info["depth"] = current_depth

            child_nodes = []
            if "imports" in file_info:
                for imp in file_info["imports"]:
                    child_path = self.resolve_import_path(imp)
                    if child_path and str(child_path) not in self.visited_files:
                        child_nodes.append(str(child_path))
                        traverse(child_path, current_depth + 1)

            file_info["children_discovered"] = child_nodes
            traversal_tree.append(file_info)

        traverse(start_path, 1)

        return {
            "subagent": "local_code_researcher",
            "start_file": str(start_path),
            "max_depth": max_depth,
            "total_files_analyzed": len(traversal_tree),
            "tree": traversal_tree,
        }


def main():
    parser = argparse.ArgumentParser(description="Local Codebase Deep Researcher for vazus SuperGraph OS")
    parser.add_argument("--file", "-f", default="C:\\vazus\\vazus_core\\supergraph_linker.py", help="Start file path")
    parser.add_argument("--depth", "-d", type=int, default=2, help="Max recursion depth")
    args = parser.parse_args()

    researcher = LocalCodeResearcher()
    res = researcher.recursive_code_research(args.file, max_depth=args.depth)

    print("\n" + "=" * 60)
    print("LOCAL CODE RESEARCHER EXECUTION RESULT")
    print("=" * 60)
    print(f"Start File: {res['start_file']}")
    print(f"Files Analyzed: {res['total_files_analyzed']}")
    for item in res["tree"]:
        print(f"\n  [Depth {item.get('depth')}] File: {item.get('file_name')}")
        print(f"    Classes: {item.get('classes', [])}")
        print(f"    Functions: {item.get('functions', [])}")
        print(f"    Discovered Children: {len(item.get('children_discovered', []))}")
    print("=" * 60)


if __name__ == "__main__":
    main()
