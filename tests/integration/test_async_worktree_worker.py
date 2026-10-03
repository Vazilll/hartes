"""
Unit tests for vazus_core.workers.async_worktree_worker.
"""

import sys
from pathlib import Path
from vazus_core.workers.async_worktree_worker import (
    AsyncWorktreeWorker,
    WorktreeTaskResult,
)


def test_worktree_task_sync_execution():
    worker = AsyncWorktreeWorker(repo_root=r"C:\vazus")

    def mutate_file(worktree_dir: Path) -> bool:
        test_file = worktree_dir / "sample_mutation.txt"
        test_file.write_text("Speculative mutation content", encoding="utf-8")
        return True

    python_exe = str(Path(r"C:\vazus\.venv\Scripts\python.exe"))
    if not Path(python_exe).exists():
        python_exe = sys.executable

    res: WorktreeTaskResult = worker.execute_task_sync(
        task_id="test_sync_01",
        mutation_fn=mutate_file,
        test_command=[python_exe, "-c", "print('Validation Command Succeeded')"],
        mode="tempdir",
        timeout_sec=15,
        auto_promote=False,
    )

    assert res.success is True
    assert res.ast_valid is True
    assert res.tests_passed is True
    assert res.duration_sec > 0.0
    assert "Validation Command Succeeded" in res.stdout
    assert not Path(res.worktree_path).exists()


def test_worktree_task_async_future():
    worker = AsyncWorktreeWorker(repo_root=r"C:\vazus", max_workers=2)

    python_exe = str(Path(r"C:\vazus\.venv\Scripts\python.exe"))
    if not Path(python_exe).exists():
        python_exe = sys.executable

    future = worker.execute_task_async(
        task_id="test_async_02",
        test_command=[python_exe, "-c", "import sys; sys.exit(0)"],
        mode="tempdir",
        timeout_sec=30,
    )

    res: WorktreeTaskResult = future.result(timeout=60)
    assert res.success is True
    assert res.tests_passed is True
    assert res.task_id == "test_async_02"
    assert not Path(res.worktree_path).exists()
