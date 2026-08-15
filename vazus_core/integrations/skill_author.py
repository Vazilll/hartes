"""
vazus_core.skill_author — Autonomous Skill Authoring & Persistence Engine.
Allows AI subagents to automatically convert successful problem-solving workflows
into permanent SKILL.md skills in ~/.gemini/config/skills/.
"""

import re
from vazus_core.engine.config import settings
from vazus_core.memory.db import get_db_connection


def create_autonomous_skill(
    skill_name: str,
    description: str,
    instructions_markdown: str,
    category: str = "Vazus OS Core"
) -> dict:
    """
    Autonomously creates a new SKILL.md file and registers it into vazus.db
    with path traversal validation and transactional persistence.
    """
    clean_name = re.sub(r"[^a-z0-9\-]", "", skill_name.lower().replace(" ", "-")).strip("-")
    if not clean_name:
        raise ValueError(f"Invalid skill name: '{skill_name}' resulted in empty identifier.")

    skills_root = settings.GEMINI_SKILLS_DIR.resolve()
    skill_dir = (skills_root / clean_name).resolve()

    # Path traversal protection
    try:
        if not skill_dir.is_relative_to(skills_root):
            raise ValueError(f"Path traversal detected: target path {skill_dir} is outside skills root {skills_root}")
    except AttributeError:
        # Fallback for older python or Windows relative path checks
        if not str(skill_dir).startswith(str(skills_root)):
            raise ValueError(f"Path traversal detected: {skill_dir}")

    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_md_path = skill_dir / "SKILL.md"

    content = f"""---
name: {clean_name}
description: {description}
---

# {skill_name} (`/{clean_name}`)

{instructions_markdown.strip()}
"""

    skill_md_path.write_text(content, encoding="utf-8")

    # Index into vazus.db with connection pooling and WAL resilience
    conn = get_db_connection()
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS skill_registry (
                name TEXT PRIMARY KEY,
                folder TEXT,
                description TEXT,
                path TEXT,
                category TEXT,
                is_active INTEGER DEFAULT 1
            );
        """)
        conn.execute("""
            INSERT OR REPLACE INTO skill_registry (name, folder, description, path, category, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
        """, (clean_name, clean_name, description, str(skill_md_path), category))

    return {
        "status": "SUCCESS",
        "skill_name": clean_name,
        "path": str(skill_md_path),
        "description": description
    }
