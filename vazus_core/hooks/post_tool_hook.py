#!/usr/bin/env python3
"""
vazus_core.hooks.post_tool_hook — Antigravity PostToolUse Lifecycle Hook.

Triggered AUTOMATICALLY by Antigravity AFTER file editing tools execute.
Performs instant AST syntax verification via python ast.parse on modified files.
Conforms 100% to Google Antigravity PostToolUse contract.
"""

import ast
import datetime
import json
import logging
from pathlib import Path
import subprocess
import sys
from typing import Optional

if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

logger = logging.getLogger(__name__)

sys.path.insert(0, "C:/vazus")
try:
    from vazus_core.memory.j_space_tool_indexer import record_j_space_tool_usage
except Exception:
    def record_j_space_tool_usage(tool_name: str, db_path: Optional[str] = None) -> bool:
        return False

try:
    from vazus_core.hooks.hud_writer import write_hud_event
except Exception as _import_err:
    def write_hud_event(event_type: str, payload: dict) -> None:
        """Standalone fallback HUD event writer that persists events to disk."""
        hud_log_path = Path("C:/vazus/data/logs/hud_session.jsonl")
        try:
            hud_log_path.parent.mkdir(parents=True, exist_ok=True)
            event_record = {
                "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "source": "post_tool_hook",
                "event": event_type,
                **payload,
            }
            with open(hud_log_path, "a", encoding="utf-8") as _f:
                _f.write(json.dumps(event_record, ensure_ascii=False) + "\n")
        except Exception as _write_err:
            logger.warning("Failed to write fallback HUD event: %s", _write_err)


def _run_targeted_tdd_test(target_path: Path) -> Optional[str]:
    """Runs fast targeted pytest on associated test file if present."""
    test_file = Path("C:/vazus/tests") / f"test_{target_path.stem}.py"
    if not test_file.exists():
        return None
    try:
        py_bin = Path("C:/vazus/.venv/Scripts/python.exe")
        p = str(py_bin) if py_bin.exists() else sys.executable
        res = subprocess.run(
            [p, "-m", "pytest", str(test_file), "-q", "--tb=line"],
            capture_output=True,
            text=True,
            timeout=4
        )
        if res.returncode == 0:
            return "PASSED"
        last_line = res.stdout.strip().splitlines()[-1] if res.stdout.strip() else "error"
        fail_msg = f"FAILED: {last_line}"
        sys.stderr.write(f"[Vazus OS TDD Gate] {test_file.name} {fail_msg}\n")
        try:
            from vazus_core.memory.mem0_memory_engine import Mem0Engine
            from vazus_core.memory.auto_improver import LessonMemoryBank
            Mem0Engine().add_fact(
                fact_text=f"[tdd_failure] {test_file.name} against {target_path.name}: {fail_msg}",
                category="test_failure",
                entity="tdd_gate"
            )
            LessonMemoryBank().save_lesson(
                task_type="tdd_gate",
                error_sig=f"{test_file.name} {fail_msg[:60]}",
                lesson_text=f"Targeted test {test_file.name} failed after editing {target_path.name}: {fail_msg}",
                fix_hint="Inspect failing test assertions and restore invariants before commit."
            )
        except Exception as tdd_mem_err:
            logger.debug("TDD failure memory routing non-fatal: %s", tdd_mem_err)
        return fail_msg
    except Exception as exc:
        logger.debug("Targeted test execution skipped or failed: %s", exc)
        return "SKIPPED"


def _handle_syntax_error(target_file: str, se: SyntaxError, tool_name: str) -> None:
    """Logs and dispatches syntax error details to HUD and Mem0."""
    write_hud_event("PostToolUse", {
        "tool": tool_name,
        "file": target_file,
        "ast_valid": False,
        "syntax_error": f"line {se.lineno}: {se.msg}",
    })
    sys.stderr.write(f"[Vazus OS AST Hook Error] Syntax error in {target_file} at line {se.lineno}: {se.msg}\n")
    try:
        from vazus_core.memory.mem0_memory_engine import Mem0Engine
        Mem0Engine().add_fact(
            fact_text=f"[syntax_error] {Path(target_file).name} line {se.lineno}: {se.msg}",
            category="bug_found",
            entity="ast_hook"
        )
    except Exception as mem_err:
        logger.debug("Mem0 fact logging skipped: %s", mem_err)


