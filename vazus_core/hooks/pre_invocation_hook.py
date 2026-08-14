#!/usr/bin/env python3
"""
vazus_core.hooks.pre_invocation_hook — Antigravity PreInvocation Lifecycle Hook.

Called AUTOMATICALLY by Antigravity BEFORE every model invocation.
On turn 0: injects MCP tool instructions AND auto-selects up to 3 relevant SKILL.md
           files based on the user's prompt using DynamicSkillDispatcher (768D vectors).
On turn N: injects nothing (to avoid context bloat).

Triggered by hooks.json — NOT a manual script.
"""

import sys
import json
import os

# Add vazus to path
sys.path.insert(0, "C:/vazus")

try:
    from vazus_core.hooks.hud_writer import write_hud_event
except Exception:
    def write_hud_event(event_type, payload): pass

MCP_INSTRUCTIONS = """## 🔧 Vazus OS MCP Tools Available (call via `call_mcp_tool`)

### Server: `codebase-memory-mcp` (AST Code Graph — 683K nodes)
- `get_architecture` — Codebase architecture overview. Args: `{"aspects": ["overview"], "project": "C-vazus"}`
- `search_code` — Semantic code search. Args: `{"query": "...", "project": "C-vazus"}`
- `query_graph` — Cypher-like graph query. Args: `{"query": "MATCH ...", "project": "C-vazus"}`
- `trace_path` — Trace call path between symbols. Args: `{"from_symbol": "A", "to_symbol": "B", "project": "C-vazus"}`
- `get_code_snippet` — Get source by qualified name. Args: `{"qualified_name": "C-vazus.module.func", "project": "C-vazus"}`

### Server: `vazus-organic` (Memory, AST Pruning, Z3 Proofs, Evolution)
- `vazus_organic_recall` — Search 768D vector memory. Args: `{"query": "...", "top_k": 5}`
- `vazus_record_insight` — Persist insight/lesson. Args: `{"category": "...", "insight": "..."}`
- `vazus_ast_prune` — AST signature compression (>70%). Args: `{"code_or_file": "path.py"}`
- `vazus_smt_z3_verify` — Formal Z3 contract proof. Args: `{"code": "...", "depth": 10}`
- `vazus_darwinian_evolve` — Genetic mutation + pytest fitness (run via subagent). Args: `{"target_module": "vazus_core", "generations": 2}`

### Server: `vazus-reasoning` (Reasoning & Jury)
- `vazus_smt_z3_verify_contract` — Contract-style Z3 verification.
- `vazus_concordia_jury_vote` — Cast formal jury vote (APPROVED/REJECTED).

### Execution Note for Subagents
- If `call_mcp_tool` is present in your tool schema, use `call_mcp_tool` directly.
- If `call_mcp_tool` is NOT in your tool schema, call MCP tools via `run_command`:
  `python C:\\vazus\\vazus_core\\mcp_client.py <server_name> <tool_name> '<json_args>'`
- Python Virtualenv: `C:\\vazus\\.venv\\Scripts\\python.exe`
- Workspace: `C:\\vazus` (must be in sys.path)
"""

# Additional skill directories to search (built-in AGY skills included)
SKILL_SEARCH_DIRS = [
    r"C:\Users\Vaz\.gemini\config\skills",
    r"C:\Users\Vaz\.gemini\antigravity-cli\builtin\skills",
    r"C:\vazus\.agents\skills",
]

MAX_SKILLS_TO_INJECT = 3
MAX_SKILL_CONTENT_CHARS = 3000  # per skill, to avoid context bloat


import re

def clean_user_prompt(text: str) -> str:
    if not text:
        return ""
    # Strip <USER_REQUEST> tags if present
    match = re.search(r"<USER_REQUEST>\s*(.*?)\s*</USER_REQUEST>", text, re.DOTALL)
    if match:
        text = match.group(1)
    # Strip metadata and setting changes
    text = re.sub(r"<ADDITIONAL_METADATA>.*?</ADDITIONAL_METADATA>", "", text, flags=re.DOTALL)
    text = re.sub(r"<USER_SETTINGS_CHANGE>.*?</USER_SETTINGS_CHANGE>", "", text, flags=re.DOTALL)
    return text.strip()


def extract_user_prompt(hook_data: dict) -> str:
    """Extract the most recent user prompt from hook data across all Antigravity formats."""
    # 1. Direct top-level keys
    for k in ["userPrompt", "prompt", "userQuery", "query", "user_prompt", "input", "userInput", "text"]:
        if hook_data.get(k):
            val = hook_data[k]
            if isinstance(val, str) and val.strip():
                return clean_user_prompt(val)

    # 2. Conversation messages list
    messages = hook_data.get("messages", [])
    if isinstance(messages, list):
        for msg in reversed(messages):
            if isinstance(msg, dict):
                role = str(msg.get("role", "")).lower()
                source = str(msg.get("source", "")).lower()
                stype = str(msg.get("type", "")).lower()
                if role in ("user", "user_explicit") or "user" in source or "user" in stype:
                    content = msg.get("content", "")
                    if isinstance(content, list):
                        parts = []
                        for block in content:
                            if isinstance(block, dict):
                                parts.append(str(block.get("text", block.get("content", ""))))
                            elif isinstance(block, str):
                                parts.append(block)
                        if parts:
                            return clean_user_prompt("\n".join(parts))
                    elif isinstance(content, str) and content.strip():
                        return clean_user_prompt(content)

    # 3. Fallback: inspect any string field containing <USER_REQUEST>
    for k, v in hook_data.items():
        if isinstance(v, str) and "<USER_REQUEST>" in v:
            return clean_user_prompt(v)

    return ""


