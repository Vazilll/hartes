"""
scripts/download_telegram_courses.py — Accelerated Parallel Telegram Course & Media Exporter.

Features:
1. 🚀 Parallel Async Downloads (5x - 10x faster using asyncio worker pools).
2. 🎯 Multi-chat selection (e.g. '1, 3, 5' or '1-4, 7' or '0' for ALL).
3. 💾 Saved API credentials & session.
4. 🎙️ Fix: Unique message ID naming for voice messages and video notes (record.mp4, oga) to prevent false-skipping collisions.
5. 📂 Automatic sorting into C:\\vazus\\knowledge\\telegram_courses\\<Course_Name>.

vazus SuperGraph OS Ecosystem
"""

import os
import sys
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

DOWNLOAD_DIR = Path("C:/vazus/knowledge/telegram_courses")
SESSION_PATH = Path("C:/vazus/user_telegram_courses_session")
MAX_CONCURRENT_DOWNLOADS = 5  # Parallel download workers for max speed



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


def get_unique_filename(message) -> str:
    """Generates unique filename with message.id to prevent collision skips on record.mp4 or oga voice notes."""
    raw_name = message.file.name if message.file and message.file.name else None
    ext = (message.file.ext if message.file and message.file.ext else "") or ".bin"

    # Handle default generic names like record.mp4, voice.oga, media.jpg
    if not raw_name or raw_name.lower() in ("record.mp4", "voice.oga", "file.bin", "audio.ogg") or raw_name.startswith("media_"):
        file_name = f"msg_{message.id}_{raw_name or 'media'}{ext if not raw_name or not raw_name.endswith(ext) else ''}"
    else:
        path_obj = Path(raw_name)
        file_name = f"{path_obj.stem}_msg{message.id}{path_obj.suffix or ext}"

    return file_name


async def download_single_message(client: TelegramClient, message, channel_dir: Path, semaphore: asyncio.Semaphore):
    """Downloads a single media file in parallel worker pool with unique ID naming."""
    if not message.media:
        return False

    file_name = get_unique_filename(message)
    save_path = channel_dir / file_name

    if save_path.exists() and save_path.stat().st_size > 0:
        print(f"  -> ⏩ Пропуск (уже скачан): {file_name}")
        return False

    async with semaphore:
        print(f"  -> 🚀 [Ускоренно] Скачивание: {file_name}...")
        t0 = time.time()
        try:
            await client.download_media(message, file=str(save_path))
            elapsed = time.time() - t0
            size_mb = save_path.stat().st_size / (1024 * 1024) if save_path.exists() else 0
            speed = size_mb / max(0.1, elapsed)
            print(f"  -> ✅ Готово: {file_name} ({size_mb:.1f} MB за {elapsed:.1f}s | {speed:.1f} MB/s)")
            return True
        except Exception as err:
            print(f"  -> ⚠️ Ошибка загрузки {file_name}: {err}")
            return False


async def main():
    print("=" * 75)
    print("⚡ РАЙТСИСТЕМ / УСКОРЕННЫЙ ВЫГРУЗЧИК КУРСОВ ТЕЛЕГРАМ (PARALLEL + VOICE FIX)")
    print("=" * 75)

    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    print(f"📂 Каталог сохранения: {DOWNLOAD_DIR}")
    print(f"⚡ Максимальная скорость: {MAX_CONCURRENT_DOWNLOADS} параллельных потоков загрузки")

    client = TelegramClient(str(SESSION_PATH), SAVED_API_ID, SAVED_API_HASH)

    print("\n[Telegram Client] Подключение и авторизация...")
    await client.start()
    print("✅ Успешный вход в аккаунт!")

    print("\n🔍 Сканирование ваших диалогов и закрытых каналов...")
    dialogs = await client.get_dialogs()
    course_dialogs = [d for d in dialogs if d.is_channel or d.is_group]

    print("\n📋 Найденные каналы и закрытые чаты:")
    print("   [0] 🚀 СКАЧАТЬ ВСЁ (Все закрытые курсы и каналы)")

    for idx, d in enumerate(course_dialogs, 1):
        d_type = "Канал" if d.is_channel else "Группа/Чат"
        print(f"   [{idx}] {d.title} ({d_type})")

    print("\n💡 Можно выбрать несколько чатов через запятую или тире (например: '1, 3, 5' или '1-4, 7'):")
    choice = input("Выберите номера чатов (или 0 для всех): ").strip()

    selected_indices = parse_selection(choice, len(course_dialogs))
    targets = [course_dialogs[i] for i in selected_indices]

    print(f"\n🎯 Выбрано чатов/курсов для скачивания: {len(targets)}")
    for t in targets:
        print(f"   • {t.title}")

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)
    total_downloaded = 0
    t_start = time.time()

    for target in targets:
        title = target.title
        print(f"\n📥 [Параллельная выгрузка] Курс/Чат: '{title}'...")

        folder_name = "".join([c if c.isalnum() or c in (" ", "_", "-") else "_" for c in title]).strip()
        channel_dir = DOWNLOAD_DIR / folder_name
        channel_dir.mkdir(parents=True, exist_ok=True)

        # Collect media messages
        media_messages = []
        async for message in client.iter_messages(target.entity, limit=2000):
            if message.media:
                media_messages.append(message)

        print(f"   Найдено медиа-файлов/видео/голосовых/документов: {len(media_messages)}")

        # Run parallel download tasks
        tasks = [
            download_single_message(client, msg, channel_dir, semaphore)
            for msg in media_messages
        ]

        results = await asyncio.gather(*tasks)
        successes = sum(1 for r in results if r)
        total_downloaded += successes
        print(f"   ✅ Завершено для '{title}': успешно скачано новых файлов: {successes}")

    await client.disconnect()

    t_total = time.time() - t_start
    print("\n" + "=" * 75)
    print("🎉 ВСЯ УСКОРЕННАЯ ВЫГРУЗКА ЗАКРЫТЫХ КУРСОВ И ГОЛОСОВЫХ ЗАВЕРШЕНА!")
    print(f"Скачано новых файлов: {total_downloaded}")
    print(f"Общее время работы: {t_total:.1f} сек")
    print(f"Каталог: {DOWNLOAD_DIR}")
    print("=" * 75)


if __name__ == "__main__":
    asyncio.run(main())
