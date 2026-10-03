"""
vazus_core.codemods.ast_grep_runner
Layer 3 Component: Wrapper for ast-grep (sg) Tree-sitter structural pattern matcher and rewriter.
"""

import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("vazus_core.codemods")


class AstGrepRunner:
    """
    Executes ast-grep structural patterns and rewrites on Python and multi-language files.
    """

    def __init__(self, workspace_root: str = r"C:\vazus"):
        self.workspace_root = Path(workspace_root).resolve()
        self.cmd_path = self._find_ast_grep_bin()

    def _find_ast_grep_bin(self) -> str:
        """Locates the ast-grep executable (preferring .cmd on Windows)."""
        candidates = ["ast-grep.cmd", "sg.cmd", "ast-grep", "sg"]
        for c in candidates:
            path = shutil.which(c)
            if path:
                return path
        # Common global npm path on Windows
        npm_path = Path(os.environ.get("APPDATA", "")) / "npm" / "ast-grep.cmd"
        if npm_path.exists():
            return str(npm_path)
        return "ast-grep.cmd"

    def find_pattern(self, pattern: str, lang: str = "python", subpath: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Searches for structural pattern occurrences using ast-grep --json.
        """
        target_dir = self.workspace_root / subpath if subpath else self.workspace_root
        cmd = [self.cmd_path, "run", "--pattern", pattern, "--lang", lang, "--json=stream", str(target_dir)]

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
            matches = []
            for line in res.stdout.strip().splitlines():
                line = line.strip()
                if line.startswith("{"):
                    try:
                        matches.append(json.loads(line))
                    except json.JSONDecodeError as exc:
                        logger.debug("Failed to decode ast-grep JSON line: %s", exc)
            return matches
        except Exception as e:
            logger.error(f"Error running ast-grep find_pattern: {e}")
            return []

    def rewrite_pattern(
        self, pattern: str, rewrite: str, lang: str = "python", subpath: Optional[str] = None, dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Applies structural replacement across files matching pattern -> rewrite.
        """
        target_dir = self.workspace_root / subpath if subpath else self.workspace_root
        cmd = [
            self.cmd_path,
            "run",
            "--pattern",
            pattern,
            "--rewrite",
            rewrite,
            "--lang",
            lang,
        ]
        if not dry_run:
            cmd.append("--update-all")
        cmd.append(str(target_dir))

        try:
            res = subprocess.run(
                cmd,
                cwd=str(self.workspace_root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=45,
            )
            return {"success": res.returncode == 0, "stdout": res.stdout, "stderr": res.stderr, "dry_run": dry_run}
        except Exception as e:
            logger.error(f"Error executing ast-grep rewrite_pattern: {e}")
            return {"success": False, "error": str(e), "dry_run": dry_run}
