#!/usr/bin/env python3
"""
vazus_core.hooks.post_invocation_hook — Antigravity PostInvocation Lifecycle Hook.

Called AUTOMATICALLY by Antigravity after every model invocation (every AI response).
Extracts real lessons, decisions and errors from the conversation and persists them
into vazus-organic (vazus_record_insight) every 5th invocation to avoid flooding.

This is NOT a manual script — it is triggered by hooks.json natively.
"""

import sys
import json
import os
import re

from vazus_core.memory.mem0_memory_engine import Mem0Engine


# Tags we extract from conversation content
LESSON_PATTERNS = [
    (r"\b(баг|bug|ошибка|error|traceback|exception|failed|сломан)\b", "bug_found"),
    (r"\b(решение|решили|fix|fixed|исправлен|исправили|resolved)\b", "fix_applied"),
    (r"\b(архитектура|architecture|паттерн|pattern|структура|design)\b", "architecture_insight"),
    (r"\b(правило|rule|запрети|запомни|remember|never|always)\b", "rule_learned"),
    (r"\b(улучшение|улучшить|optimize|optimized|refactor|рефактор)\b", "optimization"),
]


def extract_last_model_response(messages: list) -> str:
    """Extract the last assistant message text from conversation messages."""
    for msg in reversed(messages):
        if msg.get("role") in ("assistant", "model"):
            content = msg.get("content", "")
            if isinstance(content, list):
                parts = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        parts.append(block.get("text", ""))
                return " ".join(parts)
            elif isinstance(content, str):
                return content
    return ""


def extract_last_user_message(messages: list) -> str:
    """Extract the last user message text."""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        return block.get("text", "")[:200]
            elif isinstance(content, str):
                return content[:200]
    return ""


def classify_insight(text: str) -> tuple:
    """Classify text into an insight category. Returns (category, excerpt)."""
    text_lower = text.lower()
    for pattern, category in LESSON_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            match = re.search(pattern, text_lower, re.IGNORECASE)
            start = max(0, match.start() - 60)
            end = min(len(text), match.end() + 120)
            excerpt = text[start:end].strip()
            return category, excerpt
    return None, None


def main():
    try:
        raw_input = sys.stdin.read()
        if not raw_input.strip():
            print(json.dumps({}))
            return

        hook_data = json.loads(raw_input)
        invocation_num = hook_data.get("invocationNum", 0)
        conversation_id = hook_data.get("conversationId", "unknown")
        messages = hook_data.get("messages", [])

        mem0 = Mem0Engine()

        # 1. User Preferences: ONLY persist when explicitly requested via command/marker
        user_msg = extract_last_user_message(messages)
        if user_msg:
            pref_match = re.search(r"^(?:запомни|правило|rule|remember|never|always):\s*(.+)", user_msg.strip(), re.IGNORECASE)
            if pref_match:
                clean_pref = pref_match.group(1).strip()
                mem0.add_fact(
                    fact_text=f"[user_rule] {clean_pref}",
                    category="user_preference",
                    entity="user"
                )

        # 2. System Lessons: Persist only verified architectural insights periodically (every 10th turn)
        if invocation_num > 0 and invocation_num % 10 == 0:
            model_response = extract_last_model_response(messages)
            if model_response and len(model_response) > 120:
                category, excerpt = classify_insight(model_response)
                if category in ("architecture_insight", "rule_learned") and excerpt:
                    mem0.add_fact(
                        fact_text=f"[{category}] {excerpt[:300]}",
                        category=category,
                        entity="verified_insight"
                    )
                    # Export note to Zettelkasten Wiki
                    try:
                        from vazus_core.memory.zettelkasten_exporter import ZettelkastenExporter
                        exporter = ZettelkastenExporter()
                        exporter.export_insight_note(
                            title=f"{category}_{conversation_id[:8]}",
                            category=category,
                            content_text=excerpt
                        )
                    except Exception:
                        pass

        print(json.dumps({}))

    except Exception:
        print(json.dumps({}))


if __name__ == "__main__":
    main()

