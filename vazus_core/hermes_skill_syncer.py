"""
vazus_core.hermes_skill_syncer
Bridge to import and sync NousResearch Hermes agent skills into Antigravity CLI skills environment.
"""

import os
import shutil
import re

HERMES_SKILLS_DIR = r"C:\Users\Vaz\AppData\Local\hermes\hermes-agent\skills"
ANTIGRAVITY_SKILLS_DIR = r"C:\Users\Vaz\.gemini\config\skills"

def sync_hermes_skills():
    if not os.path.exists(HERMES_SKILLS_DIR):
        print(f"[!] Hermes skills directory not found: {HERMES_SKILLS_DIR}")
        return 0

    os.makedirs(ANTIGRAVITY_SKILLS_DIR, exist_ok=True)
    synced_count = 0

    for root, dirs, files in os.walk(HERMES_SKILLS_DIR):
        if "SKILL.md" in files:
            rel_dir = os.path.relpath(root, HERMES_SKILLS_DIR)
            skill_folder_name = "hermes-" + rel_dir.replace(os.sep, "-").replace("\\", "-").lower()
            target_skill_dir = os.path.join(ANTIGRAVITY_SKILLS_DIR, skill_folder_name)

            os.makedirs(target_skill_dir, exist_ok=True)

            # Copy all contents of skill folder
            for item in os.listdir(root):
                s_path = os.path.join(root, item)
                d_path = os.path.join(target_skill_dir, item)
                if os.path.isdir(s_path):
                    if os.path.exists(d_path):
                        shutil.rmtree(d_path)
                    shutil.copytree(s_path, d_path)
                else:
                    shutil.copy2(s_path, d_path)

            synced_count += 1

    print(f"[+] Successfully synced {synced_count} Hermes skills into Antigravity environment ({ANTIGRAVITY_SKILLS_DIR})")
    return synced_count


class AutomaticSkillSelector:
    """
    Automatic Skill Selection & Context Injection Engine.
    Parses skill metadata from ~/.gemini/config/skills/ and project .agents/skills/
    and matches prompt intent to automatically pull relevant SKILL.md into context on demand.
    """

    def __init__(self, skills_dir: str = ANTIGRAVITY_SKILLS_DIR):
        self.skills_dir = skills_dir
        self.skills_index = self._build_skills_index()

    _SHARED_SKILLS_INDEX = None

    def _build_skills_index(self):
        if AutomaticSkillSelector._SHARED_SKILLS_INDEX is not None:
            return AutomaticSkillSelector._SHARED_SKILLS_INDEX
        index = []
        if not os.path.exists(self.skills_dir):
            return index

        for root, dirs, files in os.walk(self.skills_dir):
            if "SKILL.md" in files:
                skill_md_path = os.path.join(root, "SKILL.md")
                try:
                    with open(skill_md_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()

                    # Extract YAML frontmatter metadata
                    name_match = re.search(r"^name:\s*(.+)$", content, re.MULTILINE)
                    desc_match = re.search(r"^description:\s*[\"']?(.+?)[\"']?$", content, re.MULTILINE)

                    name = name_match.group(1).strip() if name_match else os.path.basename(root)
                    desc = desc_match.group(1).strip() if desc_match else ""

                    index.append({
                        "name": name,
                        "description": desc,
                        "path": skill_md_path,
                        "folder": root
                    })
                except Exception:
                    continue
        AutomaticSkillSelector._SHARED_SKILLS_INDEX = index
        return index

    def select_matching_skills(self, prompt: str, top_k: int = 2) -> list:
        """Matches prompt keywords/intent against registered skill descriptions."""
        if not prompt or not self.skills_index:
            return []

        prompt_lower = prompt.lower()
        scored_skills = []

        for skill in self.skills_index:
            score = 0
            s_name = skill["name"].lower()
            s_desc = skill["description"].lower()

            # Keyword matching heuristics
            keywords = s_name.split("-") + s_desc.split()
            for kw in set(keywords):
                if len(kw) > 3 and kw in prompt_lower:
                    score += 1.0

            if "debug" in prompt_lower and "debug" in s_name:
                score += 3.0
            if "plan" in prompt_lower and "plan" in s_name:
                score += 3.0
            if ("test" in prompt_lower or "tdd" in prompt_lower) and "test" in s_name:
                score += 3.0

            if score > 0:
                scored_skills.append((score, skill))

        scored_skills.sort(key=lambda x: x[0], reverse=True)
        return [skill for _, skill in scored_skills[:top_k]]

    def load_skill_content(self, skill_name: str) -> str:
        """Loads SKILL.md file content for a given skill name."""
        for skill in self.skills_index:
            if skill["name"] == skill_name or os.path.basename(skill["folder"]) == skill_name:
                try:
                    with open(skill["path"], "r", encoding="utf-8", errors="ignore") as f:
                        return f.read()
                except Exception:
                    pass
        return ""


if __name__ == "__main__":
    sync_hermes_skills()
    selector = AutomaticSkillSelector()
    matches = selector.select_matching_skills("Need systematic debugging for failing tests")
    print(f"[+] Skill Matches: {[m['name'] for m in matches]}")

