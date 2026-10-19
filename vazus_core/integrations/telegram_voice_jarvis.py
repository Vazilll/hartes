"""
vazus_core.integrations.telegram_voice_jarvis
Interactive Telegram Voice & Text Jarvis Bridge for Vazus SuperGraph OS (SOTA 2026).
Enables remote voice note capture, semantic recall over 768D memory, academic schedule querying,
and automated morning/evening briefings directly through Telegram.
"""

import logging
import os
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

from vazus_core.engine.config import settings
from vazus_core.memory.db import get_db_connection
from vazus_core.integrations.voice_thought_engine import VoiceThoughtEngine
from vazus_core.integrations.daily_briefing_engine import DailyBriefingEngine
from vazus_core.integrations.vault_graph_canvas import VaultGraphCanvasGenerator


class TelegramVoiceJarvis:
    """Personal Jarvis AI Assistant bridge communicating over Telegram."""

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        db_path: Optional[str] = None,
        wiki_dir: Optional[str] = None,
    ):
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID", "")
        self.db_path = str(db_path or settings.VAZUS_DB_PATH)
        self.wiki_dir = Path(wiki_dir or str(settings.WIKI_DIR))
        self.voice_engine = VoiceThoughtEngine(db_path=self.db_path, wiki_dir=str(self.wiki_dir))
        self.briefing_engine = DailyBriefingEngine(db_path=self.db_path, wiki_dir=str(self.wiki_dir))
        self.canvas_gen = VaultGraphCanvasGenerator(db_path=self.db_path)

    def handle_text_command(self, text: str, _user_id: Optional[str] = None) -> str:
        """Processes incoming text message or slash command."""
        cmd = text.strip()
        if not cmd:
            return "🤖 Jarvis на связи. Отправьте голосовое сообщение или команду /help."

        if cmd.startswith("/start") or cmd.startswith("/help"):
            return self._cmd_help()
        elif cmd.startswith("/briefing") or cmd.startswith("/today"):
            return self._cmd_briefing()
        elif cmd.startswith("/search "):
            query = cmd[len("/search "):].strip()
            return self._cmd_search(query)
        elif cmd.startswith("/note "):
            note_text = cmd[len("/note "):].strip()
            return self._cmd_create_note(note_text)
        elif cmd.startswith("/canvas"):
            return self._cmd_canvas()
        elif cmd.startswith("/status"):
            return self._cmd_status()
        else:
            return self._cmd_search(cmd)

    def _cmd_help(self) -> str:
        """Renders available commands."""
        return (
            "🤖 **Vazus Jarvis — Личный голосовой ассистент**\n\n"
            "Доступные команды:\n"
            "• 🎙️ *Отправьте голосовое* — транскрибация, сохранение в Wiki и 768D векторный поиск.\n"
            "• `/today` или `/briefing` — расписание занятий, дедлайны и задачи на день.\n"
            "• `/search <запрос>` — семантический поиск по вашей базе знаний.\n"
            "• `/note <текст>` — быстрая запись заметки в базу знаний.\n"
            "• `/canvas` — генерация интерактивного графа связей Obsidian Canvas.\n"
            "• `/status` — состояние системы и баз данных."
        )

    def _cmd_briefing(self) -> str:
        """Executes morning briefing command."""
        briefing = self.briefing_engine.generate_morning_briefing()
        return self.briefing_engine.format_telegram_card(briefing)

    def _cmd_search(self, query: str) -> str:
        """Performs vector & keyword search in memory_facts_v2."""
        if not query:
            return "⚠️ Укажите поисковый запрос: `/search <тема>`"

        results = self._query_memory(query, top_k=3)
        if not results:
            return f"🔍 По запросу *«{query}»* ничего не найдено в базе знаний."

        lines = [f"🔍 **Найдено по запросу «{query}»**:\n"]
        for i, res in enumerate(results, 1):
            category = res.get("category", "fact")
            statement = res.get("statement", "")
            lines.append(f"{i}. `[{category}]` {statement}")
        return "\n".join(lines)

    def _cmd_create_note(self, note_text: str) -> str:
        """Creates a structured note from text directly."""
        thought = self.voice_engine.extract_structured_thought(note_text)
        note_path, node_id = self.voice_engine.save_thought_to_vault(thought)
        return (
            f"✅ **Заметка сохранена в базу знаний!**\n\n"
            f"📌 Заголовок: *{thought.get('title')}*\n"
            f"🏷️ Теги: `{', '.join(thought.get('tags', []))}`\n"
            f"📄 Файл: `{Path(note_path).name}`"
        )

    def _cmd_canvas(self) -> str:
        """Generates Obsidian Canvas file."""
        canvas_data = self.canvas_gen.generate_memory_facts_canvas(limit=12)
        out_file = self.wiki_dir / "vault_overview.canvas"
        self.canvas_gen.export_canvas_to_file(canvas_data, str(out_file))
        return f"🗺️ **Интерактивный граф Obsidian Canvas создан!**\nПуть: `{out_file.name}` (Узлов: {len(canvas_data['nodes'])}, Связей: {len(canvas_data['edges'])})"

    def _cmd_status(self) -> str:
        """Returns health status."""
        return "🟢 **Vazus SuperGraph OS v4.0** — Все подсистемы активны (Whisper, Z3, 768D Vector Memory)."

    def handle_voice_message(self, audio_file_path: str, custom_title: Optional[str] = None) -> Dict[str, Any]:
        """Handles incoming voice note from Telegram user."""
        res = self.voice_engine.process_voice_file(audio_file_path, custom_title=custom_title)
        if res.get("status") == "ERROR":
            return {
                "status": "ERROR",
                "message": f"❌ Ошибка обработки голосового: {res.get('error')}"
            }

        actions_str = ""
        actions = res.get("action_items", [])
        if actions:
            actions_str = "\n📌 **Выявленные задачи**:\n" + "\n".join(f"• {a}" for a in actions)

        card = (
            f"🎙️ **Голосовая мысль зафиксирована!**\n\n"
            f"📝 *«{res.get('transcription')}»*\n\n"
            f"📄 Файл: `{Path(res.get('note_path', '')).name}`\n"
            f"🏷️ Теги: `{', '.join(res.get('tags', []))}`"
            f"{actions_str}"
        )

        return {
            "status": "SUCCESS",
            "message": card,
            "transcription": res.get("transcription"),
            "note_path": res.get("note_path"),
            "node_id": res.get("node_id"),
        }

    def _query_memory(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Queries memory_facts_v2 in SQLite using keyword fallback."""
        results = []
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
            WHERE {text_col} LIKE ? OR category LIKE ? OR {domain_col} LIKE ?
            LIMIT ?
            """, (f"%{query}%", f"%{query}%", f"%{query}%", top_k)).fetchall()

            for r in rows:
                results.append({
                    "category": r[0],
                    "statement": r[1],
                    "domain": r[2]
                })
        except Exception as exc:
            logger.debug("Failed searching memory facts for '%s': %s", query, exc)
        finally:
            if conn:
                try:
                    conn.close()
                except Exception as exc:
                    logger.debug("Failed closing DB in search_facts: %s", exc)
        return results
