r"""
export_and_download_media.py — Telegram Media Exporter & Downloader
Extracts media manifests and downloads video/media files from:
  1) Курс «Покоритель Наташек 7.0» (ID: -1004298762580)
  2) BIOMACHINE SPACE (@bmchnbot, ID: 6414975843)

Saves metadata files to:
  - /home/tarhes/Проекты/vazus/knowledge/telegram_courses/pokoritel_natashek_7_0_manifest.json
  - /home/tarhes/Проекты/vazus/knowledge/telegram_courses/pokoritel_natashek_7_0_manifest.md
  - /home/tarhes/Проекты/vazus/knowledge/telegram_courses/biomachine_space_manifest.json
  - /home/tarhes/Проекты/vazus/knowledge/telegram_courses/biomachine_space_manifest.md
  - /home/tarhes/Проекты/vazus/knowledge/telegram_courses/telegram_media_export_summary.md

Downloads media files to:
  - /home/tarhes/Проекты/vazus/knowledge/telegram_courses/Курс «Покоритель Наташек 7.0»\
  - /home/tarhes/Проекты/vazus/knowledge/telegram_courses/BIOMACHINE SPACE\
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.tl.types import DocumentAttributeVideo, DocumentAttributeFilename

sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
sys.stderr.reconfigure(encoding='utf-8', line_buffering=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("media_exporter")

API_ID = 20546097
API_HASH = "60bf36fbdae62d5370f529a539b97542"
SESSION_PATH = r"/home/tarhes/Проекты/vazus/data/sessions/user_telegram_session"
BASE_DIR = Path(os.environ.get("VAZUS_COURSES_DIR", r"C:\Users\Vaz\Videos\Courses"))

TARGETS = [
    {
        "id": -1004298762580,
        "name": "Курс «Покоритель Наташек 7.0»",
        "folder_name": "Курс «Покоритель Наташек 7.0»",
        "slug": "pokoritel_natashek_7_0"
    },
    {
        "id": 6414975843,
        "name": "BIOMACHINE SPACE (@bmchnbot)",
        "folder_name": "BIOMACHINE SPACE",
        "slug": "biomachine_space"
    }
]


def sanitize_filename(name: str) -> str:
    cleaned = re.sub(r'[\\/*?:"<>|]', "_", name).strip()
    return cleaned or "unnamed"


async def export_channel_manifest(client: TelegramClient, target: dict) -> dict:
    entity = await client.get_entity(target["id"])
    target_dir = BASE_DIR / target["folder_name"]
    target_dir.mkdir(parents=True, exist_ok=True)
    
    messages_data = []
    videos_data = []
    all_media_data = []
    
    total_msgs = 0
    total_bytes = 0
    total_video_bytes = 0
    
    print(f"\n[*] Сбор манифеста для '{target['name']}' (ID: {target['id']})...")
    
    async for msg in client.iter_messages(entity):
        total_msgs += 1
        msg_id = msg.id
        date_str = msg.date.isoformat() if msg.date else ""
        text = msg.text or ""
        
        media_type = None
        file_name = None
        file_size = 0
        duration = None
        width = None
        height = None
        mime_type = None
        
        if msg.video:
            media_type = "video"
            file_size = msg.file.size if msg.file else 0
            mime_type = msg.file.mime_type if msg.file else "video/mp4"
            
            # Extract video attributes
            if msg.document and msg.document.attributes:
                for attr in msg.document.attributes:
                    if isinstance(attr, DocumentAttributeVideo):
                        duration = attr.duration
                        width = attr.w
                        height = attr.h
                    elif isinstance(attr, DocumentAttributeFilename):
                        file_name = attr.file_name
                        
            if not file_name and msg.file and msg.file.name:
                file_name = msg.file.name
            if not file_name:
                file_name = f"msg_{msg_id}_video.mp4"
                
        elif msg.photo:
            media_type = "photo"
            file_size = msg.file.size if msg.file else 0
            file_name = f"msg_{msg_id}_photo.jpg"
            mime_type = "image/jpeg"
            
        elif msg.document:
            mime_type = getattr(msg.document, "mime_type", "") or ""
            file_size = msg.file.size if msg.file else 0
            
            if msg.document.attributes:
                for attr in msg.document.attributes:
                    if isinstance(attr, DocumentAttributeFilename):
                        file_name = attr.file_name
                    elif isinstance(attr, DocumentAttributeVideo):
                        duration = attr.duration
                        width = attr.w
                        height = attr.h
                        
            if not file_name and msg.file and msg.file.name:
                file_name = msg.file.name
            if not file_name:
                file_name = f"msg_{msg_id}_doc"
                
            if "video" in mime_type:
                media_type = "video"
            elif "audio" in mime_type or "ogg" in mime_type:
                media_type = "audio"
            elif "image" in mime_type:
                media_type = "photo"
            else:
                media_type = "document"
                
        elif msg.voice:
            media_type = "voice"
            file_size = msg.file.size if msg.file else 0
            file_name = f"msg_{msg_id}_voice.ogg"
            mime_type = "audio/ogg"
            
        if file_name:
            clean_name = sanitize_filename(file_name)
            if not clean_name.startswith(f"msg_{msg_id}"):
                file_name = f"msg_{msg_id}_{clean_name}"
            else:
                file_name = clean_name
            
        msg_item = {
            "id": msg_id,
            "date": date_str,
            "sender_id": msg.sender_id,
            "text": text,
            "has_media": bool(msg.media),
            "media_type": media_type,
            "file_name": file_name,
            "file_size_bytes": file_size,
            "file_size_mb": round(file_size / (1024 * 1024), 2) if file_size else 0.0,
            "duration_seconds": duration,
            "resolution": f"{width}x{height}" if width and height else None,
            "mime_type": mime_type
        }
        
        messages_data.append(msg_item)
        
        if msg.media:
            all_media_data.append(msg_item)
            total_bytes += file_size
            if media_type == "video":
                videos_data.append(msg_item)
                total_video_bytes += file_size
                
    # Sort chronologically (oldest to newest)
    messages_data.reverse()
    videos_data.reverse()
    all_media_data.reverse()
    
    summary = {
        "channel_name": target["name"],
        "channel_id": target["id"],
        "export_date": datetime.now().isoformat(),
        "total_messages": total_msgs,
        "total_media_count": len(all_media_data),
        "total_media_mb": round(total_bytes / (1024 * 1024), 2),
        "video_count": len(videos_data),
        "video_total_mb": round(total_video_bytes / (1024 * 1024), 2),
        "videos": videos_data,
        "all_media": all_media_data,
        "all_messages": messages_data
    }
    
    # Save JSON manifest
    json_path = BASE_DIR / f"{target['slug']}_manifest.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"[✓] JSON манифест сохранён: {json_path}")
    
    # Save Markdown manifest
    md_path = BASE_DIR / f"{target['slug']}_manifest.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# 📺 Манифест медиа: {target['name']}\n\n")
        f.write(f"- **ID канала/бота**: `{target['id']}`\n")
        f.write(f"- **Всего сообщений**: {total_msgs}\n")
        f.write(f"- **Всего медиафайлов**: {len(all_media_data)} ({summary['total_media_mb']} MB)\n")
        f.write(f"- **Видео уроков/эфиров**: {len(videos_data)} ({summary['video_total_mb']} MB)\n")
        f.write(f"- **Папка выгрузки**: `{target_dir}`\n\n")
        f.write("## 🎥 Список видеоматериалов\n\n")
        f.write("| # | ID Сообщения | Название файла | Размер | Длительность | Разрешение | Тема / Описание |\n")
        f.write("|---|-------------|----------------|--------|--------------|------------|----------------|\n")
        
        for idx, vid in enumerate(videos_data, 1):
            dur_str = f"{vid['duration_seconds']}s" if vid['duration_seconds'] else "—"
            if vid['duration_seconds']:
                total_s = int(round(vid['duration_seconds']))
                mins = total_s // 60
                secs = total_s % 60
                dur_str = f"{mins}м {secs:02d}с"
            res_str = vid['resolution'] or "—"
            desc = vid['text'].replace('\n', ' ').strip()
            if len(desc) > 80:
                desc = desc[:77] + "..."
            desc = desc.replace("|", "/")
            f.write(f"| {idx} | `{vid['id']}` | **{vid['file_name']}** | {vid['file_size_mb']} MB | {dur_str} | {res_str} | {desc} |\n")
            
        f.write("\n## 🖼️ Другие медиафайлы (фото, документы, аудио)\n\n")
        f.write("| # | ID | Тип | Имя файла | Размер | Описание |\n")
        f.write("|---|----|-----|-----------|--------|----------|\n")
        other_media = [m for m in all_media_data if m['media_type'] != 'video']
        for idx, m in enumerate(other_media, 1):
            desc = m['text'].replace('\n', ' ').strip()
            if len(desc) > 60:
                desc = desc[:57] + "..."
            desc = desc.replace("|", "/")
            f.write(f"| {idx} | `{m['id']}` | {m['media_type']} | {m['file_name']} | {m['file_size_mb']} MB | {desc} |\n")
            
    print(f"[✓] Markdown манифест сохранён: {md_path}")
    return summary


async def download_videos_for_target(client: TelegramClient, target: dict, manifest: dict):
    target_dir = BASE_DIR / target["folder_name"]
    target_dir.mkdir(parents=True, exist_ok=True)
    videos = manifest["videos"]
    entity = await client.get_entity(target["id"])
    
    print(f"\n=======================================================")
    print(f"📥 СКАЧИВАНИЕ ВИДЕО: {target['name']}")
    print(f"Всего видео: {len(videos)} ({manifest['video_total_mb']} MB)")
    print(f"Целевая папка: {target_dir}")
    print(f"=======================================================")
    
    downloaded_count = 0
    downloaded_bytes = 0
    skipped_count = 0
    
    for idx, vid in enumerate(videos, 1):
        fname = vid["file_name"]
        expected_size = vid["file_size_bytes"]
        target_file = target_dir / fname
        part_file = target_dir / f"{fname}.part"
        
        # Check if already downloaded
        if target_file.exists() and target_file.stat().st_size > 0:
            if abs(target_file.stat().st_size - expected_size) < 1024:
                print(f"[{idx}/{len(videos)}] ⏭️ Уже скачано: {fname} ({vid['file_size_mb']} MB)")
                skipped_count += 1
                downloaded_bytes += target_file.stat().st_size
                continue
                
        print(f"[{idx}/{len(videos)}] ⏳ Скачивание: {fname} ({vid['file_size_mb']} MB)...")
        msg = await client.get_messages(entity, ids=vid["id"])
        if not msg or not msg.media:
            print(f"[-] Сообщение {vid['id']} не содержит медиа.")
            continue
            
        t0 = time.time()
        retries = 3
        while retries > 0:
            try:
                def progress(current, total):
                    pass
                    
                await client.download_media(msg, file=str(part_file), progress_callback=progress)
                if part_file.exists() and part_file.stat().st_size > 0:
                    if target_file.exists():
                        target_file.unlink()
                    part_file.replace(target_file)
                    elapsed = max(0.1, time.time() - t0)
                    speed = (target_file.stat().st_size / (1024 * 1024)) / elapsed
                    print(f"[{idx}/{len(videos)}] ✅ Завершено: {fname} ({vid['file_size_mb']} MB за {elapsed:.1f}s | {speed:.2f} MB/s)")
                    downloaded_count += 1
                    downloaded_bytes += target_file.stat().st_size
                    break
                else:
                    print(f"[-] Файл скачался с нулевым размером.")
                    break
            except FloodWaitError as e:
                print(f"[!] Telegram FloodWait: пауза {e.seconds} сек...")
                await asyncio.sleep(e.seconds + 2)
                retries -= 1
            except Exception as err:
                print(f"[!] Ошибка при скачивании {fname}: {err}")
                await asyncio.sleep(2)
                retries -= 1
                
    print(f"\n[✓] Итог по '{target['name']}': скачано {downloaded_count}, пропущено {skipped_count} из {len(videos)} видео.")


async def main():
    print("=" * 70)
    print("🚀 TELEGRAM MEDIA EXPORTER & DOWNLOADER — VAZUS SUPERGRAPH OS")
    print("=" * 70)
    
    client = TelegramClient(SESSION_PATH, API_ID, API_HASH)
    await client.connect()
    
    if not await client.is_user_authorized():
        print("[X] Ошибка: сессия не авторизована!")
        await client.disconnect()
        return
        
    me = await client.get_me()
    print(f"[*] Пользователь: {me.first_name} {me.last_name or ''} (@{me.username or 'none'})")
    
    manifests = {}
    
    # 1. Генерация манифестов (метаданные всех медиа файлов в файл)
    for target in TARGETS:
        manifest = await export_channel_manifest(client, target)
        manifests[target["slug"]] = manifest
        
    # Сводный манифест
    summary_path = BASE_DIR / "telegram_media_export_summary.md"
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("# 📦 Сводный отчет выгрузки медиафайлов Telegram\n\n")
        f.write(f"- **Дата формирования**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"- **Пользователь**: {me.first_name} (@{me.username})\n\n")
        for target in TARGETS:
            slug = target["slug"]
            m = manifests[slug]
            json_file = str(BASE_DIR / f"{slug}_manifest.json").replace("\\", "/")
            md_file = str(BASE_DIR / f"{slug}_manifest.md").replace("\\", "/")
            f.write(f"### 📂 {target['name']}\n")
            f.write(f"- **ID**: `{target['id']}`\n")
            f.write(f"- **Всего сообщений**: {m['total_messages']}\n")
            f.write(f"- **Медиафайлов**: {m['total_media_count']} ({m['total_media_mb']} MB)\n")
            f.write(f"- **Видео**: {m['video_count']} ({m['video_total_mb']} MB)\n")
            f.write(f"- **Манифест JSON**: [`{slug}_manifest.json`](file:///{json_file})\n")
            f.write(f"- **Манифест MD**: [`{slug}_manifest.md`](file:///{md_file})\n")
            f.write(f"- **Папка файлов**: `{BASE_DIR / target['folder_name']}`\n\n")
            
    print(f"\n[✓] Сводный отчет сохранен: {summary_path}")
    
    # 2. Скачивание видеоматериалов
    for target in TARGETS:
        await download_videos_for_target(client, target, manifests[target["slug"]])
        
    await client.disconnect()
    print("\n" + "=" * 70)
    print("🎉 ВЫГРУЗКА И СКАЧИВАНИЕ УСПЕШНО ЗАВЕРШЕНЫ!")
    print("=" * 70)


if __name__ == '__main__':
    asyncio.run(main())
