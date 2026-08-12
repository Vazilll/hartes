"""
scripts/download_telegram_messages.py — Automated Telegram Group Text Message Exporter.

Features:
1. Exports full text message history, Q&A, links, and code snippets from Telegram groups/channels.
2. Saves cleanly formatted Markdown (.md) and JSONL (.jsonl) into C:\\vazus\\knowledge\\telegram_messages.
3. Multi-chat selection ('1, 3, 5' or '0' for ALL groups).
4. Auto-ingestible for vazus SuperGraph OS vector memory & RAG search.

vazus SuperGraph OS Ecosystem
"""

import os
import sys
import json
import time
import asyncio
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

try:
    from telethon import TelegramClient
except ImportError:
    print("[Error] Telethon is not installed. Run: C:\\vazus\\.venv\\Scripts\\python.exe -m pip install telethon")
    sys.exit(1)

# Saved Telegram API Credentials
SAVED_API_ID = 20546097
SAVED_API_HASH = "60bf36fbdae62d5370f529a539b97542"

MESSAGES_DIR = Path("C:/vazus/knowledge/telegram_messages")
SESSION_PATH = Path("C:/vazus/user_telegram_messages_session")



def parse_selection(choice_str: str, max_count: int) -> list[int]:
    """Parses multi-selection syntax like '1, 3, 5-8' or '0'."""
    choice_str = choice_str.strip()
    if choice_str == "0" or not choice_str:
        return list(range(max_count))

    selected_indices = set()
    parts = choice_str.replace(";", ",").split(",")

    for part in parts:
        part = part.strip()
        if "-" in part:
            try:
                start, end = map(int, part.split("-"))
                for idx in range(start, end + 1):
                    if 1 <= idx <= max_count:
                        selected_indices.add(idx - 1)
            except ValueError:
                pass
        else:
            try:
                idx = int(part)
                if 1 <= idx <= max_count:
                    selected_indices.add(idx - 1)
            except ValueError:
                pass

    return sorted(list(selected_indices)) if selected_indices else list(range(max_count))


async def main():
    print("=" * 75)
    print("💬 РАЙТСИСТЕМ / ВЫГРУЗЧИК ТЕКСТОВЫХ СООБЩЕНИЙ И ОБСУЖДЕНИЙ ИЗ ГРУПП (CHAT EXPORTER)")
    print("=" * 75)

    MESSAGES_DIR.mkdir(parents=True, exist_ok=True)
    print(f"📂 Каталог сохранения: {MESSAGES_DIR}")

    client = TelegramClient(str(SESSION_PATH), SAVED_API_ID, SAVED_API_HASH)

    print("\n[Telegram Client] Подключение и авторизация...")
    await client.start()
    print("✅ Успешный вход в аккаунт!")

    print("\n🔍 Сканирование диалогов, групп и чатов...")
    dialogs = await client.get_dialogs()
    group_dialogs = [d for d in dialogs if d.is_group or d.is_channel]

    print("\n📋 Найденные группы и чаты:")
    print("   [0] 🚀 ВЫГРУЗИТЬ СООБЩЕНИЯ ИЗ ВСЕХ ГРУПП И ЧАТОВ")

    for idx, d in enumerate(group_dialogs, 1):
        d_type = "Группа/Чат" if d.is_group else "Канал"
        print(f"   [{idx}] {d.title} ({d_type})")

    print("\n💡 Можно выбрать несколько групп через запятую (например: '1, 3' или '0' для всех):")
    choice = input("Выберите номера групп: ").strip()

    selected_indices = parse_selection(choice, len(group_dialogs))
    targets = [group_dialogs[i] for i in selected_indices]

    print(f"\n🎯 Выбрано групп для выгрузки сообщений: {len(targets)}")

    total_msg_count = 0
    t_start = time.time()

    for target in targets:
        title = target.title
        print(f"\n💬 Выгрузка текстовых сообщений из: '{title}'...")

        safe_title = "".join([c if c.isalnum() or c in (" ", "_", "-") else "_" for c in title]).strip()
        md_file_path = MESSAGES_DIR / f"{safe_title}.md"
        jsonl_file_path = MESSAGES_DIR / f"{safe_title}.jsonl"

        messages_list = []
        md_lines = [
            f"# История сообщений и обсуждений: {title}\n",
            f"**Экспортировано**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n",
            "---\n\n"
        ]

        msg_count = 0
        async for msg in client.iter_messages(target.entity, limit=5000):
            if msg.text and msg.text.strip():
                msg_count += 1
                total_msg_count += 1

                sender_name = "Пользователь"
                if msg.sender:
                    if hasattr(msg.sender, "first_name") and msg.sender.first_name:
                        sender_name = msg.sender.first_name
                        if hasattr(msg.sender, "last_name") and msg.sender.last_name:
                            sender_name += f" {msg.sender.last_name}"
                    elif hasattr(msg.sender, "title") and msg.sender.title:
                        sender_name = msg.sender.title

                date_str = msg.date.strftime("%Y-%m-%d %H:%M:%S") if msg.date else "Н/Д"

                # Markdown format
                md_lines.append(f"### 👤 {sender_name} (`{date_str}`) [ID: {msg.id}]\n")
                if msg.reply_to:
                    md_lines.append(f"> ↩️ *Ответ на сообщение ID #{msg.reply_to.reply_to_msg_id}*\n\n")
                md_lines.append(f"{msg.text.strip()}\n\n")
                md_lines.append("---\n\n")

                # JSONL record
                messages_list.append({
                    "id": msg.id,
                    "date": date_str,
                    "sender": sender_name,
                    "text": msg.text.strip(),
                    "reply_to_msg_id": msg.reply_to.reply_to_msg_id if msg.reply_to else None,
                })

        # Save Markdown file
        md_file_path.write_text("".join(md_lines), encoding="utf-8")

        # Save JSONL file
        with open(jsonl_file_path, "w", encoding="utf-8") as f:
            for item in messages_list:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

        print(f"   ✅ Завершено для '{title}': сохранено {msg_count} текстовых сообщений")
        print(f"   -> Markdown: {md_file_path}")
        print(f"   -> JSONL:    {jsonl_file_path}")

    await client.disconnect()

    t_total = time.time() - t_start
    print("\n" + "=" * 75)
    print("🎉 ВЫГРУЗКА ВСЕХ ТЕКСТОВЫХ СООБЩЕНИЙ ЗАВЕРШЕНА!")
    print(f"Всего выгружено сообщений: {total_msg_count}")
    print(f"Общее время: {t_total:.1f} сек")
    print(f"Каталог сохранения: {MESSAGES_DIR}")
    print("=" * 75)


if __name__ == "__main__":
    asyncio.run(main())
