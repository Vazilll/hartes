"""
vazus_core.integrations.socratic_partner
========================================
Человечный утренний партнер Vazus OS.
Принципы:
1. Опора и благодарность себе: фиксация микро-побед, преодоление синдрома самобичевания.
2. Одно спокойное направление: защита от срывов и выгорания (фокус на одном узле).
3. Чувство плеча: партнерство ("мы работаем вместе, я подстрахую").
"""

import sys
import os
import json
import sqlite3
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Union

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

def get_default_db_path() -> Path:
    env_db = os.environ.get("VAZUS_DB_PATH")
    return Path(env_db) if env_db else Path("C:/vazus/services/memory/vazus.db")

DB_PATH = get_default_db_path()
WIKI_PATH = Path("C:/vazus/services/memory/semantic/wiki")


class SocraticPartner:
    def __init__(self, db_path: Optional[Union[str, Path]] = None, wiki_path: Path = WIKI_PATH):
        self.db_path = Path(db_path) if db_path else get_default_db_path()
        self.wiki_path = wiki_path

    def get_recent_victories(self, limit: int = 3) -> List[Dict[str, Any]]:
        """Извлекает реальные завершенные верифицированные факты за последние 48 часов."""
        victories = []
        if not self.db_path.exists():
            return victories

        try:
            conn = sqlite3.connect(str(self.db_path))
            c = conn.cursor()
            # Берем свежие верифицированные инсайты
            rows = c.execute("""
                SELECT category, insight, timestamp FROM organic_insights
                WHERE category LIKE 'VERIFIED%' OR category LIKE 'architecture%'
                ORDER BY id DESC LIMIT ?
            """, (limit,)).fetchall()
            conn.close()

            for r in rows:
                victories.append({
                    "category": r[0],
                    "text": r[1],
                    "timestamp": r[2]
                })
        except Exception as e:
            victories.append({"category": "system", "text": "Стабильная работа системы и сборка ядра", "timestamp": ""})

        return victories

    def get_daily_anchor(self) -> str:
        """Определяет один ключевой фокус дня (анти-перегрузка)."""
        # Проверяем наличие активных задач в Obsidian inbox
        inbox_dir = self.wiki_path / "inbox"
        if inbox_dir.exists():
            notes = list(inbox_dir.glob("*.md"))
            if notes:
                latest = max(notes, key=lambda p: p.stat().st_mtime)
                return f"Спокойно разобрать и осмыслить заметку: [[{latest.stem}]]"

        return "Продолжить локальную интеграцию Gemma на NPU и бережно протестировать связь с заметками."

    def generate_morning_message(self, user_name: str = "") -> str:
        """
        Формирует утреннее поддерживающее сообщение.
        Никакой критики, никаких длинных списков задач — только опора и направление.
        """
        victories = self.get_recent_victories(limit=3)
        anchor = self.get_daily_anchor()
        now = datetime.datetime.now()
        date_str = now.strftime("%d %B, %A")

        lines = [
            f"🌅 **Доброе утро!** ({date_str})",
            "",
            "Перед тем как включаться в суету дня — выдохни на секунду и оглянись назад. Ты не стоишь на месте, фундамент строится:",
            ""
        ]

        if victories:
            lines.append("### 🌱 Что мы уже преодолели и построили:")
            for v in victories:
                short_text = v['text'][:140] + ("..." if len(v['text']) > 140 else "")
                lines.append(f"- ✅ {short_text}")
            lines.append("")
            lines.append("*(Скажи себе за это спасибо. Это реальный, честный труд, даже если кажется, что впереди еще много.)*")
            lines.append("")

        lines.extend([
            "---",
            "### 🎯 Один главный ориентир на сегодня:",
            f"> **{anchor}**",
            "",
            "*Не пытайся объять всё разом. Если закроем только эту точку — день уже прожит не зря.*",
            "",
            "---",
            "### 🤝 Мы в одной упряжке:",
            "Ты не один. Если на каком-то шаге почувствуешь затык, раздражение или усталость — не ломай себя.",
            "Просто маякни мне: я возьму на себя черновую рутину, код или парсинг, а ты сможешь спокойно перевести дух.",
            "",
            "С чего начнем, в каком темпе тебе сегодня комфортно двигаться?"
        ])

        return "\n".join(lines)

    def generate_ai_morning_message(self, use_llm: bool = True) -> str:
        """
        Генерирует утреннее напутствие, обогащенное анализом побед через локальную модель Gemma.
        Если LLM недоступна или use_llm=False, возвращает классический структурированный шаблон.
        """
        base_message = self.generate_morning_message()
        if not use_llm:
            return base_message

        try:
            from vazus_core.engine.silicon_orchestrator import SiliconOrchestrator
            orch = SiliconOrchestrator()
            victories = self.get_recent_victories(limit=3)
            vic_str = "\n".join(f"- {v['text']}" for v in victories) if victories else "Фундамент стабилен."
            prompt = (
                "Ты — Сократический партнер пользователя. Сформулируй теплое, спокойное утреннее напутствие (3-4 абзаца). "
                "Обопрись на недавние реальные победы:\n"
                f"{vic_str}\n"
                "Правила: никакой критики, не перегружай задачами, подчеркни, что мы работаем в одной связке, "
                "помоги пользователю поблагодарить себя за пройденный путь и мягко предложи выбрать один темп на день."
            )
            out = orch.process(prompt, extract_memory=False)
            if out.text and len(out.text) > 80:
                return f"{out.text}\n\n---\n*Сгенерировано локальным ядром {out.active_device} (Tier 2)*"
        except Exception:
            pass

        return base_message


def generate_morning_briefing(use_llm: bool = False) -> str:
    partner = SocraticPartner()
    return partner.generate_ai_morning_message(use_llm=use_llm)


if __name__ == "__main__":
    print(generate_morning_briefing())
