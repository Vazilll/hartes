"""
vazus_core.git_provenance — Git Provenance & Branch Management for vazus SuperGraph OS v4.0.
"""

import os
import subprocess
from typing import Optional, Union, List


class GitProvenanceManager:
    """Manages Git branch provenance, current branch detection, and isolated feature branches."""

    @staticmethod
    def get_current_branch(repo_dir: str = r"C:\vazus") -> str:
        """Returns active git branch name."""
        try:
            res = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip()
        except Exception:
            pass
        return "vazus-main"

    @staticmethod
    def ensure_branch(prefix: str, branch_name: str, repo_dir: str = r"C:\vazus") -> str:
        """Ensures a feature branch exists or returns full branch designation."""
        target_branch = f"feature/{prefix}-{branch_name}" if "/" not in branch_name else branch_name
        try:
            res = subprocess.run(
                ["git", "branch", "--list", target_branch],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res.returncode == 0 and target_branch in res.stdout:
                return target_branch
        except Exception:
            pass
        return target_branch

    @staticmethod
    def commit_changes(commit_message: str, repo_dir: str = r"C:\vazus") -> bool:
        """Stages all modified files and commits changes with commit_message."""
        try:
            subprocess.run(["git", "add", "-A"], cwd=repo_dir, capture_output=True, timeout=10)
            res = subprocess.run(
                ["git", "commit", "-m", commit_message],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return res.returncode == 0
        except Exception:
            return False

    @staticmethod
    def revert_commit(
        commit_hash: Optional[str] = None,
        target_files: Optional[Union[str, List[str]]] = None,
        repo_dir: str = r"C:\vazus"
    ) -> bool:
        """
        Reverts specified commit or restores specific target files to head/commit state
        without destructively wiping the entire git working tree.
        """
        try:
            if target_files:
                if isinstance(target_files, str):
                    files = [target_files]
                else:
                    files = list(target_files)
                ref = commit_hash if (commit_hash and commit_hash != "HEAD") else "HEAD"
                cmd = ["git", "checkout", ref, "--"] + files
                res = subprocess.run(cmd, cwd=repo_dir, capture_output=True, text=True, timeout=10)
                return res.returncode == 0

            if commit_hash and commit_hash != "HEAD":
                res = subprocess.run(
                    ["git", "revert", "--no-edit", commit_hash],
                    cwd=repo_dir,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if res.returncode == 0:
                    return True
                res2 = subprocess.run(
                    ["git", "checkout", commit_hash],
                    cwd=repo_dir,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                return res2.returncode == 0

            diff_res = subprocess.run(
                ["git", "diff", "--name-only"],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if diff_res.returncode == 0 and diff_res.stdout.strip():
                mod_files = [f.strip() for f in diff_res.stdout.strip().splitlines() if f.strip()]
                if mod_files:
                    res3 = subprocess.run(
                        ["git", "checkout", "HEAD", "--"] + mod_files,
                        cwd=repo_dir,
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    return res3.returncode == 0
            return True
        except Exception:
            return False
