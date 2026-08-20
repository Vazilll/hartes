#!/usr/bin/env python3
"""
vazus_core.hooks.stop_hook — Antigravity Stop Lifecycle Hook.

Called AUTOMATICALLY by Antigravity when the agent execution loop terminates.
Generates a semantic session summary from conversation history and persists it
into vazus-organic as a structured insight + mem0 fact.

This is NOT a manual script — it is triggered by hooks.json natively.
"""

import sys
import json
import subprocess
from datetime import datetime

from vazus_core.memory.mem0_memory_engine import Mem0Engine


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
    except Exception:
        pass

    # Check for active verifier/pytest subprocesses (best-effort)
    try:
        import psutil
        for proc in psutil.process_iter(["name", "cmdline"]):
            try:
                cmdline = " ".join(proc.info.get("cmdline") or []).lower()
                if any(kw in cmdline for kw in ["pytest", "precommit_gate", "smt_z3", "concordia_jury"]):
                    return True, f"Active verification process: {proc.info['name']} (pid {proc.pid})"
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except ImportError:
        pass

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
    except Exception:
        pass
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
    except Exception:
        pass
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
    except Exception:
        pass


def auto_curate_session_memory(
    transcript: list,
    min_confidence: float = 0.7,
    max_facts: int = 5,
) -> list:
    """
    Anthropic Memory Loop — Curation Phase.

    Analyzes session transcript and extracts high-value facts:
    - Architectural decisions (agent changed/created/disabled something)
    - User preferences explicitly acted upon
    - Errors resolved this session

    Writes extracted facts to Mem0 with min_confidence score.
    Returns list of stored fact strings for logging.

    Called automatically from stop_hook main() on session end.
    """
    if not transcript or len(transcript) < 2:
        return []

    DECISION_KEYWORDS = [
        # Russian
        "изменил", "добавил", "удалил", "заменил", "отключил",
        "внедрил", "рефакторил", "создал", "исправил", "переработал",
        # English
        "modified", "created", "disabled", "replaced", "refactored",
        "added", "removed", "fixed", "implemented", "deleted",
    ]

    stored = []
    try:
        mem0 = Mem0Engine()

        for i, msg in enumerate(transcript):
            if msg.get("role") not in ("assistant", "model"):
                continue
            content = str(msg.get("content", ""))
            if not any(kw in content.lower() for kw in DECISION_KEYWORDS):
                continue
            # Get the preceding user message as context
            user_msg = ""
            if i > 0:
                prev = transcript[i - 1]
                raw = prev.get("content", "")
                if isinstance(raw, list):
                    user_msg = " ".join(
                        b.get("text", "") for b in raw if isinstance(b, dict)
                    )
                elif isinstance(raw, str):
                    user_msg = raw
            if not user_msg:
                continue

            fact = (
                f"[Session decision] "
                f"User: {user_msg[:120].strip()} "
                f"→ Agent: {content[:200].strip()}"
            )
            try:
                mem0.add_fact(fact, confidence=min_confidence)
                stored.append(fact)
                if len(stored) >= max_facts:
                    break
            except Exception:
                pass

    except Exception:
        pass

    return stored


def main():
    try:
        raw_input = sys.stdin.read()
        if not raw_input.strip():
            print(json.dumps({"decision": "stop"}))
            return

        hook_data = json.loads(raw_input)
        conversation_id = hook_data.get("conversationId", "unknown")
        _termination_reason = hook_data.get("terminationReason", "unknown")
        _fully_idle = hook_data.get("fullyIdle", True)
        messages = hook_data.get("messages", [])

        # ── Verification Gate: block termination if verification is pending ──
        is_pending, pending_reason = check_pending_verification()
        if is_pending:
            block_count = _increment_block_count(conversation_id)
            if block_count <= 2:
                print(json.dumps({
                    "decision": "continue",
                    "reason": f"[Verification Gate (Attempt {block_count}/2)] {pending_reason}. "
                              "Agent waiting for background verification..."
                }))
                return
            else:
                _clear_block_count(conversation_id)

        # ── AFC Gate: block exit if agent made an unverified success claim ────
        try:
            from vazus_core.verification.anti_false_confidence import has_open_violation
            if has_open_violation(conversation_id):
                afc_block = _get_block_count(f"afc_{conversation_id}")
                if afc_block < 2:
                    _increment_block_count(f"afc_{conversation_id}")
                    print(json.dumps({
                        "decision": "continue",
                        "reason": (
                            "[AFC Gate] Agent made an unverified success claim this session "
                            "(Coverage Theater detected). Run EvidenceJury or empirical test "
                            "before declaring completion. Use: "
                            "from vazus_core.verification.anti_false_confidence import resolve_afc_violation"
                        )
                    }))
                    return
                else:
                    _clear_block_count(f"afc_{conversation_id}")
        except Exception:
            pass  # AFC check is non-blocking on error

        _clear_block_count(conversation_id)
        invocation_num = hook_data.get("invocationNum", 0)

        mem0 = Mem0Engine()

        # 1. Extract conversation content
        user_msgs = extract_all_user_messages(messages)
        model_msgs = extract_all_model_responses(messages)

        # 2. Build semantic session summary
        summary = build_session_summary(
            conversation_id=conversation_id,
            user_msgs=user_msgs,
            model_msgs=model_msgs,
            turn_count=invocation_num
        )

        # 3. Persist summary in mem0
        mem0.add_fact(
            fact_text=f"[SESSION_END] {summary}",
            category="session_summary",
            entity="system"
        )

        # 4. Record as organic insight (best-effort, non-blocking)
        try:
            insight_payload = json.dumps({
                "category": "session_summary",
                "insight": summary
            })
            subprocess.Popen(
                [
                    r"C:\vazus\.venv\Scripts\python.exe",
                    r"C:\vazus\vazus_core\mcp_client.py",
                    "vazus-organic",
                    "vazus_record_insight",
                    insight_payload
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception:
            pass

        # 5. Autonomous Skill Authoring Check
        # If the session was non-trivial (4+ turns) and user task involved architecture/debugging/skills
        if invocation_num >= 4 and user_msgs:
            try:
                all_user_text = " ".join(user_msgs).lower()
                # Check if session addressed key workflow topics
                if any(kw in all_user_text for kw in ["скилл", "skill", "архитектур", "индексац", "система", "настройк", "правил"]):
                    from vazus_core.integrations.skill_author import create_autonomous_skill
                    short_task = user_msgs[0][:60].strip()
                    skill_name = f"auto-lesson-{conversation_id[:6]}"
                    desc = f"Auto-extracted workflow from session {conversation_id[:8]}: {short_task}"
                    instructions = (
                        f"## Auto-Extracted Session Workflow\n\n"
                        f"**Source Task**: {user_msgs[0]}\n\n"
                        f"### Key Steps & Resolution:\n"
                        f"- Executed in conversation `{conversation_id[:8]}` across {invocation_num} turns.\n"
                        f"- Summary: {summary}\n"
                    )
                    create_autonomous_skill(
                        skill_name=skill_name,
                        description=desc,
                        instructions_markdown=instructions,
                        category="Auto-Extracted Session"
                    )
            except Exception:
                pass

        # ── Anthropic Memory Loop — Curation Phase ────────────────────────
        try:
            curated = auto_curate_session_memory(messages)
            if curated:
                import logging as _log
                _log.getLogger("stop_hook").info(
                    "Memory Loop: curated %d facts into Mem0", len(curated)
                )
        except Exception:
            pass

        print(json.dumps({"decision": "stop"}))

    except Exception:
        print(json.dumps({"decision": "stop"}))


if __name__ == "__main__":
    main()


