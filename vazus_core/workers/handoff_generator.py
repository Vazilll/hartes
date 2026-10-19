"""
handoff_generator.py — Automatic Context-Trimming & Handoff Briefing Generator.
Prevents "Lost in the Middle" attention degradation by generating clean handover cards
when conversation turn count exceeds safety thresholds.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("handoff_generator")

HANDOFF_THRESHOLD_TURNS = 20
LATEST_HANDOFF_FILE = Path(r"/home/tarhes/Проекты/vazus/data/logs/latest_handoff.md")


def check_and_generate_handoff(
    turn_index: int, messages: Optional[List[Dict[str, Any]]] = None, threshold: int = HANDOFF_THRESHOLD_TURNS
) -> Dict[str, Any]:
    """Checks if current session exceeds threshold and creates a structured handoff briefing."""
    if turn_index < threshold:
        return {"should_handoff": False, "turn_index": turn_index}

    messages = messages or []
    user_requests = []
    decisions = []

    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if isinstance(content, list):
            content = " ".join(b.get("text", "") for b in content if isinstance(b, dict))
        if not isinstance(content, str):
            continue

        if role in ("user", "USER_EXPLICIT"):
            user_requests.append(content.strip()[:140])
        elif role in ("assistant", "model"):
            for line in content.splitlines():
                line = line.strip()
                if any(
                    w in line.lower() for w in ("создан", "исправлен", "внедрен", "обновлен", "решено", "зафиксирован")
                ):
                    if line not in decisions and len(line) < 180:
                        decisions.append(line)

    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# 🔄 Vazus OS — Handoff Briefing ({timestamp})",
        f"> **Статус**: Внимание! Сессия достигла {turn_index} шагов (порог: {threshold}).",
        "> Для предотвращения деградации внимания рекомендуется открыть новый чистый диалог.",
        "",
        "## 📌 Контекст для новой сессии",
        "### Последние задачи пользователя:",
    ]
    for u in user_requests[-4:]:
        lines.append(f"- {u}")

    if decisions:
        lines.append("\n### Принятые решения и результаты:")
        for d in decisions[-5:]:
            lines.append(f"- {d}")

    lines.append("\n### Академический дедлайн:")
    lines.append("- РТУ МИРЭА 1-й этап: **15.10.2026** (18 долгов, курируются параллельным чатом)")

    briefing_md = "\n".join(lines)

    try:
        LATEST_HANDOFF_FILE.parent.mkdir(parents=True, exist_ok=True)
        LATEST_HANDOFF_FILE.write_text(briefing_md, encoding="utf-8")
    except Exception as e:
        logger.debug("Failed writing latest handoff file: %s", e)

    return {"should_handoff": True, "turn_index": turn_index, "handoff_briefing": briefing_md}
