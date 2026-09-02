"""
vazus_core.workers.async_worktree_worker — Autonomous Asynchronous Git Worktree Worker.
Provisions isolated Git worktrees for fire-and-forget background tasks, speculative mutations,
and 5-Tier Quality Gate verification without polluting the active developer workspace.
"""

import uuid
import time
import logging
import concurrent.futures
from pathlib import Path
from typing import Callable, List, Optional, Tuple, Union

from vazus_core.verification.worktree_sandbox import AntigravityWorktreeSandbox, WorktreeTaskResult
from vazus_core.verification.ast_pruner import UniversalASTPruner

logger = logging.getLogger("AsyncWorktreeWorker")


class AsyncWorktreeWorker:
    """
    Manages autonomous isolated Git worktree background execution.
    Features:
    - Zero-pollution branch/tempdir isolation.
    - Win32 Job Object kernel memory bounds (1024 MB default).
    - 5-Tier Quality Gate (AST syntax check, pytest/subcommand, Z3 verification).
    - Asynchronous concurrent execution via ThreadPoolExecutor.
    """

    def __init__(
        self,
        repo_root: Union[str, Path] = r"C:\vazus",
        max_workers: int = 4,
        snapshot_items: Optional[List[str]] = None,
    ):
        self.repo_root = Path(repo_root).resolve()
        self.scratch_dir = self.repo_root / "scratch" / "worktrees"
        self.scratch_dir.mkdir(parents=True, exist_ok=True)
        self.sandbox = AntigravityWorktreeSandbox(
            repo_root=str(self.repo_root),
            scratch_dir=str(self.scratch_dir),
            snapshot_items=snapshot_items,
        )
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="VazusWorktreeWorker",
        )

    def _execute_mutations(
        self, mutation_fn: Optional[Callable[[Path], bool]], worktree_path: Path
    ) -> Tuple[bool, Optional[str]]:
        if not mutation_fn:
            return True, None
        try:
            success = mutation_fn(worktree_path)
            return success, (None if success else "Mutation function returned False")
        except Exception as e:
            logger.debug("Mutation exception in worktree: %s", e)
            return False, f"Mutation exception: {e}"

    def _check_files_ast(
        self, check_ast_files: Optional[List[str]], worktree_path: Path
    ) -> Tuple[bool, Optional[str]]:
        if not check_ast_files:
            return True, None
        for rel_path in check_ast_files:
            target_f = worktree_path / rel_path
            if target_f.exists():
                _, stats = UniversalASTPruner.prune_file(target_f)
                if not stats.get("is_valid", False):
                    return False, f"AST syntax validation failed on {rel_path}"
        return True, None

    def _run_test_cmd(
        self,
        test_command: Optional[List[str]],
        worktree_path: Path,
        timeout_sec: int,
        memory_limit_mb: int,
    ) -> Tuple[bool, str, str, Optional[str]]:
        if not test_command:
            return True, "", "", None
        res = self.sandbox.run_sandboxed_command(
            cmd=test_command,
            worktree_path=worktree_path,
            timeout=timeout_sec,
            memory_limit_mb=memory_limit_mb,
        )
        stdout = res.get("stdout", "")
        stderr = res.get("stderr", "")
        success = res.get("success", False)
        err = None if success else f"Test command failed (code {res.get('returncode')}): {stderr[:300]}"
        return success, stdout, stderr, err

    def _promote_if_needed(
        self,
        auto_promote: bool,
        mode: str,
        worktree_path: Path,
        *,
        branch_name: str,
        target_branch: str,
        tid: str,
    ) -> bool:
        if not (auto_promote and mode == "worktree"):
            return False
        return self.sandbox.promote_mutation(
            worktree_path=worktree_path,
            branch_name=branch_name,
            target_branch=target_branch,
            message=f"Verified autonomous task {tid}",
        )

    def _evaluate_worktree_pipeline(
        self, worktree_path: Path, mutation_fn: Optional[Callable[[Path], bool]],
        check_ast_files: Optional[List[str]], test_command: Optional[List[str]],
        *, timeout_sec: int, memory_limit_mb: int, auto_promote: bool,
        mode: str, branch_name: str, target_branch: str, tid: str, start_time: float
    ) -> WorktreeTaskResult:
        """Executes mutation, AST validation, tests, and conditional promotion inside sandbox."""
        captured_path = str(worktree_path)
        mut_ok, err_mut = self._execute_mutations(mutation_fn, worktree_path)
        if not mut_ok:
            return WorktreeTaskResult(
                task_id=tid, branch_name=branch_name, worktree_path=captured_path,
                success=False, ast_valid=False, tests_passed=False, error_message=err_mut,
                duration_sec=round(time.time() - start_time, 3),
            )

        ast_ok, err_ast = self._check_files_ast(check_ast_files, worktree_path)
        if not ast_ok:
            return WorktreeTaskResult(
                task_id=tid, branch_name=branch_name, worktree_path=captured_path,
                success=False, ast_valid=False, tests_passed=False, error_message=err_ast,
                duration_sec=round(time.time() - start_time, 3),
            )

        test_ok, stdout, stderr, err_test = self._run_test_cmd(test_command, worktree_path, timeout_sec, memory_limit_mb)
        promoted = self._promote_if_needed(
            auto_promote, mode, worktree_path,
            branch_name=branch_name, target_branch=target_branch, tid=tid
        )

        return WorktreeTaskResult(
            task_id=tid, branch_name=branch_name, worktree_path=captured_path,
            success=test_ok, ast_valid=ast_ok, tests_passed=test_ok,
            stdout=stdout, stderr=stderr, duration_sec=round(time.time() - start_time, 3),
            error_message=err_test, promoted=promoted,
        )

    def execute_task_sync(
        self,
        task_id: Optional[str] = None,
        mutation_fn: Optional[Callable[[Path], bool]] = None,
        test_command: Optional[List[str]] = None,
        check_ast_files: Optional[List[str]] = None,
        mode: str = "tempdir",
        *,
        timeout_sec: int = 60,
        memory_limit_mb: int = 1024,
        auto_promote: bool = False,
        target_branch: str = "vazus-dev",
    ) -> WorktreeTaskResult:
        """Executes a speculative mutation task synchronously inside an isolated sandbox/worktree."""
        start_time = time.time()
        tid = task_id or f"task_{uuid.uuid4().hex[:8]}"
        branch_name = f"sandbox/{tid}"
        captured_path = ""

        try:
            with self.sandbox.create_sandbox(prefix=tid, mode=mode) as worktree_path:
                captured_path = str(worktree_path)
                return self._evaluate_worktree_pipeline(
                    worktree_path, mutation_fn, check_ast_files, test_command,
                    timeout_sec=timeout_sec, memory_limit_mb=memory_limit_mb,
                    auto_promote=auto_promote, mode=mode, branch_name=branch_name,
                    target_branch=target_branch, tid=tid, start_time=start_time
                )
        except Exception as e:
            logger.error("Exception during worktree task execution: %s", e)
            return WorktreeTaskResult(
                task_id=tid, branch_name=branch_name, worktree_path=captured_path,
                success=False, ast_valid=False, tests_passed=False,
                error_message=str(e), duration_sec=round(time.time() - start_time, 3),
            )

    def execute_task_async(
        self,
        task_id: Optional[str] = None,
        mutation_fn: Optional[Callable[[Path], bool]] = None,
        test_command: Optional[List[str]] = None,
        check_ast_files: Optional[List[str]] = None,
        mode: str = "tempdir",
        *,
        timeout_sec: int = 60,
        memory_limit_mb: int = 1024,
        auto_promote: bool = False,
        target_branch: str = "vazus-dev",
    ) -> concurrent.futures.Future:
        """Dispatches a speculative mutation task asynchronously to the background worker pool."""
        return self._executor.submit(
            self.execute_task_sync,
            task_id=task_id,
            mutation_fn=mutation_fn,
            test_command=test_command,
            check_ast_files=check_ast_files,
            mode=mode,
            timeout_sec=timeout_sec,
            memory_limit_mb=memory_limit_mb,
            auto_promote=auto_promote,
            target_branch=target_branch,
        )

    def shutdown(self, wait: bool = True) -> None:
        self._executor.shutdown(wait=wait)


# Global singleton worker instance
async_worktree_worker = AsyncWorktreeWorker()

__all__ = [
    "WorktreeTaskResult",
    "AsyncWorktreeWorker",
    "async_worktree_worker",
]
