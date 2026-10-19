#!/usr/bin/env python3
"""
vazus_core.workers.github_auto_pr — Local-to-GitHub Auto-PR Bridge.
=====================================================================

Bridges local AutoImproverDaemon improvements to GitHub PRs.
Can be triggered by daemon_sidecar heartbeat or manually.

Flow:
  1. AutoImproverDaemon.run_cycle() detects improvements
  2. ruff auto-fixes applied
  3. Git branch created, changes committed
  4. PR pushed to Vazilll/hartes via GitHub MCP or REST API

Usage:
  python -m vazus_core.workers.github_auto_pr [--dry-run] [--force]
"""

import datetime
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("vazus_core.workers.github_auto_pr")

WORKSPACE_ROOT = Path(r"/home/tarhes/Проекты/vazus")
GITHUB_REPO = "Vazilll/hartes"
BASE_BRANCH = "vazus-dev"
GIT_USER_NAME = "Vazus AutoImprover"
GIT_USER_EMAIL = "vazus-bot@users.noreply.github.com"


def _run_git(args: List[str], cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
    """Run a git command and return the result."""
    cmd = ["git"] + args
    return subprocess.run(
        cmd,
        cwd=str(cwd or WORKSPACE_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
        encoding="utf-8",
        errors="replace",
    )


def _run_ruff_autofix(cwd: Optional[Path] = None) -> Dict[str, Any]:
    """Run ruff auto-fix and format on vazus_core/."""
    results = {"fix": None, "format": None}
    target = cwd or WORKSPACE_ROOT

    try:
        fix_res = subprocess.run(
            [sys.executable, "-m", "ruff", "check", "--fix", "--select", "E9,F,I", "vazus_core/"],
            cwd=str(target),
            capture_output=True,
            text=True,
            timeout=30,
            encoding="utf-8",
            errors="replace",
        )
        results["fix"] = {"returncode": fix_res.returncode, "stdout": fix_res.stdout[:500]}
    except Exception as e:
        results["fix"] = {"error": str(e)}

    try:
        fmt_res = subprocess.run(
            [sys.executable, "-m", "ruff", "format", "vazus_core/"],
            cwd=str(target),
            capture_output=True,
            text=True,
            timeout=30,
            encoding="utf-8",
            errors="replace",
        )
        results["format"] = {"returncode": fmt_res.returncode, "stdout": fmt_res.stdout[:500]}
    except Exception as e:
        results["format"] = {"error": str(e)}

    return results


def _run_tests(cwd: Optional[Path] = None) -> Dict[str, Any]:
    """Run portable tests (excluding hardware-specific ones)."""
    target = cwd or WORKSPACE_ROOT
    venv_pytest = target / ".venv" / "Scripts" / "pytest.exe"

    try:
        cmd_parts = [str(venv_pytest)] if venv_pytest.exists() else [sys.executable, "-m", "pytest"]
        cmd_parts.extend(
            [
                "tests/",
                "-x",
                "-q",
                "--tb=short",
                "-k",
                "not npu and not openvino and not wsb and not sandbox and not silicon and not hardware and not gemma",
                "--ignore=tests/future_specs",
                "--timeout=120",
            ]
        )
        result = subprocess.run(
            cmd_parts,
            cwd=str(target),
            capture_output=True,
            text=True,
            timeout=180,
            encoding="utf-8",
            errors="replace",
        )
        return {
            "returncode": result.returncode,
            "passed": result.returncode == 0,
            "stdout": result.stdout[-2000:],
            "stderr": result.stderr[-500:],
        }
    except Exception as e:
        return {"passed": False, "error": str(e)}


def _has_changes(cwd: Optional[Path] = None) -> bool:
    """Check if there are uncommitted changes in tracked files."""
    res = _run_git(["diff", "--quiet"], cwd)
    if res.returncode != 0:
        return True
    res2 = _run_git(["diff", "--cached", "--quiet"], cwd)
    return res2.returncode != 0


def _get_changed_files(cwd: Optional[Path] = None) -> List[str]:
    """Get list of changed files."""
    res = _run_git(["diff", "--name-only"], cwd)
    return [f for f in res.stdout.strip().split("\n") if f]


def _ensure_remote(cwd: Optional[Path] = None) -> bool:
    """Ensure 'origin' remote points to Vazilll/hartes."""
    res = _run_git(["remote", "-v"], cwd)
    if "origin" not in res.stdout:
        add_res = _run_git(["remote", "add", "origin", f"https://github.com/{GITHUB_REPO}.git"], cwd)
        return add_res.returncode == 0
    return True


def create_auto_pr(
    session_id: str,
    cycle_results: Dict[str, Any],
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Full pipeline: ruff fix → test → branch → commit → push → PR.

    Args:
        session_id: AutoImproverDaemon session ID
        cycle_results: Results from daemon.run_cycle()
        dry_run: If True, don't actually push or create PR

    Returns:
        Dict with status, branch name, and PR URL (if created)
    """
    report: Dict[str, Any] = {
        "session_id": session_id,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "phases": {},
        "pr_url": None,
        "success": False,
    }

    # Phase 1: Auto-fix
    logger.info("Phase 1: Running ruff auto-fix...")
    ruff_res = _run_ruff_autofix()
    report["phases"]["ruff"] = ruff_res

    # Phase 2: Check for changes
    if not _has_changes():
        report["phases"]["changes"] = "no_changes"
        report["success"] = True
        logger.info("No changes detected after auto-fix. Skipping PR.")
        return report

    changed_files = _get_changed_files()
    report["phases"]["changes"] = {"files": changed_files, "count": len(changed_files)}
    logger.info(f"Found {len(changed_files)} changed files")

    # Phase 3: Run tests
    logger.info("Phase 3: Running tests...")
    test_res = _run_tests()
    report["phases"]["tests"] = test_res
    if not test_res.get("passed", False):
        logger.warning("Tests failed after auto-fix. Reverting changes.")
        _run_git(["checkout", "--", "."])
        report["phases"]["action"] = "reverted_due_to_test_failure"
        return report

    if dry_run:
        report["phases"]["action"] = "dry_run_skip"
        report["success"] = True
        logger.info("Dry run: skipping git push and PR creation")
        return report

    # Phase 4: Ensure remote
    _ensure_remote()

    # Phase 5: Create branch, commit, push
    branch_name = f"auto-improve/{session_id}"
    logger.info(f"Phase 5: Creating branch {branch_name}...")

    _run_git(["config", "user.name", GIT_USER_NAME])
    _run_git(["config", "user.email", GIT_USER_EMAIL])
    _run_git(["checkout", "-b", branch_name])
    _run_git(["add", "-A"])

    commit_msg = (
        f"feat(auto-improve): {session_id}\n\n"
        f"Automated by AutoImproverDaemon recursive self-improvement cycle.\n\n"
        f"Changes:\n"
        + "\n".join(f"  - {f}" for f in changed_files[:20])
        + f"\n\nSession results: {json.dumps(cycle_results.get('observations', {}), default=str)[:500]}"
    )
    commit_res = _run_git(["commit", "-m", commit_msg])
    report["phases"]["commit"] = {
        "returncode": commit_res.returncode,
        "message": commit_res.stdout[:300],
    }

    if commit_res.returncode != 0:
        logger.error(f"Commit failed: {commit_res.stderr}")
        _run_git(["checkout", BASE_BRANCH])
        _run_git(["branch", "-D", branch_name])
        return report

    # Phase 6: Push
    push_res = _run_git(["push", "origin", branch_name])
    report["phases"]["push"] = {
        "returncode": push_res.returncode,
        "stderr": push_res.stderr[:500],
    }

    if push_res.returncode != 0:
        logger.error(f"Push failed: {push_res.stderr}")
        _run_git(["checkout", BASE_BRANCH])
        return report

    # Phase 7: Create PR via GitHub API (using GITHUB_TOKEN env var)
    github_token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if github_token:
        try:
            import httpx

            pr_body = (
                f"## 🔄 Automated Self-Improvement PR\n\n"
                f"Generated by `AutoImproverDaemon.run_cycle()`\n\n"
                f"### Session: `{session_id}`\n\n"
                f"### Changes ({len(changed_files)} files):\n"
                + "\n".join(f"- `{f}`" for f in changed_files[:20])
                + f"\n\n### Observations:\n```json\n{json.dumps(cycle_results.get('observations', {}), indent=2, default=str)[:1000]}\n```"
            )

            resp = httpx.post(
                f"https://api.github.com/repos/{GITHUB_REPO}/pulls",
                headers={
                    "Authorization": f"token {github_token}",
                    "Accept": "application/vnd.github.v3+json",
                },
                json={
                    "title": f"🔄 Auto-Improve: {session_id}",
                    "body": pr_body,
                    "head": branch_name,
                    "base": BASE_BRANCH,
                },
                timeout=15.0,
            )
            if resp.status_code in (200, 201):
                pr_data = resp.json()
                report["pr_url"] = pr_data.get("html_url")
                report["pr_number"] = pr_data.get("number")
                logger.info(f"PR created: {report['pr_url']}")
            else:
                report["phases"]["pr_api"] = {
                    "status": resp.status_code,
                    "body": resp.text[:500],
                }
        except Exception as e:
            report["phases"]["pr_api"] = {"error": str(e)}
    else:
        report["phases"]["pr_api"] = "no_github_token"
        logger.warning("No GITHUB_TOKEN set. PR not created via API.")

    # Checkout back to base branch
    _run_git(["checkout", BASE_BRANCH])

    report["success"] = True
    return report


def run_local_auto_improve(force: bool = False, dry_run: bool = False) -> Dict[str, Any]:
    """
    Complete local auto-improvement pipeline:
    AutoImproverDaemon.run_cycle() → ruff fix → test → git PR.
    """
    from vazus_core.workers.auto_improver_daemon import AutoImproverDaemon

    daemon = AutoImproverDaemon()

    if not force and not daemon.should_run():
        status = daemon.get_status()
        return {
            "action": "skipped",
            "reason": f"Last run {status['hours_since_last']}h ago (interval: {status['interval_hours']}h)",
            "status": status,
        }

    # Run the improvement cycle
    cycle_results = daemon.run_cycle(force=force)
    session_id = cycle_results["session_id"]

    # Create PR with the results
    pr_report = create_auto_pr(session_id, cycle_results, dry_run=dry_run)

    return {
        "action": "completed",
        "cycle": cycle_results,
        "pr": pr_report,
    }


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    logging.basicConfig(level=logging.INFO, format="%(name)s | %(message)s")

    force = "--force" in sys.argv
    dry_run = "--dry-run" in sys.argv

    result = run_local_auto_improve(force=force, dry_run=dry_run)
    print(json.dumps(result, indent=2, default=str))
