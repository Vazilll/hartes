r"""
vazus_core.verification.candidate_harvester
Layer 4 Component: Candidate Optimization & Dead Code Harvester.

Computes the safe candidate set via mathematical intersection:
C_candidate = (C_static_0ref ∩ C_dynamic_0hit) \ W_protect
"""

import ast
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from vazus_core.memory.db import DEFAULT_VAZUS_DB, get_db_connection
from vazus_core.memory.whitelist_manager import WhitelistManager

logger = logging.getLogger("vazus_core.verification")


class CandidateHarvester:
    """
    Finds dead functions and optimization candidates through static AST analysis,
    runtime PEP 669 telemetry hits, and whitelist safety filters.
    """

    def __init__(self, workspace_root: str = r"C:\vazus", db_path: str = DEFAULT_VAZUS_DB):
        import os

        self.workspace_root = Path(workspace_root).resolve()
        self.db_path = db_path if db_path != DEFAULT_VAZUS_DB else os.getenv("VAZUS_DB_PATH", DEFAULT_VAZUS_DB)
        self.whitelist_mgr = WhitelistManager(self.db_path)

    def scan_file_definitions_and_references(self, file_path: Path) -> Tuple[Set[str], Set[str], bool]:
        """
        Parses a Python file and returns:
        (defined_functions, referenced_names, has_dynamic_reflection)
        """
        defined_functions = set()
        referenced_names = set()
        has_dynamic_reflection = False

        try:
            tree = ast.parse(file_path.read_text(encoding="utf-8", errors="ignore"))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    defined_functions.add(node.name)
                elif isinstance(node, ast.Name):
                    referenced_names.add(node.id)
                    if node.id in ("getattr", "globals", "locals", "eval", "exec", "import_module"):
                        has_dynamic_reflection = True
                elif isinstance(node, ast.Attribute):
                    referenced_names.add(node.attr)
        except Exception as e:
            logger.warning(f"Failed to parse {file_path}: {e}")

        return defined_functions, referenced_names, has_dynamic_reflection

    def _collect_global_references(self) -> Tuple[Set[str], List[Path]]:
        """Collects all references and valid python files across the entire workspace."""
        global_referenced_names = set()
        all_py_files = []
        for py_file in self.workspace_root.rglob("*.py"):
            if any(part in py_file.parts for part in (".venv", "__pycache__", ".git", ".pytest_cache")):
                continue
            all_py_files.append(py_file)
            _, refs, _ = self.scan_file_definitions_and_references(py_file)
            global_referenced_names.update(refs)
        return global_referenced_names, all_py_files

    def _query_dynamic_hits(self) -> Dict[str, int]:
        """Queries dynamic execution hits from database telemetry."""
        dynamic_hits_map = {}
        try:
            conn = get_db_connection(self.db_path)
            cur = conn.cursor()
            cur.execute("SELECT function_fqn, hit_count FROM telemetry_function_hits;")
            for fqn, hits in cur.fetchall():
                dynamic_hits_map[fqn] = hits
            conn.close()
        except Exception as exc:
            logger.debug("Telemetry hits query skipped or failed: %s", exc)
        return dynamic_hits_map

    def harvest_dead_function_candidates(self, target_subdir: Optional[str] = None) -> List[Dict[str, Any]]:
        """Identifies verified dead functions across workspace files."""
        candidates = []
        root = self.workspace_root / target_subdir if target_subdir else self.workspace_root
        whitelist = self.whitelist_mgr.get_whitelist()
        global_referenced_names, all_py_files = self._collect_global_references()
        dynamic_hits_map = self._query_dynamic_hits()

        for py_file in all_py_files:
            if target_subdir and not str(py_file).startswith(str(root)):
                continue
            defs, _, has_reflection = self.scan_file_definitions_and_references(py_file)
            if has_reflection:
                continue

            rel_path = str(py_file.relative_to(self.workspace_root)).replace("\\", "/")
            for fn_name in defs:
                if fn_name in whitelist or fn_name.startswith("__"):
                    continue

                is_private = fn_name.startswith("_")
                static_unreferenced = fn_name not in global_referenced_names
                dynamic_hits = sum(
                    hits for fqn, hits in dynamic_hits_map.items() if fqn.startswith(rel_path) and f":{fn_name}#" in fqn
                )

                if static_unreferenced and dynamic_hits == 0:
                    candidates.append(
                        {
                            "file": rel_path,
                            "function_name": fn_name,
                            "is_private": is_private,
                            "static_references": 0,
                            "dynamic_hits": dynamic_hits,
                            "safety_level": "HIGH" if is_private else "MEDIUM",
                        }
                    )

        return candidates
