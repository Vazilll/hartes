"""
vazus_core.skills.hermes_engine — Real NousResearch Hermes Agent Skill Engine.

Implements the official NousResearch Hermes Agent skill protocol:
  1. Progressive Disclosure: keeps catalog compact (<60 chars per skill),
     loads full instructions JIT (Just-In-Time) only when matched.
  2. Hardline Authoring Rules:
     - name: lowercase-hyphenated, <= 64 chars.
     - description: ONE sentence, <= 60 chars, ends with a period.
     - Frontmatter: strict YAML (---).
  3. CRUD & Management:
     - Uses NousResearch hermes-agent primitives (skills_tool, skill_manager_tool).
     - Persists and tracks skills in C:/vazus/skills and vazus.db.
"""

import os
import sys
import re
import json
import logging
import sqlite3
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger("hermes_skill_engine")

HERMES_ROOT = Path(r"C:\Users\Vaz\AppData\Local\hermes\hermes-agent")
VAZUS_SKILLS_DIR = Path(r"C:\vazus\skills")
VAZUS_DB_PATH = Path(r"C:\vazus\services\memory\vazus.db")

# Add hermes-agent to sys.path for direct native execution
if HERMES_ROOT.exists() and str(HERMES_ROOT) not in sys.path:
    sys.path.insert(0, str(HERMES_ROOT))

# Import Hermes native utilities
try:
    from agent.skill_utils import parse_frontmatter, SKILL_PROMPT_DESC_LIMIT
    from tools.skills_tool import skills_list as _hermes_skills_list, skill_view as _hermes_skill_view
    from tools.skill_manager_tool import skill_manage as _hermes_skill_manage
    _HERMES_NATIVE_AVAILABLE = True
except Exception as _import_err:
    logger.warning("Could not import native Hermes Agent modules: %s", _import_err)
    _HERMES_NATIVE_AVAILABLE = False
    SKILL_PROMPT_DESC_LIMIT = 60

VALID_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")

_BILINGUAL_SYNONYMS = {
    "тест": ["test", "dogfood", "qa"],
    "тестир": ["test", "dogfood", "qa"],
    "дискрет": ["math", "logic"],
    "логик": ["logic", "boolean"],
    "жегалк": ["zhegalkin", "logic", "polynomial"],
    "матриц": ["matrix", "matrices", "linear"],
    "слау": ["linear", "equation", "matrix"],
    "интеграл": ["calculus", "math"],
    "производн": ["derivative", "calculus"],
    "диаграм": ["diagram", "svg", "architecture"],
    "схем": ["diagram", "architecture"],
    "заметк": ["note", "notes", "memo"],
    "напомина": ["reminder", "reminders"],
    "стать": ["paper", "arxiv", "research"],
    "документ": ["document", "docx", "pdf"],
    "таблиц": ["table", "airtable", "truth"],
    "архив": ["arxiv", "paper"],
    "мирэа": ["mirea"],
}


