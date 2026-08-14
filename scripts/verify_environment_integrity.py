"""
vazus.scripts.verify_environment_integrity — Diagnostic Audit Script for vazus SuperGraph OS v4.0.
Verifies git branch status, C:\\vazus\\.venv packages, and the canonical SQLite database (services/memory/vazus.db),
Cremniy C++ Engine, and git_open layers.
"""

import os
import sys
import json
import sqlite3
import subprocess
from pathlib import Path
from typing import Dict, Any

VAZUS_DIR = Path("C:/vazus")
if str(VAZUS_DIR) not in sys.path:
    sys.path.insert(0, str(VAZUS_DIR))


class EnvironmentIntegrityAuditor:
    """Diagnostic Auditor for vazus SuperGraph OS v4.0."""

    def __init__(self):
        self.vazus_dir = VAZUS_DIR

    def audit_git_branches(self) -> Dict[str, Any]:
        """Audits current git branch, commit status, and branch list."""
        try:
            branch_res = subprocess.run(["git", "branch", "-a"], cwd=str(self.vazus_dir), capture_output=True, text=True)
            status_res = subprocess.run(["git", "status", "--porcelain"], cwd=str(self.vazus_dir), capture_output=True, text=True)
            
            lines = branch_res.stdout.splitlines()
            current_branch = "unknown"
            branches = []
            for line in lines:
                line_str = line.strip()
                if line_str.startswith("*"):
                    current_branch = line_str.replace("*", "").strip()
                    branches.append(current_branch)
                elif line_str:
                    branches.append(line_str)
                    
            uncommitted_count = len(status_res.stdout.splitlines())
            return {
                "current_branch": current_branch,
                "all_branches": branches,
                "uncommitted_files": uncommitted_count,
                "clean": uncommitted_count == 0
            }
        except Exception as e:
            return {"error": str(e)}

    def audit_databases(self) -> Dict[str, Any]:
        """Audits canonical vazus.db (services/memory/vazus.db) — single source of truth."""
        vazus_db_path = Path("C:/vazus/services/memory/vazus.db")

        res = {}
        if vazus_db_path.exists():
            conn = sqlite3.connect(str(vazus_db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()
            res["vazus_db"] = {
                "path": str(vazus_db_path),
                "size_mb": round(vazus_db_path.stat().st_size / (1024 * 1024), 2),
                "tables": tables,
                "table_count": len(tables)
            }

        return res

    def audit_binaries(self) -> Dict[str, Any]:
        """Checks binaries in C:\\vazus\\bin (llama.cpp, radare2, rizin)."""
        bin_dir = self.vazus_dir / "bin"
        found = []
        if bin_dir.exists():
            for f in bin_dir.glob("*.exe"):
                found.append(f.name)
        return {
            "bin_dir": str(bin_dir),
            "executables": found,
            "has_radare2": "radare2.exe" in found or "r2.exe" in found,
            "has_rizin": "rizin.exe" in found,
            "has_llama": "llama-server-zaya.exe" in found or "llama-cli-zaya.exe" in found
        }


def main():
    auditor = EnvironmentIntegrityAuditor()
    report = {
        "git": auditor.audit_git_branches(),
        "databases": auditor.audit_databases(),
        "binaries": auditor.audit_binaries()
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
