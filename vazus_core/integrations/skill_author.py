"""
vazus_core.integrations.skill_author — Autonomous Skill Authoring via NousResearch Hermes Standards.

Converts successful workflows into reusable SKILL.md playbooks stored in C:/vazus/skills/
following NousResearch Hardline standards:
  - name: lowercase-hyphenated, <= 64 chars
  - description: ONE sentence, <= 60 chars, ends with a period
  - indexed in vazus.db
"""

from typing import Dict, Any
from vazus_core.skills.hermes_engine import HermesSkillEngine

_engine = HermesSkillEngine()


def create_autonomous_skill(
    skill_name: str,
    description: str,
    instructions_markdown: str,
    category: str = "vazus"
) -> Dict[str, Any]:
    """
    Autonomously creates a new SKILL.md file following NousResearch standards
    and registers it into vazus.db.
    """
    res = _engine.create_skill(
        name=skill_name,
        description=description,
        instructions=instructions_markdown,
        category=category
    )
    if isinstance(res, dict) and "status" not in res:
        res["status"] = "SUCCESS" if res.get("success") else "FAILED"
    return res

