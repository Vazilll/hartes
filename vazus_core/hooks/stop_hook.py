#!/usr/bin/env python3
"""
vazus_core.hooks.stop_hook — Antigravity Stop Lifecycle Hook.

Called AUTOMATICALLY by Antigravity when the agent execution loop terminates.
Generates a semantic session summary from conversation history and persists it
into vazus-organic as a structured insight + mem0 fact.

This is NOT a manual script — it is triggered by hooks.json natively.
"""

import os
import sys
import json
import subprocess
import logging
from datetime import datetime
from typing import Optional

from vazus_core.memory.mem0_memory_engine import Mem0Engine

logger = logging.getLogger("stop_hook")


def extract_all_user_messages(messages: list) -> list:
    """Extract all user messages from conversation history."""
    results = []
    for msg in messages:
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text = block.get("text", "").strip()
                        if len(text) > 10:
                            results.append(text[:150])
            elif isinstance(content, str) and len(content.strip()) > 10:
                results.append(content.strip()[:150])
    return results


def extract_all_model_responses(messages: list) -> list:
    """Extract all model response texts from conversation history."""
    results = []
    for msg in messages:
        if msg.get("role") in ("assistant", "model"):
            content = msg.get("content", "")
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text = block.get("text", "").strip()
                        if len(text) > 50:
                            results.append(text[:200])
            elif isinstance(content, str) and len(content.strip()) > 50:
                results.append(content.strip()[:200])
    return results


def build_session_summary(conversation_id: str, user_msgs: list, model_msgs: list, turn_count: int) -> str:
    """Build a compact semantic session summary."""
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    short_id = conversation_id[:8]

    # Pick the first and last user messages as context anchors
    first_task = user_msgs[0] if user_msgs else "unknown"
    last_task = user_msgs[-1] if len(user_msgs) > 1 else first_task

    # Detect key themes
    all_text = " ".join(user_msgs + model_msgs).lower()
    themes = []
    if any(k in all_text for k in ["hook", "mcp", "subagent", "skill", "plugin"]):
        themes.append("system-architecture")
    if any(k in all_text for k in ["bug", "error", "fix", "debug", "traceback"]):
        themes.append("debugging")
    if any(k in all_text for k in ["memory", "vector", "embedding", "organic"]):
        themes.append("memory-system")
    if any(k in all_text for k in ["code", "python", "function", "class", "module"]):
        themes.append("code-development")
    if any(k in all_text for k in ["audit", "review", "compare", "check"]):
        themes.append("audit-review")

    themes_str = ", ".join(themes) if themes else "general"

    summary = (
        f"Session {short_id} | {timestamp} | {turn_count} turns | themes: [{themes_str}]\n"
        f"First task: {first_task[:120]}\n"
        f"Last task: {last_task[:120]}"
    )
    return summary


def check_pending_verification() -> tuple[bool, str]:
    """Check if any Z3 verification, Pytest suite, or Concordia Jury vote is pending.

    Returns (is_pending, reason) — if is_pending is True, agent termination
    should be blocked until verification completes.
    """
    import sqlite3
    import os

    db_path = os.path.join(os.path.dirname(__file__), "..", "..", "services", "memory", "vazus.db")
    db_path = os.path.normpath(db_path)

    if not os.path.isfile(db_path):
        return False, ""

    try:
        conn = sqlite3.connect(db_path, timeout=2)
        cur = conn.cursor()

        # Check for pending verification markers (inserted by pre-commit gate)
        cur.execute(
            "SELECT COUNT(*) FROM organic_insights "
            "WHERE category = 'verification_pending' "
            "AND created_at > datetime('now', '-10 minutes')"
        )
        pending_count = cur.fetchone()[0]
        conn.close()

        if pending_count > 0:
            return True, f"Z3/Concordia verification pending ({pending_count} active markers)"
    except Exception as db_err:
        logger.debug("Database verification check error: %s", db_err)

    # Check for active verifier/pytest subprocesses (best-effort)
    try:
        import psutil
        for proc in psutil.process_iter(["name", "cmdline"]):
            try:
                cmdline = " ".join(proc.info.get("cmdline") or []).lower()
                if any(kw in cmdline for kw in ["pytest", "precommit_gate", "smt_z3", "concordia_jury"]):
                    return True, f"Active verification process: {proc.info['name']} (pid {proc.pid})"
            except (psutil.NoSuchProcess, psutil.AccessDenied) as proc_err:
                logger.debug("Process inspection skipped: %s", proc_err)
                continue
    except ImportError as imp_err:
        logger.debug("Optional psutil not available: %s", imp_err)

    return False, ""


