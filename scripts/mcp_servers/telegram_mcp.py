#!/usr/bin/env python3
"""
telegram_mcp.py — Native Telegram MCP Server for Vazus SuperGraph OS.
Provides seamless access to Telegram user account via Telethon:
- Search dialogs and public channels
- Inspect chat history and media counts
- Download media files even from restricted channels
- Export full media manifest catalogs to JSON/Markdown

Configuration: ~/.gemini/config/mcp_config.json -> "telegram-mcp"
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any, List

from fastmcp import FastMCP
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.tl.types import (
    Channel, Chat, User, MessageMediaDocument, MessageMediaPhoto
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("telegram_mcp")

mcp = FastMCP("telegram-mcp")

API_ID = 20546097
API_HASH = "60bf36fbdae62d5370f529a539b97542"
SESSION_PATH = os.getenv("TELEGRAM_SESSION_PATH", r"C:\vazus\data\sessions\user_telegram_session")
DEFAULT_DOWNLOAD_DIR = Path(os.environ.get("VAZUS_COURSES_DIR", r"C:\Users\Vaz\Videos\Courses"))

_CLIENT: Optional[TelegramClient] = None
_CLIENT_LOCK = asyncio.Lock()


async def get_client() -> TelegramClient:
    global _CLIENT
    async with _CLIENT_LOCK:
        if _CLIENT is None or not _CLIENT.is_connected():
            _CLIENT = TelegramClient(SESSION_PATH, API_ID, API_HASH)
            await _CLIENT.connect()
            if not await _CLIENT.is_user_authorized():
                raise RuntimeError(f"Telegram session at {SESSION_PATH} is not authorized.")
        return _CLIENT


async def resolve_peer(client: TelegramClient, chat_id: str):
    """Resolves integer ID or username into an entity."""
    clean_id = chat_id.strip()
    try:
        numeric_id = int(clean_id)
        return await client.get_entity(numeric_id)
    except ValueError:
        return await client.get_entity(clean_id)


def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "_", name).strip()


@mcp.tool()
async def tg_search_dialogs(query: str) -> str:
    """Search through the user's own dialogs (including archived) for a specific name."""
    client = await get_client()
    query_lower = query.lower()
    matches = []
    
    dialogs = await client.get_dialogs()
    for d in dialogs:
        title = d.title or d.name or ""
        uname = getattr(d.entity, "username", "") or ""
        if query_lower in title.lower() or query_lower in uname.lower():
            matches.append({
                "id": d.id,
                "title": title,
                "username": f"@{uname}" if uname else None,
                "type": type(d.entity).__name__,
                "unread_count": d.unread_count,
            })
            
    return json.dumps({"query": query, "total_matches": len(matches), "dialogs": matches}, ensure_ascii=False, indent=2)


@mcp.tool()
async def tg_search_channels(query: str, limit: int = 5) -> str:
    """Search for public channels/users by a text query."""
    client = await get_client()
    from telethon.tl.functions.contacts import SearchRequest
    result = await client(SearchRequest(q=query, limit=limit))
    
    channels = []
    for chat in result.chats:
        channels.append({
            "id": chat.id,
            "title": getattr(chat, "title", ""),
            "username": getattr(chat, "username", None),
            "participants_count": getattr(chat, "participants_count", None),
        })
        
    return json.dumps({"query": query, "count": len(channels), "results": channels}, ensure_ascii=False, indent=2)


@mcp.tool()
async def tg_get_history(chat_id: str, limit: int = 10) -> str:
    """Fetch recent messages from a channel, group, or user."""
    client = await get_client()
    entity = await resolve_peer(client, chat_id)
    
    messages = []
    async for msg in client.iter_messages(entity, limit=min(limit, 100)):
        has_media = bool(msg.media)
        media_type = None
        media_size = None
        if msg.video:
            media_type = "video"
            media_size = msg.file.size if msg.file else None
        elif msg.photo:
            media_type = "photo"
            media_size = msg.file.size if msg.file else None
        elif msg.document:
            media_type = f"document/{getattr(msg.document, 'mime_type', 'unknown')}"
            media_size = msg.file.size if msg.file else None
            
        messages.append({
            "id": msg.id,
            "date": msg.date.isoformat() if msg.date else None,
            "sender_id": msg.sender_id,
            "text": msg.text or "",
            "has_media": has_media,
            "media_type": media_type,
            "media_size_bytes": media_size,
        })
        
    return json.dumps({
        "chat_id": chat_id,
        "chat_title": getattr(entity, "title", getattr(entity, "first_name", "")),
        "count": len(messages),
        "messages": messages
    }, ensure_ascii=False, indent=2)


