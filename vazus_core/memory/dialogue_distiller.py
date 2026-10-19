"""
dialogue_distiller.py — Distills historical Antigravity sessions into dense, actionable knowledge.
Packs long-running conversations into structured markdown cards and indexes confirmed decisions.
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("dialogue_distiller")

BRAIN_DIR = Path(r"C:\Users\Vaz\.gemini\antigravity\brain")
DISTILLED_FILE = Path(r"/home/tarhes/Проекты/vazus/services/memory/DISTILLED_SESSIONS.md")


def extract_session_essence(messages: List[Dict[str, Any]]) -> str:
    """Extracts high-density technical summary from a list of session messages."""
    if not messages:
        return ""

    user_requests = []
    assistant_actions = []
    links = []
    files_touched = []

    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if isinstance(content, list):
            text_blocks = [b.get("text", "") for b in content if isinstance(b, dict)]
            content = " ".join(text_blocks)
        if not isinstance(content, str):
            continue

        clean_text = content.strip()
        if role in ("user", "USER_EXPLICIT"):
            # Strip XML tags
            clean_text = re.sub(r"<[^>]+>", "", clean_text).strip()
            if len(clean_text) > 5 and clean_text not in user_requests:
                user_requests.append(clean_text)
        elif role in ("assistant", "model"):
            # Look for action summaries, decisions, files
            for line in clean_text.splitlines():
                line = line.strip()
                if any(
                    kw in line.lower()
                    for kw in ("развернут", "успешно", "создан", "исправлен", "deploy", "vazus-", "запущен")
                ):
                    if len(line) < 200 and line not in assistant_actions:
                        assistant_actions.append(line)

        # Extract links
        found_links = re.findall(r"https?://[^\s)\]]+", content)
        for lnk in found_links:
            if lnk not in links and not lnk.endswith((".png", ".jpg", ".svg")):
                links.append(lnk)

        # Extract file paths
        found_files = re.findall(r"[C-Z]:\\[a-zA-Z0-9_.\-\\]+", content)
        for f in found_files:
            if f not in files_touched and not f.endswith((".pyc", ".tmp")):
                files_touched.append(f)

    if not user_requests and not assistant_actions:
        return ""

    sections = []
    if user_requests:
        sections.append("**Ключевые запросы пользователя:**")
        for u in user_requests[:5]:
            sections.append(f"- {u[:150]}")

    if assistant_actions:
        sections.append("\n**Выполненные действия & Результаты:**")
        for a in assistant_actions[:5]:
            sections.append(f"- {a}")

    if links:
        sections.append("\n**Ссылки & Ресурсы:**")
        for lnk in links[:5]:
            sections.append(f"- {lnk}")

    if files_touched:
        sections.append("\n**Затронутые файлы:**")
        for f in files_touched[:5]:
            sections.append(f"- `{f}`")

    return "\n".join(sections)


def distill_all_sessions(max_sessions: int = 25, output_file: Optional[Path] = None) -> str:
    """Scans all historical sessions in brain/ and produces a consolidated DISTILLED_SESSIONS.md."""
    if not BRAIN_DIR.exists():
        return "# Реестр сессий пуст\n"

    target_file = output_file or DISTILLED_FILE
    session_dirs = [
        d
        for d in BRAIN_DIR.iterdir()
        if d.is_dir() and d.name not in (".system_generated", "tempmediaStorage", "scratch")
    ]

    # Sort newest first
    session_dirs.sort(key=lambda d: d.stat().st_mtime, reverse=True)

    lines = [
        "# 📚 Vazus OS — Дистиллированный реестр всех диалогов (Memory Digest)",
        "> **Назначение**: Концентрированная выжимка всех 20+ сессий Antigravity.",
        f"> **Сгенерировано**: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "---",
        "",
    ]

    processed_count = 0
    for sdir in session_dirs[:max_sessions]:
        tf = sdir / ".system_generated" / "logs" / "transcript.jsonl"
        if not tf.exists():
            continue

        raw_msgs = []
        try:
            with open(tf, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if '"type":"USER_INPUT"' in line or '"USER_INPUT"' in line:
                        try:
                            obj = json.loads(line)
                            raw_msgs.append({"role": "user", "content": obj.get("content", "")})
                        except:
                            pass
                    elif '"type":"PLANNER_RESPONSE"' in line:
                        try:
                            obj = json.loads(line)
                            raw_msgs.append({"role": "assistant", "content": obj.get("content", "")})
                        except:
                            pass
        except Exception as e:
            logger.debug("Failed reading %s: %s", tf, e)
            continue

        if not raw_msgs:
            continue

        essence = extract_session_essence(raw_msgs)
        if not essence:
            continue

        mtime = datetime.fromtimestamp(tf.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        size_kb = tf.stat().st_size // 1024

        lines.append(f"## 💬 Сессия `{sdir.name[:8]}` ({mtime} | {size_kb} KB)")
        lines.append(essence)
        lines.append("\n---\n")
        processed_count += 1

    content_md = "\n".join(lines)
    try:
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text(content_md, encoding="utf-8")
        logger.info("Distilled %d sessions to %s", processed_count, target_file)
    except Exception as e:
        logger.error("Failed saving distilled sessions: %s", e)

    return content_md


if __name__ == "__main__":
    result = distill_all_sessions()
    print(f"Distilled session summary generated ({len(result)} chars).")