def _get_block_count(conversation_id: str) -> int:
    import json
    import os
    state_file = "C:/vazus/.stop_hook_state.json"
    try:
        if os.path.exists(state_file):
            with open(state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get(conversation_id, 0)
    except Exception as state_err:
        logger.debug("State file read failed: %s", state_err)
    return 0


def _increment_block_count(conversation_id: str) -> int:
    import json
    import os
    state_file = "C:/vazus/.stop_hook_state.json"
    cnt = _get_block_count(conversation_id) + 1
    try:
        data = {}
        if os.path.exists(state_file):
            with open(state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        data[conversation_id] = cnt
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception as write_err:
        logger.debug("State file write failed: %s", write_err)
    return cnt


def _clear_block_count(conversation_id: str):
    import json
    import os
    state_file = "C:/vazus/.stop_hook_state.json"
    try:
        if os.path.exists(state_file):
            with open(state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            data.pop(conversation_id, None)
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(data, f)
    except Exception as clear_err:
        logger.debug("State file clear failed: %s", clear_err)


def _extract_decision_fact(msg: dict, prev_msg: Optional[dict], keywords: list) -> Optional[str]:
    """Extracts candidate decision fact from assistant message and preceding user context."""
    content = str(msg.get("content", ""))
    if not any(kw in content.lower() for kw in keywords):
        return None
    user_msg = ""
    if prev_msg:
        raw = prev_msg.get("content", "")
        if isinstance(raw, list):
            user_msg = " ".join(b.get("text", "") for b in raw if isinstance(b, dict))
        elif isinstance(raw, str):
            user_msg = raw
    return f"[Session decision] User: {user_msg[:120].strip()} -> Agent: {content[:200].strip()}"


def auto_curate_session_memory(
    transcript: list,
    min_confidence: float = 0.7,
    max_facts: int = 5,
) -> list:
    """
    Anthropic Memory Loop — Curation Phase.
    Analyzes session transcript, extracts decisions, and writes to Mem0.
    """
    if not transcript or len(transcript) < 2:
        return []

    decision_keywords = [
        "изменил", "добавил", "удалил", "заменил", "отключил",
        "внедрил", "рефакторил", "создал", "исправил", "переработал",
        "modified", "created", "disabled", "replaced", "refactored",
        "added", "removed", "fixed", "implemented", "deleted",
    ]

    stored = []
    try:
        mem0 = Mem0Engine()
        for i, msg in enumerate(transcript):
            if msg.get("role") not in ("assistant", "model"):
                continue
            prev_msg = transcript[i - 1] if i > 0 else None
            fact = _extract_decision_fact(msg, prev_msg, decision_keywords)
            if fact:
                try:
                    mem0.add_fact(fact, confidence=min_confidence)
                    stored.append(fact)
                    if len(stored) >= max_facts:
                        break
                except Exception as e:
                    logger.debug("Failed adding fact to Mem0: %s", e)
    except Exception as e:
        logger.debug("Error during session memory curation: %s", e)

    return stored


def _check_termination_gates(conversation_id: str) -> Optional[dict]:
    """Checks verification pending gate and Anti-False-Confidence (AFC) gate."""
    is_pending, pending_reason = check_pending_verification()
    if is_pending:
        block_count = _increment_block_count(conversation_id)
        if block_count <= 2:
            return {
                "decision": "continue",
                "reason": f"[Verification Gate (Attempt {block_count}/2)] {pending_reason}. Agent waiting for background verification..."
            }
        _clear_block_count(conversation_id)

    try:
        from vazus_core.verification.anti_false_confidence import has_open_violation
        if has_open_violation(conversation_id):
            afc_block = _get_block_count(f"afc_{conversation_id}")
            if afc_block < 2:
                _increment_block_count(f"afc_{conversation_id}")
                return {
                    "decision": "continue",
                    "reason": (
                        "[AFC Gate] Agent made an unverified success claim this session "
                        "(Coverage Theater detected). Run EvidenceJury or empirical test "
                        "before declaring completion. Use: "
                        "from vazus_core.verification.anti_false_confidence import resolve_afc_violation"
                    )
                }
            _clear_block_count(f"afc_{conversation_id}")
    except Exception as e:
        logger.debug("AFC check error: %s", e)

    _clear_block_count(conversation_id)
    return None


def _persist_session_memories(conversation_id: str, invocation_num: int, messages: list) -> None:
    """Extracts summary, adds Mem0/organic insights, and authors skills if applicable."""
    user_msgs = extract_all_user_messages(messages)
    if not user_msgs or invocation_num < 1:
        return

    is_test_lock = os.path.exists(r"C:\vazus\.vazus_test.lock")

    if not is_test_lock:
        mem0 = Mem0Engine()
        model_msgs = extract_all_model_responses(messages)
        summary = build_session_summary(conversation_id=conversation_id, user_msgs=user_msgs, model_msgs=model_msgs, turn_count=invocation_num)

        mem0.add_fact(fact_text=f"[SESSION_END] {summary}", category="session_summary", entity="system")

        try:
            insight_payload = json.dumps({"category": "session_summary", "insight": summary})
            subprocess.Popen(
                [r"C:\vazus\.venv\Scripts\python.exe", r"C:\vazus\vazus_core\mcp_client.py", "vazus-organic", "vazus_record_insight", insight_payload],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except Exception as e:
            logger.debug("Subprocess organic insight error: %s", e)

    if os.getenv("VAZUS_ENABLE_AUTO_SKILLS", "0") == "1" and invocation_num >= 4 and user_msgs:
        try:
            all_user_text = " ".join(user_msgs).lower()
            if any(kw in all_user_text for kw in ["скилл", "skill", "архитектур", "индексац", "система", "настройк", "правил"]):
                from vazus_core.integrations.skill_author import create_autonomous_skill
                short_task = user_msgs[0][:60].strip()
                skill_name = f"auto-lesson-{conversation_id[:6]}"
                desc = f"Auto-extracted workflow from session {conversation_id[:8]}: {short_task}"
                instructions = (
                    f"## Auto-Extracted Session Workflow\n\n**Source Task**: {user_msgs[0]}\n\n"
                    f"### Key Steps & Resolution:\n- Executed in conversation `{conversation_id[:8]}` across {invocation_num} turns.\n- Summary: {summary}\n"
                )
                create_autonomous_skill(skill_name=skill_name, description=desc, instructions_markdown=instructions, category="Auto-Extracted Session")
        except Exception as e:
            logger.debug("Autonomous skill creation error: %s", e)


    try:
        curated = auto_curate_session_memory(messages)
        if curated:
            logger.info("Memory Loop: curated %d facts into Mem0", len(curated))
    except Exception as e:
        logger.debug("Memory Loop curation error: %s", e)

    if invocation_num >= 20:
        try:
            from vazus_core.workers.handoff_generator import check_and_generate_handoff
            check_and_generate_handoff(turn_index=invocation_num)
        except Exception as e:
            logger.debug("Handoff generator in stop_hook failed: %s", e)

    try:
        from vazus_core.engine.unified_hub import VazusUnifiedHub
        VazusUnifiedHub().sync_state_to_cloud_file()
    except Exception as e:
        logger.debug("Cloud sync in stop_hook failed: %s", e)


def main():
    try:
        raw_input = sys.stdin.read()
        if not raw_input.strip():
            print(json.dumps({"decision": "stop"}))
            return

        hook_data = json.loads(raw_input)
        conversation_id = hook_data.get("conversationId", "unknown")
        messages = hook_data.get("messages", [])
        invocation_num = hook_data.get("invocationNum", 0)

        gate_decision = _check_termination_gates(conversation_id)
        if gate_decision is not None:
            print(json.dumps(gate_decision))
            return

        _persist_session_memories(conversation_id, invocation_num, messages)
        print(json.dumps({"decision": "stop"}))

    except Exception as e:
        logger.warning("Unhandled exception in stop_hook: %s", e)
        print(json.dumps({"decision": "stop"}))


async def run_stop_hook(
    session_id: str = "unknown",
    workspace_root: str = "C:/vazus",
    invocation_num: int = 0,
    messages: Optional[list] = None,
    **_kwargs
) -> dict:
    """Async wrapper for stop hook consolidation."""
    if invocation_num >= 20:
        try:
            from vazus_core.workers.handoff_generator import check_and_generate_handoff
            check_and_generate_handoff(turn_index=invocation_num)
        except Exception as e:
            logger.debug("Async handoff generator failed: %s", e)

    try:
        from vazus_core.engine.unified_hub import VazusUnifiedHub
        VazusUnifiedHub().sync_state_to_cloud_file()
    except Exception as e:
        logger.debug("Async cloud sync failed: %s", e)

    return {
        "status": "CONSOLIDATED",
        "session_id": session_id,
        "workspace_root": workspace_root,
        "decision": "stop",
    }


if __name__ == "__main__":
    main()



