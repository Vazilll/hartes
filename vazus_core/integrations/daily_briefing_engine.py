"""
vazus_core.integrations.daily_briefing_engine
Automated Daily Chronos Briefing & Morning/Evening Synthesis Engine for Vazus OS.
Combines RTU MIREA schedule, academic milestones, recorded voice thoughts, and 768D memory facts
into structured daily cards for Telegram and Karpathy Memory Wiki.
"""

import logging
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

from vazus_core.engine.config import settings
from vazus_core.memory.db import get_db_connection
from vazus_core.integrations.mirea_student_manager import MireaStudentManager


def _get_russian_weekday() -> str:
    """Returns current Russian weekday name."""
    days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    return days[time.localtime().tm_wday]


class DailyBriefingEngine:
    """Generates daily morning briefings and evening summaries."""

    def __init__(self, db_path: Optional[str] = None, wiki_dir: Optional[str] = None):
        self.db_path = str(db_path or settings.VAZUS_DB_PATH)
        self.wiki_dir = Path(wiki_dir or str(settings.WIKI_DIR))
        self.wiki_dir.mkdir(parents=True, exist_ok=True)
        self.mirea_mgr = MireaStudentManager(db_path=self.db_path)

    def generate_morning_briefing(self, group_name: str = "ИВБО-22-25") -> Dict[str, Any]:
        """Generates comprehensive morning briefing for the day."""
        weekday = _get_russian_weekday()
        today_date = time.strftime("%Y-%m-%d")

        # Fetch schedule for today
        all_schedule_data = self.mirea_mgr.get_schedule(group_name=group_name)
        today_lessons = []
        for item in all_schedule_data.get("schedule", []):
            if item.get("weekday") == weekday:
                today_lessons.append(item)

        # Fetch pending milestones
        milestones = all_schedule_data.get("milestones", [])
        urgent_milestones = [m for m in milestones if m.get("status") != "COMPLETED"]

        # Fetch recent memory facts
        recent_facts = self._get_recent_facts(limit=3)

        return {
            "type": "morning_briefing",
            "date": today_date,
            "weekday": weekday,
            "group_name": group_name,
            "lessons_count": len(today_lessons),
            "today_lessons": today_lessons,
            "urgent_milestones": urgent_milestones[:4],
            "recent_facts": recent_facts,
        }

    def generate_evening_digest(self) -> Dict[str, Any]:
        """Generates evening retrospective of recorded thoughts and system milestones."""
        today_date = time.strftime("%Y-%m-%d")
        facts = self._get_recent_facts(limit=6)

        return {
            "type": "evening_digest",
            "date": today_date,
            "summary": f"Итоги дня {today_date}: зафиксировано {len(facts)} ключевых фактов и идей в памяти.",
            "recorded_facts": facts,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }

    def _get_recent_facts(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Retrieves recent facts from memory_facts_v2."""
        facts = []
        conn = None
        try:
            conn = get_db_connection(self.db_path)
            cur = conn.cursor()
            cols = [c[1] for c in cur.execute("PRAGMA table_info(memory_facts_v2)").fetchall()]
            text_col = "fact_text" if "fact_text" in cols else "statement"
            domain_col = "provenance" if "provenance" in cols else "source_domain"
            rows = cur.execute(f"""
            SELECT category, {text_col}, {domain_col}
            FROM memory_facts_v2
            ORDER BY created_at DESC
            LIMIT ?
            """, (limit,)).fetchall()
            for r in rows:
                facts.append({
                    "category": r[0],
                    "statement": r[1],
                    "domain": r[2] or "general"
                })
        except Exception as exc:
            logger.debug("Failed fetching recent memory facts: %s", exc)
        finally:
            if conn:
                try:
                    conn.close()
                except Exception as exc:
                    logger.debug("Failed closing DB connection: %s", exc)
        return facts

    def format_telegram_card(self, briefing: Dict[str, Any]) -> str:
        """Formats briefing data as a concise, readable Telegram message."""
        b_type = briefing.get("type", "morning_briefing")
        date_str = briefing.get("date", "")
        weekday = briefing.get("weekday", "")

        if b_type == "morning_briefing":
            lines = [
                f"☀️ **Утренний брифинг Vazus OS** ({weekday}, {date_str})",
                f"🎓 Группа: `{briefing.get('group_name')}`",
                "",
                "📚 **Расписание на сегодня**:"
            ]
            lessons = briefing.get("today_lessons", [])
            if lessons:
                for les in lessons:
                    lines.append(f"• `{les.get('lesson_time')}`: {les.get('subject')} ({les.get('lesson_type')}) — {les.get('teacher')}, ауд. {les.get('classroom')}")
            else:
                lines.append("• Сегодня занятий по расписанию нет (самостоятельная работа / спорт).")

            milestones = briefing.get("urgent_milestones", [])
            if milestones:
                lines.append("")
                lines.append("🎯 **Ближайшие дедлайны и контрольные точки**:")
                for m in milestones:
                    lines.append(f"• `[{m.get('due_date')}]` {m.get('subject')}: {m.get('milestone_name')}")

            return "\n".join(lines)
        else:
            lines = [
                f"🌙 **Вечерний дайджест Vazus OS** ({date_str})",
                briefing.get("summary", ""),
                "",
                "🧠 **Свежие факты в памяти**:"
            ]
            for f in briefing.get("recorded_facts", []):
                lines.append(f"• [{f.get('category')}] {f.get('statement')[:100]}...")
            return "\n".join(lines)

    def save_briefing_to_wiki(self, briefing: Dict[str, Any]) -> str:
        """Persists the daily briefing as a Markdown page in Karpathy Memory Wiki."""
        date_str = briefing.get("date", time.strftime("%Y-%m-%d"))
        b_type = briefing.get("type", "morning_briefing")
        fname = f"daily_briefing_{b_type}_{date_str}.md"
        fpath = self.wiki_dir / fname

        text = self.format_telegram_card(briefing)
        md_content = f"---\ntitle: \"Брифинг {date_str}\"\ndate: {date_str}\ntags: [briefing, daily, chronos]\n---\n\n{text}\n"
        fpath.write_text(md_content, encoding="utf-8")
        return str(fpath)
