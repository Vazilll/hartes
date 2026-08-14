#!/usr/bin/env python3
"""
TARS OS — Post-Commit Hook Handler
====================================
Triggered automatically by Git after every commit.
Pipeline:
  1. Parse changed files from git log
  2. Write memory trace to vazus.db (System 2 slow memory)
  3. Generate/update Obsidian Zettelkasten note
  4. Push bilingual vocab card to Google Tasks (Pixel 10)

Usage (called by .git/hooks/post-commit):
  python C:/vazus/harness/autonomy/tars_hook_handler.py
"""

import os
import sys
import subprocess
import sqlite3
import json
import re
from pathlib import Path
from datetime import datetime

# Force UTF-8 output on Windows (avoids cp1252 UnicodeEncodeError)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# ── Config ────────────────────────────────────────────────────────────────────
VAZUS_ROOT = Path("C:/vazus")
DB_PATH = VAZUS_ROOT / "services/memory/vazus.db"
WIKI_DIR = VAZUS_ROOT / "services/memory/semantic/wiki"
TOKEN_PATH = VAZUS_ROOT / "data/sessions/token.json"
SKILL_TRIGGERS = {
    ".cpp": "mirea-programming-cpp-rust-english",
    ".rs":  "mirea-programming-cpp-rust-english",
    ".zig": "mirea-programming-cpp-rust-english",
    ".py":  "vazus-core-python",
    ".md":  "knowledge-base",
}

# ── Helpers ───────────────────────────────────────────────────────────────────
def run(cmd: list[str]) -> str:
    try:
        return subprocess.check_output(cmd, text=True, cwd=str(VAZUS_ROOT)).strip()
    except subprocess.CalledProcessError:
        return ""

def get_commit_info() -> dict:
    """Read metadata from the latest git commit."""
    return {
        "hash":    run(["git", "log", "-1", "--format=%H"]),
        "short":   run(["git", "log", "-1", "--format=%h"]),
        "author":  run(["git", "log", "-1", "--format=%an"]),
        "message": run(["git", "log", "-1", "--format=%s"]),
        "branch":  run(["git", "rev-parse", "--abbrev-ref", "HEAD"]),
        "files":   run(["git", "diff-tree", "--no-commit-id", "-r", "--name-only", "HEAD"]).splitlines(),
        "stats":   run(["git", "log", "-1", "--stat", "--format="]),
    }

def detect_skills(files: list[str]) -> set[str]:
    """Map changed file extensions to TARS skill names."""
    skills = set()
    for f in files:
        ext = Path(f).suffix.lower()
        if ext in SKILL_TRIGGERS:
            skills.add(SKILL_TRIGGERS[ext])
    return skills

