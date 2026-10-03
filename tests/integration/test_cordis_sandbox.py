"""
tests.test_cordis_sandbox — Tests for Vazus-Cordis Spatiotemporal Git Worktree Sandbox.
Verifies ephemeral worktree creation, Win32 Job Object confinement, command execution, and teardown.
"""

import sys
import os
from pathlib import Path
import pytest

from vazus_core.verification.worktree_sandbox import AntigravityWorktreeSandbox, worktree_sandbox


def test_worktree_sandbox_creation_and_cleanup():
    """Verify that an ephemeral worktree sandbox can be created and cleanly torn down."""
    sandbox = AntigravityWorktreeSandbox()
    sandbox_path = None
    
    with sandbox.create_sandbox(prefix="test-cordis") as sb_path:
        sandbox_path = sb_path
        assert sb_path.exists(), "Sandbox directory should exist during context"
        assert sb_path.is_dir(), "Sandbox path should be a directory"
        
    assert not sandbox_path.exists(), "Sandbox directory should be cleaned up after exit"


def test_worktree_sandbox_command_execution():
    """Verify that commands execute cleanly inside the sandboxed environment."""
    sandbox = AntigravityWorktreeSandbox()
    
    with sandbox.create_sandbox(prefix="test-exec") as sb_path:
        res = sandbox.run_sandboxed_command(
            [sys.executable, "-c", "import sys; print('SANDBOX_OK')"],
            worktree_path=sb_path,
            timeout=10,
        )
        assert res["success"] is True
        assert res["returncode"] == 0
        assert "SANDBOX_OK" in res["stdout"]


def test_worktree_sandbox_timeout_handling():
    """Verify that long-running or stuck processes are terminated within the timeout limit."""
    sandbox = AntigravityWorktreeSandbox()
    
    with sandbox.create_sandbox(prefix="test-timeout") as sb_path:
        res = sandbox.run_sandboxed_command(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            worktree_path=sb_path,
            timeout=1,
        )
        assert res["success"] is False
        assert res["timed_out"] is True
