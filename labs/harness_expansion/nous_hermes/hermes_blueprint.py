"""
labs.harness_expansion.nous_hermes.hermes_blueprint
NousResearch Hermes XML Tool Calling & Skill Directory Sync Blueprint.
"""

import os
import re
import json

from pathlib import Path
from typing import Dict, Any, List, Optional

SKILLS_DIR = Path(r"C:\Users\Vaz\.gemini\config\skills")


class HermesHarnessBlueprint:
    """
    NousResearch Hermes XML Tool Calling & Skill Synchronization Harness Blueprint.
    Parses and formats XML `<tool_call>` constructs and synchronizes active agent skills.
    """

    def __init__(self, skills_path: Optional[Path] = None):
        self.skills_path = skills_path or SKILLS_DIR

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "harness_id": "nous_hermes",
            "name": "NousResearch Hermes XML Tooling & Skill Harness",
            "lab": "NousResearch",
            "domain": "tool_calling_and_skills",
            "description": "Hermes XML format tool parsing, skill directory scanning, and AGY hybrid execution.",
            "features": ["xml_tool_calling", "skill_sync", "agent_step_execution"],
        }

    def format_tool_calls(self, tool_calls: List[Dict[str, Any]]) -> str:
        """Formats tool call requests into standard Hermes XML string."""
        xml_snippets = []
        for tc in tool_calls:
            name = tc.get("name", "unknown_tool")
            args = tc.get("arguments", {})
            args_json = json.dumps(args, ensure_ascii=False)
            snippet = f"<tool_call>\n<name>{name}</name>\n<arguments>\n{args_json}\n</arguments>\n</tool_call>"
            xml_snippets.append(snippet)
        return "\n".join(xml_snippets)

    def parse_xml_response(self, response_text: str) -> List[Dict[str, Any]]:
        """Parses Hermes XML <tool_call> tags from model response string using regex and ET."""
        results = []
        pattern = re.compile(r"<tool_call>\s*<name>(.*?)</name>\s*<arguments>(.*?)</arguments>\s*</tool_call>", re.DOTALL)
        matches = pattern.findall(response_text)
        
        for name, args_str in matches:
            name_clean = name.strip()
            args_clean = args_str.strip()
            try:
                args_dict = json.loads(args_clean)
            except Exception:
                args_dict = {"raw_arguments": args_clean}
            results.append({"name": name_clean, "arguments": args_dict})
            
        if not results:
            # Fallback regex search for un-nested tags
            name_match = re.search(r"<name>(.*?)</name>", response_text)
            args_match = re.search(r"<arguments>(.*?)</arguments>", response_text, re.DOTALL)
            if name_match:
                name_clean = name_match.group(1).strip()
                args_clean = args_match.group(1).strip() if args_match else "{}"
                try:
                    args_dict = json.loads(args_clean)
                except Exception:
                    args_dict = {"raw_arguments": args_clean}
                results.append({"name": name_clean, "arguments": args_dict})
                
        return results

    def sync_skills(self, custom_skills_dir: Optional[str] = None) -> Dict[str, Any]:
        """Scans skills directory and extracts skill metadata from SKILL.md frontmatter."""
        target_dir = Path(custom_skills_dir) if custom_skills_dir else self.skills_path
        discovered_skills = []

        if target_dir.exists():
            for skill_file in target_dir.glob("**/SKILL.md"):
                try:
                    content = skill_file.read_text(encoding="utf-8")
                    skill_name = skill_file.parent.name
                    desc_match = re.search(r"description:\s*(.*)", content)
                    desc = desc_match.group(1).strip() if desc_match else "No description available"
                    discovered_skills.append({
                        "name": skill_name,
                        "path": str(skill_file),
                        "description": desc[:150],
                    })
                except Exception:
                    pass

        return {
            "status": "SUCCESS",
            "skills_directory": str(target_dir),
            "skills_count": len(discovered_skills),
            "skills": discovered_skills,
        }

    def execute_agent_step(self, prompt: str, context: Optional[str] = None) -> Dict[str, Any]:
        """Executes a Hermes tool calling step, producing prompt XML and parsing potential responses."""
        skills_summary = self.sync_skills()
        formatted_prompt = f"System: Hermes Agent System (Active Skills: {skills_summary['skills_count']})\nContext: {context or 'N/A'}\nUser: {prompt}"
        
        # Test parse if prompt contains tool call sample
        parsed_tools = self.parse_xml_response(prompt)
        
        return {
            "status": "SUCCESS",
            "prompt_formatted": formatted_prompt[:300],
            "skills_active": skills_summary["skills_count"],
            "tool_calls_detected": len(parsed_tools),
            "parsed_tool_calls": parsed_tools,
        }