def auto_select_skills(user_prompt: str) -> list:
    """
    Uses DynamicSkillDispatcher to find top-k relevant skills for the user prompt.
    Returns list of dicts: [{"name": ..., "path": ..., "content": ...}]
    Falls back to empty list on any error (hook must never crash the agent).
    """
    if not user_prompt or len(user_prompt.strip()) < 10:
        return []

    try:
        from vazus_core.dynamic_skill_dispatcher import SkillIntentParser

        parser = SkillIntentParser(search_dirs=SKILL_SEARCH_DIRS, auto_index=True)
        matched = parser.match_skills(user_prompt, top_k=MAX_SKILLS_TO_INJECT, effort="medium")

        result = []
        for skill in matched:
            if skill.score < 0.15:
                # Below threshold — not relevant enough
                continue
            try:
                with open(skill.skill_md_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                # Truncate to avoid flooding context
                if len(content) > MAX_SKILL_CONTENT_CHARS:
                    content = content[:MAX_SKILL_CONTENT_CHARS] + "\n\n[... truncated for context efficiency ...]"
                result.append({
                    "name": skill.name,
                    "path": skill.skill_md_path,
                    "score": skill.score,
                    "content": content
                })
            except Exception:
                pass

        return result

    except Exception:
        return []


def auto_retrieve_memory(user_prompt: str, invocation_num: int) -> str:
    """
    Passively retrieves long-term user profile, 768D semantic facts, and recent system traces.
    Injects them directly into the agent prompt before generation.
    """
    lines = []

    # 1. On turn 0, inject core User Profile and Preferences (USER.md)
    if invocation_num == 0:
        user_md_path = "C:/vazus/services/memory/USER.md"
        if os.path.exists(user_md_path):
            try:
                with open(user_md_path, "r", encoding="utf-8", errors="ignore") as f:
                    u_content = f.read().strip()
                    if u_content:
                        lines.append(f"\n## 👤 User Profile & Preferences (USER.md)\n{u_content}\n")
            except Exception:
                pass

    # 2. Semantic Mem0 Facts search based on current user prompt
    if user_prompt and len(user_prompt.strip()) > 5:
        try:
            from vazus_core.memory.mem0_memory_engine import Mem0Engine
            mem0 = Mem0Engine()
            facts = mem0.search_facts(user_prompt, top_k=3)
            if facts:
                lines.append("\n## 📌 Relevant Long-Term Memory Facts (768D Mem0)")
                for ft in facts:
                    fact_str = ft.get("fact") or ft.get("fact_text") or str(ft)
                    lines.append(f"- {fact_str}")
                lines.append("")
        except Exception:
            pass

    # 3. Recent Git / Subagent Traces
    if invocation_num == 0:
        try:
            from vazus_core.memory.db import get_db_connection
            with get_db_connection(read_only=True) as conn:
                traces = conn.execute("""
                    SELECT summary, created_at FROM subagent_memory_traces
                    ORDER BY rowid DESC LIMIT 3
                """).fetchall()
                if traces:
                    lines.append("\n## 🔀 Recent System Commits & Traces")
                    for t in traces:
                        lines.append(f"- [{t[1]}] {t[0]}")
                    lines.append("")
        except Exception:
            pass

    return "\n".join(lines)


def build_skills_injection(skills: list) -> str:
    """Formats loaded skills into a readable injection block."""
    if not skills:
        return ""

    lines = ["\n## 🧠 Auto-Loaded Skills (DynamicSkillDispatcher)\n"]
    lines.append(f"The following {len(skills)} skill(s) were auto-matched to your task:\n")

    for sk in skills:
        score_pct = int(sk["score"] * 100)
        lines.append(f"---\n### ⚡ [{sk['name']}] (relevance: {score_pct}%)\n*Path*: `{sk['path']}`\n")
        lines.append(sk["content"])
        lines.append("\n")

    return "\n".join(lines)


def main():
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            print(json.dumps({}))
            return

        hook_data = json.loads(raw)
        try:
            debug_path = "C:/vazus/logs/pre_invocation_raw.jsonl"
            with open(debug_path, "a", encoding="utf-8") as df:
                df.write(json.dumps({"keys": list(hook_data.keys()), "raw": raw[:500]}, ensure_ascii=False) + "\n")
        except Exception:
            pass

        invocation_num = hook_data.get("invocationNum", 0)
        user_prompt = extract_user_prompt(hook_data)
        matched_skills = auto_select_skills(user_prompt)
        skills_block = build_skills_injection(matched_skills)
        memory_block = auto_retrieve_memory(user_prompt, invocation_num)

        # Base message: MCP instructions on turn 0, empty string on subsequent turns
        full_message = MCP_INSTRUCTIONS if invocation_num == 0 else ""
        if memory_block:
            full_message += memory_block
        if skills_block:
            full_message += skills_block

        # --- HUD visibility: log what we're injecting ---
        injected_skills = [{"name": s["name"], "score_pct": int(s["score"] * 100)} for s in matched_skills]
        write_hud_event("PreInvocation", {
            "turn": invocation_num,
            "prompt_preview": user_prompt[:80] if user_prompt else "",
            "mcp_injected": invocation_num == 0,
            "skills_injected": injected_skills,
            "memory_injected": bool(memory_block),
            "total_chars": len(full_message),
        })

        if full_message.strip():
            result = {
                "injectSteps": [
                    {"ephemeralMessage": full_message}
                ]
            }
        else:
            result = {}

        print(json.dumps(result))

    except Exception:
        # Hooks must NEVER crash the agent
        print(json.dumps({}))


if __name__ == "__main__":
    main()