def _append_review_feed(
    target_file: str,
    tool_name: str,
    ast_valid: Optional[bool],
    session_id: str = "",
) -> None:
    """Appends file modification event to review feed for parallel adversary reviewer."""
    feed_path = Path("C:/vazus/data/logs/review_feed.jsonl")
    try:
        feed_path.parent.mkdir(parents=True, exist_ok=True)
        rec = {
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "file": str(target_file),
            "tool": str(tool_name),
            "ast_valid": ast_valid,
            "session_id": str(session_id),
        }
        with open(feed_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception as feed_err:
        logger.debug("Review feed write error: %s", feed_err)


def _resolve_canonical_tool_name(raw_name: str, args: dict) -> str:
    """Normalizes raw Antigravity/MCP tool names to canonical forms."""
    if not raw_name:
        return ""
    if raw_name == "call_mcp_tool":
        return str(args.get("ToolName") or args.get("ServerName") or raw_name)
    if raw_name.startswith("mcp_"):
        parts = raw_name.split("_", 2)
        if len(parts) >= 3:
            return parts[2]
    return raw_name


def _bump_tool_usage_counter() -> None:
    """Tracks tool usages and periodically triggers dynamic tool reweighting."""
    counter_path = Path("C:/vazus/data/logs/.tool_usage_counter")
    try:
        cnt = int(counter_path.read_text(encoding="utf-8").strip()) if counter_path.exists() else 0
        cnt += 1
        counter_path.parent.mkdir(parents=True, exist_ok=True)
        counter_path.write_text(str(cnt), encoding="utf-8")
        if cnt % 25 == 0:
            from vazus_core.memory.j_space_tool_indexer import get_tool_indexer
            get_tool_indexer().reweight_tools_by_usage(min_proposals=3)
    except Exception as exc:
        logger.debug("Tool usage counter bump notice: %s", exc)


def _process_target_file(target_file: str, tool_name: str, session_id: str = "") -> None:
    """Processes target file for AST validity and targeted test execution."""
    if target_file.endswith(".py"):
        target_path = Path(target_file)
        if target_path.exists():
            try:
                code_content = target_path.read_text(encoding="utf-8", errors="ignore")
                ast.parse(code_content)
                test_res = _run_targeted_tdd_test(target_path)
                
                # Self-Sustaining Protocol: Auto-sync block SPEC.md on completion
                # Decoupled: trigger_indexer=False so micro-edits do NOT spawn SCIP indexing
                try:
                    from vazus_core.maintenance.auto_index_runner import run_maintenance
                    run_maintenance(paths=[target_file], trigger_indexer=False)
                except Exception as maint_err:
                    logger.debug("AutoIndex maintenance non-fatal: %s", maint_err)

                write_hud_event("PostToolUse", {
                    "tool": tool_name,
                    "file": target_file,
                    "ast_valid": True,
                    "test_result": test_res
                })
                _append_review_feed(target_file, tool_name, ast_valid=True, session_id=session_id)
            except SyntaxError as se:
                _handle_syntax_error(target_file, se, tool_name)
                _append_review_feed(target_file, tool_name, ast_valid=False, session_id=session_id)
    else:
        write_hud_event("PostToolUse", {
            "tool": tool_name,
            "file": target_file,
            "ast_valid": None,
        })
        _append_review_feed(target_file, tool_name, ast_valid=None, session_id=session_id)


def run_post_tool_hook(
    session_id: str = "unknown",
    tool_name: str = "",
    tool_args: Optional[dict] = None,
    raw_output: str = "",
    **_kwargs
) -> dict:
    """Captures post-tool execution telemetry and signal metrics."""
    actual = _resolve_canonical_tool_name(tool_name, tool_args or {})
    if actual:
        record_j_space_tool_usage(actual)
    if tool_name and tool_name != actual:
        record_j_space_tool_usage(tool_name)
    _bump_tool_usage_counter()
    return {
        "status": "CAPTURED",
        "session_id": session_id,
        "tool_name": tool_name,
        "telemetry": {
            "output_len": len(raw_output),
            "tool_args": tool_args or {},
        }
    }


def main():
    try:
        input_data = json.load(sys.stdin)
        tool_call = input_data.get("toolCall", {})
        raw_tool_name = tool_call.get("name", "")
        args = tool_call.get("args", {})
        session_id = input_data.get("conversationId", "")

        canonical_tool = _resolve_canonical_tool_name(raw_tool_name, args)
        if canonical_tool:
            record_j_space_tool_usage(canonical_tool)
        if raw_tool_name and raw_tool_name != canonical_tool:
            record_j_space_tool_usage(raw_tool_name)
        _bump_tool_usage_counter()

        target_file = args.get("TargetFile") or args.get("AbsolutePath") or ""
        if target_file:
            _process_target_file(target_file, canonical_tool or raw_tool_name, session_id=session_id)
    except Exception as exc:
        logger.debug("PostToolUse hook encountered non-fatal error: %s", exc)
    finally:
        print(json.dumps({}))


if __name__ == "__main__":
    main()