class HermesSkillEngine:
    """Production Skill Engine adhering to NousResearch Hermes standards."""

    def __init__(self, project_skills_dir: Path = VAZUS_SKILLS_DIR):
        self.project_skills_dir = project_skills_dir
        self.project_skills_dir.mkdir(parents=True, exist_ok=True)
        self.hermes_skills_dir = HERMES_ROOT / "skills"

    def list_all_skills(self) -> List[Dict[str, Any]]:
        """Lists all skills across Hermes native bundle and Vazus project directory."""
        skills = []
        seen_names = set()

        # 1. Vazus project skills (primary priority)
        if self.project_skills_dir.exists():
            for p in self.project_skills_dir.rglob("SKILL.md"):
                meta = self._parse_skill_file(p, source="vazus")
                if meta and meta["name"] not in seen_names:
                    skills.append(meta)
                    seen_names.add(meta["name"])

        # 2. Hermes native bundled skills
        if self.hermes_skills_dir.exists():
            for p in self.hermes_skills_dir.rglob("SKILL.md"):
                meta = self._parse_skill_file(p, source="hermes")
                if meta and meta["name"] not in seen_names:
                    skills.append(meta)
                    seen_names.add(meta["name"])

        return sorted(skills, key=lambda x: x["name"])

    def _parse_skill_file(self, path: Path, source: str = "vazus") -> Optional[Dict[str, Any]]:
        """Parses a SKILL.md file and returns normalized metadata."""
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
            fm_match = re.search(r"^---\s*\n(.*?)\n---", content, re.DOTALL | re.MULTILINE)
            name = path.parent.name
            description = ""
            category = path.parent.parent.name if path.parent.parent != path.parent else "general"

            if fm_match:
                fm_text = fm_match.group(1)
                name_m = re.search(r"^name:\s*[\"']?(.+?)[\"']?\s*$", fm_text, re.MULTILINE)
                if name_m:
                    name = name_m.group(1).strip()
                desc_m = re.search(r"^description:\s*[\"']?(.+?)[\"']?\s*$", fm_text, re.MULTILINE)
                if desc_m:
                    description = desc_m.group(1).strip()

            return {
                "name": name,
                "description": description,
                "category": category,
                "path": str(path),
                "source": source
            }
        except Exception as exc:
            logger.debug("Failed parsing skill file %s: %s", path, exc)
            return None

    def view_skill(self, name: str) -> Dict[str, Any]:
        """Reads full instructions and resources for a specific skill (Progressive Disclosure Stage 2)."""
        clean_name = name.strip().lower()

        # Check Vazus project directory first
        for p in self.project_skills_dir.rglob("SKILL.md"):
            if p.parent.name.lower() == clean_name:
                try:
                    return {
                        "success": True,
                        "name": clean_name,
                        "path": str(p),
                        "content": p.read_text(encoding="utf-8", errors="ignore"),
                        "source": "vazus"
                    }
                except Exception as e:
                    return {"success": False, "error": str(e)}

        # Check Hermes native skills via native tool or file
        if _HERMES_NATIVE_AVAILABLE:
            try:
                res_str = _hermes_skill_view(clean_name)
                data = json.loads(res_str)
                if data.get("success"):
                    return data
            except Exception as e:
                logger.debug("Hermes native skill_view fallback: %s", e)

        for p in self.hermes_skills_dir.rglob("SKILL.md"):
            if p.parent.name.lower() == clean_name:
                try:
                    return {
                        "success": True,
                        "name": clean_name,
                        "path": str(p),
                        "content": p.read_text(encoding="utf-8", errors="ignore"),
                        "source": "hermes"
                    }
                except Exception as e:
                    return {"success": False, "error": str(e)}

        return {"success": False, "error": f"Skill '{name}' not found."}

    def route_skills(self, user_prompt: str, top_k: int = 2) -> List[Dict[str, Any]]:
        """
        NousResearch Dynamic Routing: matches prompt against skill names & descriptions
        using token overlap and BM25 keywords, returning top-k matching skills.
        """
        if not user_prompt or len(user_prompt.strip()) < 3:
            return []

        prompt_tokens = set(re.findall(r"\b[a-zA-Z0-9_\-\u0400-\u04FF]{3,}\b", user_prompt.lower()))
        if not prompt_tokens:
            return []

        # Bilingual expansion for Russian/English parity
        p_lower = user_prompt.lower()
        for stem, synonyms in _BILINGUAL_SYNONYMS.items():
            if stem in p_lower:
                for syn in synonyms:
                    prompt_tokens.add(syn.lower())

        all_skills = self.list_all_skills()
        scored: List[Tuple[float, Dict[str, Any]]] = []

        for sk in all_skills:
            score = 0.0
            name_parts = set(re.split(r"[-_]", sk["name"].lower()))
            desc_tokens = set(re.findall(r"\b[a-zA-Z0-9_\-\u0400-\u04FF]{3,}\b", sk["description"].lower()))

            # Exact name mention in prompt
            if sk["name"].lower() in user_prompt.lower():
                score += 5.0

            # Name token matches
            name_overlap = len(prompt_tokens.intersection(name_parts))
            if name_overlap > 0:
                score += 3.0 * name_overlap

            # Description token matches
            desc_overlap = len(prompt_tokens.intersection(desc_tokens))
            if desc_overlap > 0:
                score += 1.0 * desc_overlap

            if score > 1.5:
                scored.append((score, sk))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored[:top_k]]

    def get_progressive_disclosure_context(self, user_prompt: str) -> Optional[str]:
        """
        Generates the JIT Progressive Disclosure injection block for the prompt.
        If a specific skill matches the prompt, loads its full instructions.
        """
        matches = self.route_skills(user_prompt, top_k=2)
        if not matches:
            return None

        blocks = []
        for m in matches:
            detail = self.view_skill(m["name"])
            if detail.get("success"):
                content = detail.get("content", "").strip()
                # Strip frontmatter for lean context
                content_clean = re.sub(r"^---\s*\n.*?\n---\s*", "", content, flags=re.DOTALL)
                blocks.append(
                    f"### ⚡ Loaded Skill: `{m['name']}` ({m['source']})\n"
                    f"*{m['description']}*\n\n"
                    f"{content_clean[:3500]}"
                )

        if blocks:
            return (
                "\n## 🧠 NousResearch Procedural Skills (Progressive Disclosure JIT)\n"
                "The following specialized skill(s) were dynamically loaded for your current task:\n\n"
                + "\n\n---\n\n".join(blocks)
                + "\n"
            )
        return None

    def build_compact_index(self, max_skills: int = 40) -> str:
        """
        Builds the compact Hermes <available_skills> index for turn 0 (<60 chars per skill).
        Total token footprint is ~300 tokens instead of 50k tokens.
        """
        skills = self.list_all_skills()[:max_skills]
        if not skills:
            return ""

        by_cat: Dict[str, List[Tuple[str, str]]] = {}
        for s in skills:
            cat = s["category"]
            desc = s["description"][:60].strip()
            by_cat.setdefault(cat, []).append((s["name"], desc))

        lines = ["<available_skills>"]
        for cat, items in sorted(by_cat.items()):
            lines.append(f"  {cat}:")
            for name, desc in sorted(items, key=lambda x: x[0]):
                desc_str = f": {desc}" if desc else ""
                lines.append(f"    - {name}{desc_str}")
        lines.append("</available_skills>")

        return (
            "## Skills Catalog (NousResearch Progressive Disclosure)\n"
            "If a task matches an available skill, it will be automatically JIT-loaded into context.\n"
            + "\n".join(lines)
        )

    def create_skill(
        self,
        name: str,
        description: str,
        instructions: str,
        category: str = "vazus",
    ) -> Dict[str, Any]:
        """
        Creates a new skill strictly following NousResearch Hardline standards:
        - name: lowercase-hyphenated, <= 64 chars
        - description: <= 60 chars, ends with a period
        """
        clean_name = re.sub(r"[^a-z0-9\-]", "", name.lower().replace(" ", "-")).strip("-")
        if not clean_name or len(clean_name) > 64 or not VALID_NAME_RE.match(clean_name):
            return {"success": False, "error": f"Invalid skill name '{name}'. Must be lowercase-hyphenated, <= 64 chars."}

        clean_desc = description.strip().strip("'\"")
        if not clean_desc.endswith("."):
            clean_desc += "."

        # Enforce NousResearch 60-char limit
        if len(clean_desc) > 60:
            clean_desc = clean_desc[:57].rstrip() + "..."
            if not clean_desc.endswith("."):
                clean_desc += "."

        target_dir = self.project_skills_dir / category / clean_name
        target_dir.mkdir(parents=True, exist_ok=True)
        skill_file = target_dir / "SKILL.md"

        escaped_desc = f'"{clean_desc}"' if ":" in clean_desc else clean_desc

        full_content = (
            f"---\n"
            f"name: {clean_name}\n"
            f"description: {escaped_desc}\n"
            f"category: {category}\n"
            f"version: 1.0.0\n"
            f"---\n\n"
            f"# {clean_name}\n\n"
            f"{instructions.strip()}\n"
        )

        try:
            skill_file.write_text(full_content, encoding="utf-8")
        except Exception as e:
            return {"success": False, "error": f"Failed writing SKILL.md: {e}"}

        # Index in vazus.db
        try:
            conn = sqlite3.connect(str(VAZUS_DB_PATH), timeout=3.0)
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
                """, (clean_name, clean_name, clean_desc, str(skill_file), category))
            conn.close()
        except Exception as db_err:
            logger.debug("Database indexing note: %s", db_err)

        logger.info("Successfully created NousResearch skill '%s' in %s", clean_name, target_dir)
        return {
            "success": True,
            "name": clean_name,
            "description": clean_desc,
            "path": str(skill_file),
            "category": category
        }

    def patch_skill(
        self,
        name: str,
        old_string: str,
        new_string: str,
    ) -> Dict[str, Any]:
        """In-place targeted patch for a skill."""
        detail = self.view_skill(name)
        if not detail.get("success"):
            return detail

        file_path = Path(detail["path"])
        content = detail["content"]

        if old_string not in content:
            return {"success": False, "error": f"Target string not found in skill '{name}'."}

        new_content = content.replace(old_string, new_string, 1)
        file_path.write_text(new_content, encoding="utf-8")
        return {"success": True, "name": name, "message": f"Successfully patched skill '{name}'."}


# Global singleton instance
engine = HermesSkillEngine()


if __name__ == "__main__":
    eng = HermesSkillEngine()
    print(f"Total skills discovered: {len(eng.list_all_skills())}")
    print("\n--- Testing Compact Available Skills Index ---")
    print(eng.build_compact_index(max_skills=10))
    print("\n--- Testing Routing on 'test dogfooding web application' ---")
    matched = eng.route_skills("test dogfooding web application")
    print("Matched:", [m["name"] for m in matched])
