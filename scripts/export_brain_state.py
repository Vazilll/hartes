import sys
try:
    if sys.stdout:
        sys.stdout.reconfigure(encoding='utf-8')
    if sys.stderr:
        sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

import os
import re
import json
import sqlite3
from datetime import datetime

# --- Paths ---
DB_PATH = r"C:\vazus\services\memory\vazus.db"
USER_MD_PATH = r"C:\vazus\services\memory\USER.md"
DIALOGUES_DIR = r"G:\Мой диск\ai\dialogues cli"
OUTPUT_PATH = r"G:\Мой диск\ai\brain_state.md"


def read_user_md():
    """Read USER.md and split into profile and backlog sections."""
    try:
        with open(USER_MD_PATH, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        return f"*Ошибка чтения USER.md: {e}*", ""

    # Extract profile (everything before Активный Бэклог Задач)
    profile = content
    backlog = ""

    backlog_match = re.search(r'(## Активный Бэклог Задач.*)', content, re.DOTALL)
    if backlog_match:
        backlog = backlog_match.group(1).strip()
        profile = content[:backlog_match.start()].strip()

    return profile, backlog


def get_last_dialogues(n=5):
    """Read last N dialogue files, extract first user message and first assistant response."""
    if not os.path.isdir(DIALOGUES_DIR):
        return f"*Папка диалогов не найдена: {DIALOGUES_DIR}*"

    files = [f for f in os.listdir(DIALOGUES_DIR) if f.endswith(".md")]
    files.sort(reverse=True)
    files = files[:n]

    if not files:
        return "*Нет диалогов*"

    lines = []
    for fname in files:
        fpath = os.path.join(DIALOGUES_DIR, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            lines.append(f"- **{fname}**: _(ошибка чтения: {e})_")
            continue

        # Extract first user message
        user_match = re.search(r'### 👤 Пользователь.*?\n(.*?)(?=\n---|\n### |$)', content, re.DOTALL)
        user_msg = user_match.group(1).strip() if user_match else ""

        # Extract first assistant response
        assistant_match = re.search(r'### 🤖 Ассистент.*?\n(.*?)(?=\n---|\n### |$)', content, re.DOTALL)
        assistant_msg = assistant_match.group(1).strip() if assistant_match else ""

        # Truncate for readability on phone
        if len(user_msg) > 300:
            user_msg = user_msg[:297] + "..."
        if len(assistant_msg) > 500:
            assistant_msg = assistant_msg[:497] + "..."

        # Extract date from filename
        date_part = fname.split(" - ")[0] if " - " in fname else fname
        title_part = fname.replace(".md", "")
        if len(title_part) > 80:
            title_part = title_part[:77] + "..."

        lines.append(f"### 📝 {title_part}")
        if user_msg:
            lines.append(f"**Запрос:** {user_msg}")
        if assistant_msg:
            lines.append(f"**Ответ:** {assistant_msg}")
        lines.append("")

    return "\n".join(lines)


def get_user_memories():
    """Read user memories from SQLite."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT text FROM user_memories WHERE user_id='Vaz'")
        rows = cursor.fetchall()
        conn.close()
    except Exception as e:
        return f"*Ошибка чтения user_memories: {e}*"

    if not rows:
        return "*Нет записей*"

    lines = []
    for i, (text,) in enumerate(rows, 1):
        # Truncate very long entries for phone readability
        display = text if len(text) <= 500 else text[:497] + "..."
        lines.append(f"{i}. {display}")

    return "\n".join(lines)


def get_kv_facts():
    """Read KV store facts."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM kv")
        rows = cursor.fetchall()
        conn.close()
    except Exception as e:
        return f"*Ошибка чтения kv: {e}*"

    if not rows:
        return "*Нет записей*"

    lines = []
    for key, value in rows:
        val_str = str(value) if value else ""
        if len(val_str) > 300:
            val_str = val_str[:297] + "..."
        lines.append(f"- **{key}**: {val_str}")

    return "\n".join(lines)


def get_knowledge_graph_stats():
    """Get basic KG stats from the knowledge graph JSONL or graph.db."""
    stats_lines = []

    # Try knowledge_graph.jsonl first
    kg_path = r"C:\vazus\services\memory\knowledge_graph.jsonl"
    if os.path.exists(kg_path):
        try:
            nodes = []
            with open(kg_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        try:
                            entry = json.loads(line)
                            nodes.append(entry)
                        except Exception:
                            pass

            stats_lines.append(f"- **Всего записей в KG**: {len(nodes)}")

            # Count by type if available
            type_counts = {}
            domain_counts = {}
            for node in nodes:
                ntype = node.get("type", node.get("label", "unknown"))
                type_counts[ntype] = type_counts.get(ntype, 0) + 1
                domain = node.get("domain", node.get("category", ""))
                if domain:
                    domain_counts[domain] = domain_counts.get(domain, 0) + 1

            if type_counts:
                top_types = sorted(type_counts.items(), key=lambda x: -x[1])[:5]
                stats_lines.append("- **Топ типов**: " + ", ".join(f"{t} ({c})" for t, c in top_types))

            if domain_counts:
                top_domains = sorted(domain_counts.items(), key=lambda x: -x[1])[:5]
                stats_lines.append("- **Топ доменов**: " + ", ".join(f"{d} ({c})" for d, c in top_domains))

        except Exception as e:
            stats_lines.append(f"*Ошибка чтения KG: {e}*")
    else:
        stats_lines.append("*Файл knowledge_graph.jsonl не найден*")

    # Try graph.db for additional stats
    graph_db = r"C:\vazus\services\memory\graph.db"
    if os.path.exists(graph_db):
        try:
            conn = sqlite3.connect(graph_db)
            cursor = conn.cursor()
            # Try to get table names
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in cursor.fetchall()]
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM [{table}]")
                count = cursor.fetchone()[0]
                stats_lines.append(f"- **{table}**: {count} записей")
            conn.close()
        except Exception as e:
            stats_lines.append(f"*Ошибка чтения graph.db: {e}*")

    return "\n".join(stats_lines) if stats_lines else "*Нет данных*"


def export_brain_state():
    """Generate the brain state markdown file."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    profile, backlog = read_user_md()
    dialogues = get_last_dialogues(5)
    memories = get_user_memories()
    kv_facts = get_kv_facts()
    kg_stats = get_knowledge_graph_stats()

    md = f"""# 🧠 Состояние Мозга DNTS

> **Последнее обновление:** {now}
> **Автоматически сгенерировано** скриптом export_brain_state.py

---

## 👤 Профиль Пользователя

{profile}

---

## 📋 Активные Задачи

{backlog}

---

## 💬 Последние 5 Диалогов (Краткое содержание)

{dialogues}

---

## 🧠 Воспоминания (user_memories)

> ⚠️ **Примечание:** Некоторые записи могут быть зашифрованы. Зашифрованные поля отображаются как есть — для расшифровки требуется локальная система DNTS.

{memories}

---

## 📊 Статистика Knowledge Graph

{kg_stats}

---

## 🔑 KV-Хранилище (Факты)

{kv_facts}

---

*Файл для чтения Gemini на телефоне. Генерируется каждые 10 минут.*
"""

    try:
        os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"Brain state exported to {OUTPUT_PATH}")
    except Exception as e:
        print(f"Error writing brain state: {e}")
        raise


if __name__ == "__main__":
    export_brain_state()
