"""
scripts/telegram_exporter_all.py — Unified All-in-One Telegram Exporter.
Allows downloading:
1. Media & Voice Notes (videos, oga, mp4, files).
2. Text Messages & Q&A Discussions (Markdown & JSONL).
3. Both Media + Text in 1 connection.

vazus SuperGraph OS Ecosystem
"""

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

SAVED_API_ID = 20546097
SAVED_API_HASH = "60bf36fbdae62d5370f529a539b97542"

BASE_KNOWLEDGE_DIR = Path("C:/vazus/knowledge")
SESSION_PATH = Path("C:/vazus/user_telegram_unified_session")
MAX_CONCURRENT_DOWNLOADS = 5


def parse_selection(choice_str: str, max_count: int) -> list[int]:
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


def get_unique_filename(message) -> str:
    raw_name = message.file.name if message.file and message.file.name else None
    ext = (message.file.ext if message.file and message.file.ext else "") or ".bin"
    if not raw_name or raw_name.lower() in ("record.mp4", "voice.oga", "file.bin", "audio.ogg") or raw_name.startswith("media_"):
        file_name = f"msg_{message.id}_{raw_name or 'media'}{ext if not raw_name or not raw_name.endswith(ext) else ''}"
    else:
        path_obj = Path(raw_name)
        file_name = f"{path_obj.stem}_msg{message.id}{path_obj.suffix or ext}"
    return file_name


async def download_media_file(client: TelegramClient, message, channel_dir: Path, semaphore: asyncio.Semaphore):
    if not message.media:
        return False
    file_name = get_unique_filename(message)
    save_path = channel_dir / file_name
    if save_path.exists() and save_path.stat().st_size > 0:
        return False
    async with semaphore:
        try:
            t0 = time.time()
            await client.download_media(message, file=str(save_path))
            elapsed = time.time() - t0
            size_mb = save_path.stat().st_size / (1024 * 1024) if save_path.exists() else 0
            speed = size_mb / max(0.1, elapsed)
            print(f"  -> 📥 Скачано: {file_name} ({size_mb:.1f} MB | {speed:.1f} MB/s)")
            return True
        except Exception as err:
            print(f"  -> ⚠️ Ошибка {file_name}: {err}")
            return False


async def export_chat(client: TelegramClient, target, mode: str, semaphore: asyncio.Semaphore):
    title = target.title
    safe_title = "".join([c if c.isalnum() or c in (" ", "_", "-") else "_" for c in title]).strip()
    print(f"\n🚀 Обработка курса/чата: '{title}'...")

    # Mode 1 or 3: Media & Voice
    if mode in ("1", "3"):
        media_dir = BASE_KNOWLEDGE_DIR / "telegram_courses" / safe_title
        media_dir.mkdir(parents=True, exist_ok=True)
        media_msgs = []
        async for msg in client.iter_messages(target.entity, limit=2000):
            if msg.media:
                media_msgs.append(msg)
        print(f"  [Медиа/Голосовые] Найдено медиа-файлов: {len(media_msgs)}")
        tasks = [download_media_file(client, m, media_dir, semaphore) for m in media_msgs]
        results = await asyncio.gather(*tasks)
        print(f"  ✅ [Медиа] Новых файлов скачано: {sum(1 for r in results if r)}")

    # Mode 2 or 3: Text Messages
    if mode in ("2", "3"):
        text_dir = BASE_KNOWLEDGE_DIR / "telegram_messages"
        text_dir.mkdir(parents=True, exist_ok=True)
        md_file = text_dir / f"{safe_title}.md"
        jsonl_file = text_dir / f"{safe_title}.jsonl"

        md_lines = [f"# Чат/Курс: {title}\n\n"]
        jsonl_items = []
        txt_count = 0

        async for msg in client.iter_messages(target.entity, limit=5000):
            if msg.text and msg.text.strip():
                txt_count += 1
                sender = getattr(msg.sender, "first_name", "Пользователь") or "Пользователь"
                date_str = msg.date.strftime("%Y-%m-%d %H:%M:%S") if msg.date else ""
                md_lines.append(f"### 👤 {sender} (`{date_str}`) [ID: {msg.id}]\n{msg.text.strip()}\n\n---\n\n")
                jsonl_items.append({"id": msg.id, "date": date_str, "sender": sender, "text": msg.text.strip()})

        md_file.write_text("".join(md_lines), encoding="utf-8")
        with open(jsonl_file, "w", encoding="utf-8") as f:
            for item in jsonl_items:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        print(f"  ✅ [Текст] Сохранено {txt_count} текстовых сообщений в Markdown & JSONL")


async def main():
    print("=" * 75)
    print("🌟 РАЙТСИСТЕМ / ЕДИНЫЙ ЦЕНТР ВЫГРУЗКИ ТЕЛЕГРАМ (ALL-IN-ONE EXPORTER)")
    print("=" * 75)

    client = TelegramClient(str(SESSION_PATH), SAVED_API_ID, SAVED_API_HASH)
    print("\n[Telegram Client] Подключение...")
    await client.start()
    print("✅ Успешный вход в аккаунт!")

    dialogs = await client.get_dialogs()
    target_dialogs = [d for d in dialogs if d.is_channel or d.is_group]

    print("\n📋 Выберите режим работы:")
    print("   [1] 🎬 Только Медиа, Видео и Голосовые заметки")
    print("   [2] 💬 Только Текстовые сообщения и Обсуждения")
    print("   [3] 🚀 ВСЁ ВМЕСТЕ (Медиа + Текстовые сообщения)")
    mode = input("Режим (1/2/3, по умолчанию 3): ").strip() or "3"

    print("\n📋 Список ваших каналов и закрытых чатов:")
    print("   [0] 🌟 ВСЕ КАНАЛЫ И ГРУППЫ")
    for idx, d in enumerate(target_dialogs, 1):
        print(f"   [{idx}] {d.title}")

    choice = input("\nВыберите номера чатов (например '1, 3' или '0' для всех): ").strip()
    selected_indices = parse_selection(choice, len(target_dialogs))
    selected_targets = [target_dialogs[i] for i in selected_indices]

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)
    t0 = time.time()

    for target in selected_targets:
        await export_chat(client, target, mode, semaphore)

    await client.disconnect()

    print("\n" + "=" * 75)
    print(f"🎉 ВСЯ ВЫГРУЗКА ЗАВЕРШЕНА за {time.time()-t0:.1f}s!")
    print(f"Файлы расположены в: {BASE_KNOWLEDGE_DIR}")
    print("=" * 75)


if __name__ == "__main__":
    asyncio.run(main())
