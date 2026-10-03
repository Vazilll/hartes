"""
vazus_core.codemods.codemod_router
Layer 3 Component: Multi-Tier Codemod Router.

Orchestrates code transformations across:
- Tier 0: Ruff (5ms unused imports / locals hygiene)
- Tier 1: ast-grep (Fast structural Tree-sitter replacements)
- Tier 2: GritQL (Declarative context migrations)
- Tier 3: LibCST (100% comment/whitespace-preserving CST mutations)
"""

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional, Set

from .ast_grep_runner import AstGrepRunner
from .libcst_pruner import LibCSTPruner

logger = logging.getLogger("vazus_core.codemods")


class CodemodRouter:
    """
    Unified router that selects and applies the appropriate transformation tier.
    """

    def __init__(self, workspace_root: str = r"C:\vazus"):
        self.workspace_root = Path(workspace_root).resolve()
        self.ast_grep = AstGrepRunner(str(self.workspace_root))
        self.cst_pruner = LibCSTPruner()
        self.ruff_bin = self._find_ruff_bin()

    def _find_ruff_bin(self) -> str:
        """Locates the ruff executable in venv, PATH, or cmd wrappers."""
        venv_ruff = self.workspace_root / ".venv" / "Scripts" / "ruff.exe"
        if venv_ruff.exists():
            return str(venv_ruff)
        found = shutil.which("ruff")
        if found:
            return found
        return "ruff"

    def run_ruff_hygiene(self, target_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Tier 0: Runs ruff check --fix --select F401,F841,UP,B007 for sub-10ms cleanup.
        """
        path = self.workspace_root / target_path if target_path else self.workspace_root
        cmd = [self.ruff_bin, "check", "--fix", "--select", "F401,F841,UP,B007", str(path)]
        try:
            res = subprocess.run(
                cmd,
                cwd=str(self.workspace_root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=30,
            )
            return {"success": res.returncode == 0, "tier": "Tier 0 (Ruff)", "stdout": res.stdout, "stderr": res.stderr}
        except Exception as e:
            logger.error(f"Ruff hygiene error: {e}")
            return {"success": False, "tier": "Tier 0 (Ruff)", "error": str(e)}

    def apply_structural_rewrite(
        self, pattern: str, rewrite: str, lang: str = "python", dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Tier 1: Applies structural Tree-sitter replacement via ast-grep.
        """
        res = self.ast_grep.rewrite_pattern(pattern, rewrite, lang=lang, dry_run=dry_run)
        res["tier"] = "Tier 1 (ast-grep)"
        return res

    def excise_dead_functions_in_file(self, rel_file_path: str, dead_functions: Set[str]) -> Dict[str, Any]:
        """
        Tier 3: Uses LibCST to excise dead functions cleanly while preserving comments and formatting,
        followed by Tier 0 Ruff hygiene to clean up any orphaned imports.
        """
        full_path = self.workspace_root / rel_file_path
        if not full_path.exists():
            return {"success": False, "error": f"File {rel_file_path} not found"}

        try:
            original_code = full_path.read_text(encoding="utf-8")
            transformed_code, count = self.cst_pruner.excise_dead_functions(original_code, dead_functions)

            if count > 0:
                full_path.write_text(transformed_code, encoding="utf-8")
                # Post-excision hygiene pass to eliminate newly orphaned imports
                self.run_ruff_hygiene(rel_file_path)

            return {
                "success": True,
                "tier": "Tier 3 (LibCST) + Tier 0 (Ruff)",
                "file": rel_file_path,
                "excised_count": count,
            }
        except Exception as e:
            logger.error(f"Error excising dead functions in {rel_file_path}: {e}")
            return {"success": False, "tier": "Tier 3 (LibCST)", "error": str(e)}
