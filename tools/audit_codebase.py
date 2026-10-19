"""
Comprehensive Codebase Audit Tool for vazus SuperGraph OS.
Performs AST-based dependency graphing, dead-code / reachability detection,
Windows-specific dependency scanning (for CachyOS migration),
and token bloat estimation.
"""

import ast
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent
EXCLUDE_DIRS = {
    ".venv", ".git", ".pytest_cache", ".ruff_cache", "__pycache__",
    ".obsidian", ".whisper_cache", ".hermes", "backups", "scratch"
}

WINDOWS_PATH_PATTERN = re.compile(r"""(?:[a-zA-Z]:[\\/]|\\\\)[^'"\s]+""")
WIN32_IMPORTS = {"win32api", "win32con", "win32gui", "win32process", "win32com", "ctypes.windll", "msvcrt"}

class CodebaseAuditor:
    def __init__(self, root: Path):
        self.root = root
        self.py_files: List[Path] = []
        self.imports: Dict[Path, Set[str]] = {}  # file -> set of imported module names
        self.defined_symbols: Dict[Path, Set[str]] = {}  # file -> set of function/class names
        self.used_symbols: Dict[Path, Set[str]] = {}
        self.windows_paths: Dict[Path, List[Tuple[int, str]]] = {}
        self.windows_imports: Dict[Path, List[str]] = {}
        self.binary_files: List[Path] = []
        self.file_line_counts: Dict[Path, int] = {}

    def discover_files(self):
        for root, dirs, files in os.walk(self.root):
            # prune excluded dirs
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]
            root_path = Path(root)
            for f in files:
                file_path = root_path / f
                suffix = file_path.suffix.lower()
                if suffix == ".py":
                    self.py_files.append(file_path)
                elif suffix in {".dll", ".exe", ".so", ".pyd", ".bin", ".dylib"}:
                    self.binary_files.append(file_path)

    def analyze_file(self, file_path: Path):
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return

        self.file_line_counts[file_path] = len(content.splitlines())

        # Check for hardcoded Windows paths
        win_matches = []
        for line_no, line in enumerate(content.splitlines(), start=1):
            if line.strip().startswith("#"):
                continue
            for m in WINDOWS_PATH_PATTERN.finditer(line):
                win_matches.append((line_no, m.group(0)))
        if win_matches:
            self.windows_paths[file_path] = win_matches

        # AST parsing
        try:
            tree = ast.parse(content, filename=str(file_path))
        except SyntaxError:
            return

        file_imports = set()
        file_win_imports = []
        defined = set()
        used = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    file_imports.add(alias.name)
                    if alias.name in WIN32_IMPORTS or alias.name.startswith("win32"):
                        file_win_imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                file_imports.add(mod)
                if mod in WIN32_IMPORTS or mod.startswith("win32"):
                    file_win_imports.append(mod)
                for alias in node.names:
                    file_imports.add(f"{mod}.{alias.name}" if mod else alias.name)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                defined.add(node.name)
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                used.add(node.id)

        self.imports[file_path] = file_imports
        if file_win_imports:
            self.windows_imports[file_path] = file_win_imports
        self.defined_symbols[file_path] = defined
        self.used_symbols[file_path] = used

    def run(self) -> dict:
        self.discover_files()
        for f in self.py_files:
            self.analyze_file(f)

        # Build module name mapping to files
        # e.g. vazus_core.engine.scheduler -> /home/tarhes/Проекты/vazus/vazus_core/engine/scheduler.py
        mod_to_file = {}
        for f in self.py_files:
            rel = f.relative_to(self.root)
            parts = list(rel.parts)
            if parts[-1] == "__init__.py":
                parts.pop()
            else:
                parts[-1] = parts[-1].replace(".py", "")
            mod_name = ".".join(parts)
            mod_to_file[mod_name] = f
            # Also register relative to subpackages
            if len(parts) > 1:
                sub_name = ".".join(parts[1:])
                mod_to_file[sub_name] = f

        # Cross reference incoming imports
        imported_files = set()
        for f, imps in self.imports.items():
            for imp in imps:
                if not imp:
                    continue
                # Direct match
                if imp in mod_to_file:
                    imported_files.add(mod_to_file[imp])
                else:
                    # Match dot-separated package prefixes
                    for m_name, target_f in mod_to_file.items():
                        if imp == m_name or imp.startswith(m_name + ".") or m_name.startswith(imp + "."):
                            imported_files.add(target_f)

        # Find entrypoints, tests, and isolated modules
        all_py = set(self.py_files)
        entrypoint_names = {"main.py", "cli.py", "app.py", "clip_ocr.py", "wsb_sandbox_controller.py", "pre_tool_hook.py", "post_tool_hook.py"}
        entrypoints = {f for f in all_py if f.name in entrypoint_names or "tests" in f.parts or "test_" in f.name}
        
        # Modules never imported by other modules (excluding entrypoints and __init__.py)
        unimported = all_py - imported_files - entrypoints
        unimported_regular = {f for f in unimported if f.name != "__init__.py"}

        return {
            "total_py_files": len(self.py_files),
            "total_lines_code": sum(self.file_line_counts.values()),
            "binary_files": [str(b.relative_to(self.root)) for b in self.binary_files],
            "unimported_files_count": len(unimported_regular),
            "unimported_files": [str(f.relative_to(self.root)) for f in sorted(unimported_regular)],
            "windows_path_occurrences": {
                str(f.relative_to(self.root)): paths
                for f, paths in self.windows_paths.items()
            },
            "windows_specific_imports": {
                str(f.relative_to(self.root)): imps
                for f, imps in self.windows_imports.items()
            }
        }

if __name__ == "__main__":
    auditor = CodebaseAuditor(ROOT_DIR)
    results = auditor.run()

    report_path = ROOT_DIR / "docs" / "audit_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    import json
    report_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"=== VAZUS CODEBASE AUDIT SUMMARY ===")
    print(f"Total Python Files: {results['total_py_files']}")
    print(f"Total Lines of Code: {results['total_lines_code']}")
    print(f"Binary Assets: {len(results['binary_files'])} ({results['binary_files']})")
    print(f"Unimported / Potentially Dead Python Files: {results['unimported_files_count']}")
    print(f"Files with Hardcoded Windows Paths: {len(results['windows_path_occurrences'])}")
    print(f"Files with Windows-Specific Imports: {len(results['windows_specific_imports'])}")
    print(f"\nDetailed report written to: {report_path}")
