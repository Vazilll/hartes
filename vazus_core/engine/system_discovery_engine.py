"""
System Discovery Engine, Dead Code Hunter & Architecture Capability Matcher for Vazus OS.
Scans the codebase to detect unreferenced symbols, orphan files, and matches capabilities to prevent code duplication.
"""

import ast
import os
import re
import shutil
import logging
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger("SystemDiscoveryEngine")



@dataclass
class SymbolDefinition:
    name: str
    kind: str # "function", "class", "async_function", "variable"
    file_path: str
    line_number: int
    docstring: str = ""
    is_exported: bool = True


@dataclass
class SystemCapability:
    name: str
    module_path: str
    class_or_func: str
    description: str
    keywords: Set[str] = field(default_factory=set)


class SystemDiscoveryEngine:
    """
    Continuous Capability Hunter and Dead Code / Orphan File Detector.
    """

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = Path(workspace_root or "C:/vazus").resolve()
        self.defined_symbols: Dict[str, SymbolDefinition] = {}
        self.referenced_symbols: Set[str] = set()
        self.file_imports: Dict[str, Set[str]] = {} # file -> imported module paths
        self.all_py_files: Set[str] = set()
        self.capabilities: List[SystemCapability] = []

    def scan_codebase(self) -> Dict[str, Any]:
        """
        Performs full AST scan across workspace, extracting definitions, references, and capabilities.
        """
        self.defined_symbols.clear()
        self.referenced_symbols.clear()
        self.file_imports.clear()
        self.all_py_files.clear()
        self.capabilities.clear()

        # Directories to ignore
        ignore_dirs = {".venv", "venv", "__pycache__", ".git", ".idea", ".vscode", "node_modules", "dist", "build"}

        for py_path in self.workspace_root.glob("**/*.py"):
            parts = py_path.parts
            if any(ig in parts for ig in ignore_dirs):
                continue

            rel_path = str(py_path.relative_to(self.workspace_root)).replace("\\", "/")
            self.all_py_files.add(rel_path)
            self.file_imports[rel_path] = set()

            try:
                content = py_path.read_text(encoding="utf-8", errors="ignore")
                tree = ast.parse(content, filename=str(py_path))
            except Exception:
                continue

            # Walk AST
            for node in ast.walk(tree):
                # 1. Capture Imports
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self.file_imports[rel_path].add(alias.name)
                        self.referenced_symbols.add(alias.name.split(".")[-1])
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        self.file_imports[rel_path].add(node.module)
                    for alias in node.names:
                        self.referenced_symbols.add(alias.name)

                # 2. Capture Definitions
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    kind = "class" if isinstance(node, ast.ClassDef) else ("async_function" if isinstance(node, ast.AsyncFunctionDef) else "function")
                    doc = ast.get_docstring(node) or ""
                    symbol_id = f"{rel_path}:{node.name}"
                    
                    sym_def = SymbolDefinition(
                        name=node.name,
                        kind=kind,
                        file_path=rel_path,
                        line_number=node.lineno,
                        docstring=doc,
                        is_exported=not node.name.startswith("_")
                    )
                    self.defined_symbols[symbol_id] = sym_def

                    # Register capability if it has a meaningful docstring or public name
                    if sym_def.is_exported and (len(doc) > 10 or kind == "class"):
                        corpus = (node.name + " " + doc).lower()
                        keywords = set(re.findall(r'\b[a-zA-Z_]{3,}\b', corpus))
                        self.capabilities.append(SystemCapability(
                            name=node.name,
                            module_path=rel_path,
                            class_or_func=node.name,
                            description=doc.strip().split("\n")[0] if doc else node.name,
                            keywords=keywords
                        ))

                # 3. Capture References (Calls, Names, Attributes)
                elif isinstance(node, ast.Name):
                    self.referenced_symbols.add(node.id)
                elif isinstance(node, ast.Attribute):
                    self.referenced_symbols.add(node.attr)

        return {
            "total_files": len(self.all_py_files),
            "total_defined_symbols": len(self.defined_symbols),
            "total_capabilities": len(self.capabilities)
        }

    def find_orphan_files(self) -> List[str]:
        """
        Identifies Python files that are never imported by any other file
        and do not contain test or main entry points.
        """
        imported_modules = set()
        for imports in self.file_imports.values():
            for imp in imports:
                # Convert module path to file candidate (e.g. vazus_core.storage.sqlite_pool)
                as_path = imp.replace(".", "/")
                imported_modules.add(as_path)

        orphans = []
        for file_rel in self.all_py_files:
            stem_path = file_rel[:-3] if file_rel.endswith(".py") else file_rel
            is_entry = file_rel.startswith("tests/") or file_rel.endswith("__init__.py") or file_rel.endswith("main.py")
            is_hook = "hook" in file_rel or "cli" in file_rel or "daemon" in file_rel

            if is_entry or is_hook:
                continue

            # Check if any imported module matches this file path
            is_imported = any(stem_path.endswith(imp) or imp.endswith(stem_path) for imp in imported_modules)
            if not is_imported:
                orphans.append(file_rel)

        return sorted(orphans)

    def find_unreferenced_symbols(self) -> List[SymbolDefinition]:
        """
        Finds public functions and classes that are never referenced anywhere in the workspace.
        """
        unreferenced = []
        for sym_id, sym_def in self.defined_symbols.items():
            # Skip test functions and magic methods
            if sym_def.name.startswith("test_") or sym_def.name.startswith("__"):
                continue
            if sym_def.file_path.startswith("tests/"):
                continue

            if sym_def.name not in self.referenced_symbols:
                unreferenced.append(sym_def)

        return unreferenced

    def search_capabilities(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Matches a natural language query against the catalog of existing system capabilities.
        Prevents reinvention of existing modules.
        """
        query_terms = set(re.findall(r'\b[a-zA-Z_]{3,}\b', query.lower()))
        if not query_terms:
            return []

        scored = []
        for cap in self.capabilities:
            overlap = query_terms.intersection(cap.keywords)
            if overlap:
                score = len(overlap) / float(len(query_terms.union(cap.keywords)))
                if any(term in cap.name.lower() for term in query_terms):
                    score *= 1.8
                scored.append((score, cap))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for score, cap in scored[:top_k]:
            results.append({
                "name": cap.name,
                "module": cap.module_path,
                "description": cap.description,
                "relevance_score": round(score, 3)
            })
        return results

    def find_shadow_directories(self) -> List[Path]:
        """
        Discovers shadow / duplicate package directories (e.g. vazus_core/hooks/vazus_core).
        Prunes ignored directories in-place to prevent scanning deeply into vendor / scratch trees.
        """
        shadow_dirs = []
        ignore_dirs = {
            ".venv", "venv", "__pycache__", ".git", ".idea", ".vscode",
            "node_modules", "dist", "build", "labs", "bin", "apps", "vendor",
            "scratch", "inference", "llama.cpp", "services/inference"
        }
        top_package_names = {"vazus_core"}

        for dirpath, dirnames, _ in os.walk(self.workspace_root):
            dirnames[:] = [d for d in dirnames if d not in ignore_dirs and not d.startswith(".")]

            for d in list(dirnames):
                full_d = Path(dirpath) / d
                # If vazus_core is found nested inside another folder (e.g. vazus_core/hooks/vazus_core)
                if d in top_package_names and full_d != (self.workspace_root / d):
                    shadow_dirs.append(full_d)

        return shadow_dirs

    def find_dummy_artifacts(self) -> List[Path]:
        """
        Identifies temporary dummy test files, 0 KB empty scripts, or scratch artifacts.
        Prunes ignored directories (.venv, .git, etc.) immediately to prevent scanning 50k+ files.
        """
        dummy_files = []
        ignore_dirs = {
            ".venv", "venv", "__pycache__", ".git", ".idea", ".vscode",
            "node_modules", "dist", "build", "labs", "bin", "vendor"
        }
        scratch_patterns = re.compile(r"^(?:temp_|tmp_|scratch_|dummy_).*\.py$|.*\.tmp$|.*\.scratch$", re.IGNORECASE)

        for dirpath, dirnames, filenames in os.walk(self.workspace_root):
            # Prune ignored directories in-place so os.walk does not recurse into them
            dirnames[:] = [d for d in dirnames if d not in ignore_dirs and not d.startswith(".")]

            for fname in filenames:
                if fname == "__init__.py":
                    continue
                p = Path(dirpath) / fname
                if scratch_patterns.match(fname):
                    dummy_files.append(p)
                elif fname.endswith(".py"):
                    try:
                        if p.stat().st_size == 0:
                            dummy_files.append(p)
                    except OSError:
                        pass

        return dummy_files

    def purge_shadow_directories(self) -> List[str]:
        """
        Removes all discovered shadow directories and returns their string paths.
        """
        shadows = self.find_shadow_directories()
        purged = []
        for s in shadows:
            try:
                if s.exists() and s.is_dir():
                    shutil.rmtree(s)
                    purged.append(str(s))
            except Exception as e:
                logger.warning(f"Failed to purge shadow dir {s}: {e}")
        return purged

    def purge_dummy_artifacts(self) -> List[str]:
        """
        Deletes all discovered dummy artifact files and returns their string paths.
        """
        dummies = self.find_dummy_artifacts()
        purged = []
        for d in dummies:
            try:
                if d.exists() and d.is_file():
                    d.unlink()
                    purged.append(str(d))
            except Exception as e:
                logger.warning(f"Failed to purge dummy artifact {d}: {e}")
        return purged

    def run_proactive_cleanup(self) -> Dict[str, Any]:
        """
        Executes complete proactive cleanup across shadow directories and dummy files.
        """
        purged_shadows = self.purge_shadow_directories()
        purged_dummies = self.purge_dummy_artifacts()
        return {
            "purged_shadow_dirs": purged_shadows,
            "purged_dummy_artifacts": purged_dummies,
            "total_purged": len(purged_shadows) + len(purged_dummies),
            "status": "clean"
        }

