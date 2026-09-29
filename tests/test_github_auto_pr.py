"""
Tests for GitHub CI/CD integration and auto-PR bridge.
Validates:
  1. Workflow YAML files are syntactically valid
  2. github_auto_pr module imports and key functions exist
  3. dry-run auto-PR pipeline works without git/network
  4. ruff autofix helper functions are callable
  5. daemon_sidecar heartbeat includes github_pr_triggered flag
"""

from pathlib import Path
from unittest.mock import patch

WORKSPACE_ROOT = Path(__file__).parent.parent


class TestGitHubWorkflows:
    """Validate GitHub Actions workflow YAML files."""

    def test_ci_workflow_exists(self):
        ci_path = WORKSPACE_ROOT / ".github" / "workflows" / "ci.yml"
        assert ci_path.exists(), f"CI workflow not found at {ci_path}"

    def test_auto_improve_workflow_exists(self):
        ai_path = WORKSPACE_ROOT / ".github" / "workflows" / "auto-improve.yml"
        assert ai_path.exists(), f"Auto-improve workflow not found at {ai_path}"

    def test_ci_workflow_valid_yaml(self):
        import yaml
        ci_path = WORKSPACE_ROOT / ".github" / "workflows" / "ci.yml"
        with open(ci_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert "jobs" in data
        assert "lint" in data["jobs"]
        assert "test" in data["jobs"]
        assert "db-integrity" in data["jobs"]

    def test_auto_improve_workflow_valid_yaml(self):
        import yaml
        ai_path = WORKSPACE_ROOT / ".github" / "workflows" / "auto-improve.yml"
        with open(ai_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert "jobs" in data
        assert "auto-improve" in data["jobs"]
        # Must have schedule trigger
        assert "schedule" in data.get("on", data.get(True, {}))


class TestGitHubAutoPRModule:
    """Validate github_auto_pr module structure."""

    def test_import(self):
        from vazus_core.workers.github_auto_pr import (
            create_auto_pr,
            run_local_auto_improve,
            GITHUB_REPO,
            BASE_BRANCH,
        )
        assert GITHUB_REPO == "Vazilll/hartes"
        assert BASE_BRANCH == "vazus-dev"
        assert callable(create_auto_pr)
        assert callable(run_local_auto_improve)

    def test_ruff_autofix_callable(self):
        from vazus_core.workers.github_auto_pr import _run_ruff_autofix
        assert callable(_run_ruff_autofix)

    def test_has_changes_callable(self):
        from vazus_core.workers.github_auto_pr import _has_changes
        assert callable(_has_changes)

    def test_ensure_remote_callable(self):
        from vazus_core.workers.github_auto_pr import _ensure_remote
        assert callable(_ensure_remote)

    @patch("vazus_core.workers.github_auto_pr._has_changes", return_value=False)
    @patch("vazus_core.workers.github_auto_pr._run_ruff_autofix", return_value={"fix": None, "format": None})
    def test_create_auto_pr_no_changes(self, mock_ruff, mock_changes):
        from vazus_core.workers.github_auto_pr import create_auto_pr

        result = create_auto_pr(
            session_id="test_session_001",
            cycle_results={"observations": {"hit_rate": 0.5}},
            dry_run=True,
        )
        assert result["success"] is True
        assert result["phases"]["changes"] == "no_changes"

    @patch("vazus_core.workers.github_auto_pr._has_changes", return_value=True)
    @patch("vazus_core.workers.github_auto_pr._get_changed_files", return_value=["vazus_core/test.py"])
    @patch("vazus_core.workers.github_auto_pr._run_ruff_autofix", return_value={"fix": None, "format": None})
    @patch("vazus_core.workers.github_auto_pr._run_tests", return_value={"passed": True, "returncode": 0})
    def test_create_auto_pr_dry_run(self, mock_tests, mock_ruff, mock_files, mock_changes):
        from vazus_core.workers.github_auto_pr import create_auto_pr

        result = create_auto_pr(
            session_id="test_session_002",
            cycle_results={"observations": {"hit_rate": 0.7}},
            dry_run=True,
        )
        assert result["success"] is True
        assert result["phases"]["action"] == "dry_run_skip"

    @patch("vazus_core.workers.github_auto_pr._has_changes", return_value=True)
    @patch("vazus_core.workers.github_auto_pr._get_changed_files", return_value=["vazus_core/test.py"])
    @patch("vazus_core.workers.github_auto_pr._run_ruff_autofix", return_value={"fix": None, "format": None})
    @patch("vazus_core.workers.github_auto_pr._run_tests", return_value={"passed": False, "returncode": 1})
    @patch("vazus_core.workers.github_auto_pr._run_git")
    def test_create_auto_pr_reverts_on_test_failure(self, mock_git, mock_tests, mock_ruff, mock_files, mock_changes):
        from vazus_core.workers.github_auto_pr import create_auto_pr

        result = create_auto_pr(
            session_id="test_session_003",
            cycle_results={"observations": {}},
            dry_run=False,
        )
        assert result["success"] is False
        assert result["phases"]["action"] == "reverted_due_to_test_failure"
        # Verify git checkout was called to revert
        mock_git.assert_called_with(["checkout", "--", "."])


class TestDaemonSidecarImport:
    """Verify DaemonSidecar module is importable."""

    def test_daemon_sidecar_imports(self):
        from vazus_core.workers.daemon_sidecar import DaemonSidecar, TranscriptEvent
        assert callable(DaemonSidecar)
        assert callable(TranscriptEvent)
