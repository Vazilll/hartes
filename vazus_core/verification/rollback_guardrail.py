"""
vazus_core.rollback_guardrail — Automated Rollback Guardrail & Git Provenance Integration.
Provides byte-level file snapshot backup/restoration and Git rollback on failure for Vazus SuperGraph OS v4.0.
"""

import logging
import subprocess
from pathlib import Path
from typing import Any, Callable, List, Optional, Union

from vazus_core.verification.git_provenance import GitProvenanceManager

logger = logging.getLogger("RollbackGuardrail")


class RollbackGuardrail:
    """
    Automated Rollback Guardrail for safe code optimization and modification.
    Creates snapshot backups, executes optimization routines and verification tests,
    and automatically reverts changes via GitProvenanceManager when failures occur.
    """

    def __init__(self, repo_dir: str = r"C:\vazus"):
        self.repo_dir = repo_dir
        self.git_manager = GitProvenanceManager()

    @staticmethod
    def execute_with_guardrail(
        target_file: Union[str, Path],
        opt_func: Callable[[], Any],
        test_cmd: List[str]
    ) -> bool:
        """
        Executes code modification with file-level snapshot restoration guardrail.
        If opt_func or test_cmd fails, target_file is restored to original state.
        """
        target_path = Path(target_file).resolve()
        file_existed = target_path.exists()
        backup_content: Optional[bytes] = None

        if file_existed:
            backup_content = target_path.read_bytes()

        try:
            # Step 1: Run optimization function
            opt_res = opt_func()
            if opt_res is False:
                logger.warning(f"[RollbackGuardrail] Optimization function returned False. Restoring {target_path}")
                RollbackGuardrail._restore_file(target_path, file_existed, backup_content)
                return False

            # Step 2: Run test suite command
            proc = subprocess.run(test_cmd, capture_output=True, text=True)
            if proc.returncode != 0:
                logger.warning(f"[RollbackGuardrail] Test command failed (code {proc.returncode}). Restoring {target_path}")
                RollbackGuardrail._restore_file(target_path, file_existed, backup_content)
                return False

            # Optimization and verification passed
            return True

        except Exception as e:
            logger.error(f"[RollbackGuardrail] Exception during guardrail execution: {e}. Restoring {target_path}")
            RollbackGuardrail._restore_file(target_path, file_existed, backup_content)
            return False

    @classmethod
    def rollback_on_failure(
        cls,
        target_files: Optional[Union[str, List[str]]] = None,
        commit_hash: Optional[str] = None,
        repo_dir: str = r"C:\vazus"
    ) -> bool:
        """
        Snapshot-isolated rollback for specific target files or commit hash.
        Prevents destructive global working tree wiping.
        """
        logger.warning(
            f"[RollbackGuardrail] Initiating snapshot-isolated rollback for target files: {target_files or 'modified tracked'}, commit: {commit_hash or 'HEAD'}"
        )
        return GitProvenanceManager.revert_commit(commit_hash=commit_hash, target_files=target_files, repo_dir=repo_dir)

    @staticmethod
    def _restore_file(target_path: Path, existed: bool, content: Optional[bytes]) -> None:
        """Internal helper to restore file bytes snapshot."""
        if existed and content is not None:
            target_path.write_bytes(content)
        elif not existed and target_path.exists():
            target_path.unlink()