# ── Step 1: Save Memory Trace to vazus.db with 768D Vector Embeddings ─────────
def save_memory_trace(commit: dict, skills: set) -> str:
    """Write structured commit memory trace to System 2 slow memory with 768D vectors."""
    summary = f"[{commit['branch']}] {commit['short']}: {commit['message']}"
    content_dict = {
        "hash": commit["hash"],
        "branch": commit["branch"],
        "message": commit["message"],
        "files_changed": commit["files"],
        "skills_triggered": list(skills),
        "stats": commit["stats"],
        "recorded_at": datetime.now().isoformat(),
    }
    content = json.dumps(content_dict, ensure_ascii=False, indent=2)
    note_path = f"Commits/{commit['short']}.md"

    # Compute real 768D vector embedding for semantic search / MCP recall
    vector_768d = []
    try:
        sys.path.insert(0, str(VAZUS_ROOT))
        from vazus_core.memory.embeddings import get_embedding
        embed_text = f"Git Commit {commit['short']}: {commit['message']}. Branch: {commit['branch']}. Files: {', '.join(commit['files'])}. Skills: {', '.join(skills)}"
        vector_768d = get_embedding(embed_text)
    except Exception as e:
        print(f"  ⚠️  [Embedder Note] Could not compute vector: {e}")

    try:
        from vazus_core.memory.db import get_db_connection
        with get_db_connection() as conn:
            conn.execute("""
                INSERT INTO subagent_memory_traces
                    (agent_name, trace_kind, summary, content, obsidian_note_path, created_at)
                VALUES (?, ?, ?, ?, ?, datetime('now'))
            """, ("tars-git-hook", "commit", summary, content, note_path))

            node_id = f"commit_{commit['short']}"
            tags_str = "#git #commit " + " ".join(f"#{s}" for s in skills)
            conn.execute("""
                INSERT OR REPLACE INTO kg_nodes 
                    (id, name, domain, node_type, description, tags, properties, embedding_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                node_id,
                f"Commit {commit['short']}",
                "git_commit",
                "commit",
                summary,
                tags_str,
                content,
                json.dumps(vector_768d) if vector_768d else None
            ))
            conn.commit()
    except Exception as e:
        # Fallback to direct sqlite connection if module import has issues
        conn = sqlite3.connect(str(DB_PATH))
        try:
            conn.execute("""
                INSERT INTO subagent_memory_traces
                    (agent_name, trace_kind, summary, content, obsidian_note_path, created_at)
                VALUES (?, ?, ?, ?, ?, datetime('now'))
            """, ("tars-git-hook", "commit", summary, content, note_path))
            conn.commit()
        finally:
            conn.close()

    dim_info = f" ({len(vector_768d)}D vector)" if vector_768d else ""
    print(f"  ✅ [DB] Memory trace + KG node saved: {summary}{dim_info}")
    return note_path

# ── Step 2: Create/Update Obsidian Zettelkasten Note ─────────────────────────
def create_obsidian_note(commit: dict, skills: set) -> Path:
    """Generate a Zettelkasten note for this commit."""
    WIKI_DIR.mkdir(parents=True, exist_ok=True)
    commits_dir = WIKI_DIR / "Commits"
    commits_dir.mkdir(exist_ok=True)

    note_path = commits_dir / f"{commit['short']}.md"
    files_list = "\n".join(f"  - `{f}`" for f in commit["files"]) or "  - (no files)"
    skills_list = "\n".join(f"  - [[{s}]]" for s in skills) or "  - (none)"

    note_content = f"""# 🔀 Commit `{commit['short']}` — {commit['message']}

> **Branch:** `{commit['branch']}`  
> **Author:** {commit['author']}  
> **Time:** {datetime.now().strftime('%Y-%m-%d %H:%M')}  
> **Tags:** #git #commit #tars

---

## 📁 Changed Files
{files_list}

## 🎯 Skills Triggered
{skills_list}

## 📊 Diff Stats
```
{commit['stats'] or '(no stats)'}
```

## 🔗 Cross-References
- [[TARS_Knowledge_Graph_Bridge]]
- [[Ring_Buffer_RAII]]

---
*Auto-generated by TARS Git post-commit hook*
"""
    note_path.write_text(note_content, encoding="utf-8")
    print(f"  ✅ [Obsidian] Zettelkasten note: {note_path}")
    return note_path

# ── Step 3: Push Vocab Card to Google Tasks (Pixel 10) ───────────────────────
def push_pixel_task(commit: dict, skills: set) -> bool:
    """Send a bilingual commit summary card to Google Tasks on Pixel 10."""
    if not TOKEN_PATH.exists():
        print("  ⚠️  [Tasks] token.json not found — skipping Pixel 10 push.")
        return False

    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH))
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())

        service = build("tasks", "v1", credentials=creds)
        tasklists = service.tasklists().list().execute().get("items", [])
        if not tasklists:
            print("  ⚠️  [Tasks] No task lists found.")
            return False

        tlist_id = tasklists[0]["id"]
        files_preview = ", ".join(commit["files"][:3])
        if len(commit["files"]) > 3:
            files_preview += f" +{len(commit['files'])-3} more"

        skills_str = ", ".join(skills) or "none"

        body = {
            "title": f"🔀 TARS Commit | [{commit['branch']}] {commit['message'][:50]}",
            "notes": (
                f"📌 Hash: {commit['short']}\n"
                f"📂 Files: {files_preview or 'none'}\n"
                f"🎯 Skills: {skills_str}\n\n"
                f"🇬🇧 Commit = a saved snapshot of code changes with a message describing intent.\n"
                f"🇷🇺 Коммит = сохранённый снимок изменений в коде с описанием цели правки."
            ),
        }

        result = service.tasks().insert(tasklist=tlist_id, body=body).execute()
        print(f"  ✅ [Pixel 10] Task pushed: '{result.get('title')}'")
        return True

    except Exception as e:
        print(f"  ❌ [Tasks] Error: {e}")
        return False

# ── Main Pipeline ─────────────────────────────────────────────────────────────
def main():
    print()
    print("╔══════════════════════════════════════════════╗")
    print("║  🤖 TARS OS — Git Post-Commit Hook Activated  ║")
    print("╚══════════════════════════════════════════════╝")

    commit = get_commit_info()

    print(f"\n📝 Commit: [{commit['branch']}] {commit['short']} — {commit['message']}")
    print(f"📁 Files changed ({len(commit['files'])}):")
    for f in commit["files"]:
        print(f"     • {f}")

    skills = detect_skills(commit["files"])
    if skills:
        print(f"🎯 Skills triggered: {', '.join(skills)}")
    else:
        print("🎯 No specific skills triggered.")

    print("\n── Running TARS Hook Pipeline ──────────────────")
    save_memory_trace(commit, skills)
    create_obsidian_note(commit, skills)
    push_pixel_task(commit, skills)

    print("\n✅ TARS hook pipeline complete.\n")

if __name__ == "__main__":
    main()
