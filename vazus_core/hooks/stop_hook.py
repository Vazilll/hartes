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

        print(json.dumps({"decision": "stop"}))

    except Exception:
        print(json.dumps({"decision": "stop"}))


if __name__ == "__main__":
    main()