@mcp.tool()
async def tg_count_media(chat_id: str) -> str:
    """Count how many video/audio/voice/photo media files are in a chat."""
    client = await get_client()
    entity = await resolve_peer(client, chat_id)
    
    stats = {
        "total_messages": 0,
        "videos": 0,
        "photos": 0,
        "documents": 0,
        "voice": 0,
        "video_total_bytes": 0,
        "total_media_bytes": 0
    }
    
    async for msg in client.iter_messages(entity):
        stats["total_messages"] += 1
        if msg.video:
            stats["videos"] += 1
            sz = msg.file.size if msg.file else 0
            stats["video_total_bytes"] += sz
            stats["total_media_bytes"] += sz
        elif msg.voice:
            stats["voice"] += 1
            sz = msg.file.size if msg.file else 0
            stats["total_media_bytes"] += sz
        elif msg.photo:
            stats["photos"] += 1
            sz = msg.file.size if msg.file else 0
            stats["total_media_bytes"] += sz
        elif msg.document:
            mime = getattr(msg.document, "mime_type", "") or ""
            sz = msg.file.size if msg.file else 0
            stats["total_media_bytes"] += sz
            if "video" in mime:
                stats["videos"] += 1
                stats["video_total_bytes"] += sz
            else:
                stats["documents"] += 1
                
    stats["video_total_mb"] = round(stats["video_total_bytes"] / (1024 * 1024), 2)
    stats["total_media_mb"] = round(stats["total_media_bytes"] / (1024 * 1024), 2)
    
    return json.dumps({
        "chat_id": chat_id,
        "chat_title": getattr(entity, "title", getattr(entity, "first_name", "")),
        "stats": stats
    }, ensure_ascii=False, indent=2)


@mcp.tool()
async def tg_download_media(chat_id: str, message_id: int, output_dir: Optional[str] = None) -> str:
    """
    Download media from a specific message, EVEN IF saving is restricted in the channel.
    Args:
        chat_id: username or ID of the chat.
        message_id: integer ID of the message.
        output_dir: optional destination directory.
    Returns:
        Absolute path to the downloaded file.
    """
    client = await get_client()
    entity = await resolve_peer(client, chat_id)
    msg = await client.get_messages(entity, ids=message_id)
    if not msg or not msg.media:
        return json.dumps({"status": "error", "message": f"Message {message_id} has no media."})
        
    chat_title = sanitize_filename(getattr(entity, "title", getattr(entity, "first_name", "chat")))
    dest_dir = Path(output_dir) if output_dir else (DEFAULT_DOWNLOAD_DIR / chat_title)
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    # Determine base filename
    fname = None
    if msg.file and msg.file.name:
        fname = sanitize_filename(msg.file.name)
    elif msg.video:
        fname = f"video_msg_{msg.id}.mp4"
    elif msg.photo:
        fname = f"photo_msg_{msg.id}.jpg"
    else:
        fname = f"media_msg_{msg.id}"
        
    final_path = dest_dir / fname
    part_path = dest_dir / f"{fname}.part"
    
    t0 = time.time()
    await client.download_media(msg, file=str(part_path))
    
    if part_path.exists() and part_path.stat().st_size > 0:
        if final_path.exists():
            final_path.unlink()
        part_path.replace(final_path)
        elapsed = max(0.01, time.time() - t0)
        size_mb = final_path.stat().st_size / (1024 * 1024)
        return json.dumps({
            "status": "success",
            "file_path": str(final_path),
            "size_mb": round(size_mb, 2),
            "elapsed_seconds": round(elapsed, 2)
        }, ensure_ascii=False, indent=2)
    else:
        return json.dumps({"status": "error", "message": "Download failed or produced 0-byte file."})


@mcp.tool()
async def tg_download_all_media_background(chat_id: str, media_type: str = "video", output_dir: Optional[str] = None) -> str:
    """Start a background task to download media from the chat."""
    client = await get_client()
    entity = await resolve_peer(client, chat_id)
    chat_title = sanitize_filename(getattr(entity, "title", getattr(entity, "first_name", "chat")))
    dest_dir = Path(output_dir) if output_dir else (DEFAULT_DOWNLOAD_DIR / chat_title)
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    downloaded = 0
    total_bytes = 0
    
    async for msg in client.iter_messages(entity):
        if media_type == "video" and not msg.video:
            mime = getattr(msg.document, "mime_type", "") if msg.document else ""
            if "video" not in mime:
                continue
        elif not msg.media:
            continue
            
        fname = getattr(msg.file, "name", None) or f"msg_{msg.id}_{media_type}.mp4"
        fname = sanitize_filename(fname)
        target = dest_dir / fname
        
        if target.exists() and target.stat().st_size > 0:
            downloaded += 1
            total_bytes += target.stat().st_size
            continue
            
        part = dest_dir / f"{fname}.part"
        try:
            await client.download_media(msg, file=str(part))
            if part.exists() and part.stat().st_size > 0:
                if target.exists():
                    target.unlink()
                part.replace(target)
                downloaded += 1
                total_bytes += target.stat().st_size
        except FloodWaitError as e:
            logger.warning(f"Telegram FloodWait: {e.seconds}s")
            await asyncio.sleep(e.seconds + 1)
        except Exception as e:
            logger.error(f"Error downloading msg {msg.id}: {e}")
            
    return json.dumps({
        "status": "completed",
        "chat_id": chat_id,
        "chat_title": chat_title,
        "downloaded_files": downloaded,
        "total_mb": round(total_bytes / (1024 * 1024), 2),
        "target_directory": str(dest_dir)
    }, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    mcp.run()
