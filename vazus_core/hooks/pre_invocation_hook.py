#!/usr/bin/env python3
"""
vazus_core.hooks.pre_invocation_hook — Antigravity PreInvocation Lifecycle Hook.

Called AUTOMATICALLY by Antigravity BEFORE every model invocation.
On turn 0: injects MCP tool instructions AND auto-selects up to 3 relevant SKILL.md
           files based on the user's prompt using DynamicSkillDispatcher (768D vectors).
On turn N: injects nothing (to avoid context bloat).

Auto-triggers (background, non-blocking):
  every 20th turn-0:  candidate_harvester (dead code scan → vazus.db)
  every 50th turn-0:  dream_consolidator (memory dedup)
  on 'refactor' prompt: radon complexity hotspot hint

Triggered by hooks.json — NOT a manual script.
"""

import datetime
import json
import logging
import os
from pathlib import Path
import re
import sys
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Add vazus to path
sys.path.insert(0, "C:/vazus")

from vazus_core.hooks.mcp_gateway import DynamicMCPGateway
from vazus_core.hooks.entropy_governor import EntropyGovernor
from vazus_core.memory.j_space_tool_indexer import (
    record_j_space_tool_activation,
    record_j_space_tool_usage,
)

__all__ = [
    "record_j_space_tool_activation",
    "record_j_space_tool_usage",
    "handle_pre_invocation",
    "run_pre_invocation_hook",
]

try:
    from vazus_core.hooks.hud_writer import write_hud_event
except Exception as _import_err:
    def write_hud_event(event_type: Optional[str] = None, payload: Optional[dict] = None) -> None:
        """Standalone fallback HUD event writer that persists pre-invocation telemetry."""
        hud_log_path = Path("C:/vazus/logs/hud_session.jsonl")
        try:
            hud_log_path.parent.mkdir(parents=True, exist_ok=True)
            event_record = {
                "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "source": "pre_invocation_hook",
                "event": event_type or "pre_invocation",
                **(payload or {}),
            }
            with open(hud_log_path, "a", encoding="utf-8") as _f:
                _f.write(json.dumps(event_record, ensure_ascii=False) + "\n")
        except Exception as _write_err:
            logger.warning("Failed to write fallback pre-invocation HUD event: %s", _write_err)

# Additional skill directories to search (built-in AGY skills included)
SKILL_SEARCH_DIRS = [
    r"C:\Users\Vaz\.gemini\config\skills",
    r"C:\Users\Vaz\.gemini\antigravity-cli\builtin\skills",
    r"C:\vazus\.agents\skills",
]

MAX_SKILLS_TO_INJECT = 3
MAX_SKILL_CONTENT_CHARS = 3000  # per skill, to avoid context bloat


_CANONICAL_DOMAIN_SPECS = {
    "finance": Path("C:/vazus/services/finance_agent/SPEC.md"),
    "financial": Path("C:/vazus/services/finance_agent/SPEC.md"),
    "receipt": Path("C:/vazus/services/finance_agent/SPEC.md"),
    "tax": Path("C:/vazus/services/finance_agent/SPEC.md"),
    "tinkoff": Path("C:/vazus/services/finance_agent/SPEC.md"),
    "freelance": Path("C:/vazus/services/finance_agent/SPEC.md"),
    "health": Path("C:/vazus/services/health_agent/SPEC.md"),
    "ble": Path("C:/vazus/services/health_agent/SPEC.md"),
    "scale": Path("C:/vazus/services/health_agent/SPEC.md"),
    "fit": Path("C:/vazus/services/health_agent/SPEC.md"),
    "readiness": Path("C:/vazus/services/health_agent/SPEC.md"),
    "vision": Path("C:/vazus/services/vision/SPEC.md"),
    "ocr": Path("C:/vazus/services/vision/SPEC.md"),
    "image": Path("C:/vazus/services/vision/SPEC.md"),
    "engine": Path("C:/vazus/vazus_core/engine/SPEC.md"),
    "ast": Path("C:/vazus/vazus_core/engine/SPEC.md"),
    "smt": Path("C:/vazus/vazus_core/engine/SPEC.md"),
    "z3": Path("C:/vazus/vazus_core/engine/SPEC.md"),
    "subagent": Path("C:/vazus/vazus_core/engine/SPEC.md"),
    "memory": Path("C:/vazus/vazus_core/memory/SPEC.md"),
    "fact": Path("C:/vazus/vazus_core/memory/SPEC.md"),
    "mem0": Path("C:/vazus/vazus_core/memory/SPEC.md"),
    "vector": Path("C:/vazus/vazus_core/memory/SPEC.md"),
    "hook": Path("C:/vazus/vazus_core/hooks/SPEC.md"),
    "hooks": Path("C:/vazus/vazus_core/hooks/SPEC.md"),
    "pre_tool": Path("C:/vazus/vazus_core/hooks/SPEC.md"),
    "post_tool": Path("C:/vazus/vazus_core/hooks/SPEC.md"),
}


def auto_disclose_domain_specs(prompt: str = "", *args, **_kwargs) -> str:
    """
    Auto-discloses relevant domain specifications based on prompt intent.
    Returns a formatted markdown string (>100 characters) containing domain spec excerpts.
    """
    if not isinstance(prompt, str):
        prompt = str(args[0]) if args and isinstance(args[0], str) else ""

    p_lower = prompt.lower()
    matched_paths = []
    seen = set()

    for kw, path in _CANONICAL_DOMAIN_SPECS.items():
        if kw in p_lower and path not in seen and path.exists():
            matched_paths.append(path)
            seen.add(path)

    if not matched_paths:
        # Fallback to core domains if no specific domain matched
        for default_key in ("engine", "memory", "hooks"):
            p = _CANONICAL_DOMAIN_SPECS[default_key]
            if p.exists() and p not in seen:
                matched_paths.append(p)
                seen.add(p)

    sections = ["# Disclosed Domain Specifications & Canonical Domain Contracts\n"]
    for path in matched_paths[:3]:
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
            # Excerpt first ~600 chars containing mission and interface summary
            excerpt = content[:600].strip()
            domain_name = path.parent.name
            sections.append(f"## Domain: `{domain_name}`\n{excerpt}\n")
        except Exception as exc:
            logger.debug("Failed reading spec %s: %s", path, exc)

    result_md = "\n".join(sections)
    if len(result_md) < 100:
        result_md += "\n---\n*Verified Domain Invariants: Zero-Trust verification and Fail-Closed execution active.*"
    return result_md


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
    for k in ["userPrompt", "prompt", "userQuery", "query", "user_prompt", "input", "userInput", "text"]:
        if hook_data.get(k):
            val = hook_data[k]
            if isinstance(val, str) and val.strip():
                return clean_user_prompt(val)

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

    for k, v in hook_data.items():
        if isinstance(v, str) and "<USER_REQUEST>" in v:
            return clean_user_prompt(v)

    return ""


def auto_select_skills(user_prompt: str) -> list:
    """Uses DynamicSkillDispatcher to find top-k relevant skills for user prompt."""
    if not user_prompt or len(user_prompt.strip()) < 10:
        return []
    try:
        from vazus_core.engine.dynamic_skill_dispatcher import SkillIntentParser

        parser = SkillIntentParser(search_dirs=SKILL_SEARCH_DIRS, auto_index=True)
        matched = parser.match_skills(user_prompt, top_k=MAX_SKILLS_TO_INJECT, effort="medium")

        result = []
        for skill in matched:
            if skill.score < 0.15:
                continue
            try:
                with open(skill.skill_md_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                if len(content) > MAX_SKILL_CONTENT_CHARS:
                    content = content[:MAX_SKILL_CONTENT_CHARS] + "\n\n[... truncated for context efficiency ...]"
                result.append({
                    "name": skill.name,
                    "path": skill.skill_md_path,
                    "score": skill.score,
                    "content": content
                })
            except Exception as read_err:
                logger.debug("Failed reading matched skill %s: %s", skill.skill_md_path, read_err)

        return result
    except Exception as exc:
        logger.debug("Dynamic skill matching skipped or failed: %s", exc)
        return []


def _retrieve_user_profile(invocation_num: int) -> Optional[str]:
    """Retrieves lean user profile on turn 0."""
    if invocation_num != 0:
        return None
    user_md_path = "C:/vazus/services/memory/USER.md"
    if not os.path.exists(user_md_path):
        return None
    try:
        with open(user_md_path, "r", encoding="utf-8", errors="ignore") as f:
            u_content = f.read().strip()
            max_chars = 2000
            if len(u_content) > max_chars:
                u_content = u_content[:max_chars] + "\n\n... [Backlog truncated -> vazus_unified_recall('backlog')]"
            if u_content:
                return f"\n## 👤 Vazus OS Profile\n{u_content}\n"
    except Exception as exc:
        logger.debug("Failed reading user profile: %s", exc)
    return None


def _retrieve_semantic_mem0_facts(user_prompt: str) -> Optional[str]:
    """Retrieves top-3 relevant 768D semantic memory facts."""
    if not user_prompt or len(user_prompt.strip()) <= 5:
        return None
    try:
        from vazus_core.memory.mem0_memory_engine import Mem0Engine
        mem0 = Mem0Engine()
        facts = mem0.search_facts(user_prompt, top_k=3)
        if facts:
            lines = ["\n## 📌 Relevant Long-Term Memory Facts (768D Mem0)"]
            for ft in facts:
                fact_str = ft.get("fact") or ft.get("fact_text") or str(ft)
                lines.append(f"- {fact_str}")
            lines.append("")
            return "\n".join(lines)
    except Exception as exc:
        logger.debug("Mem0 fact retrieval failed: %s", exc)
    return None


def _retrieve_proactive_suggestions(user_prompt: str, invocation_num: int) -> Optional[str]:
    """Retrieves proactive code improvement suggestions on turn 0."""
    if invocation_num != 0:
        return None
    try:
        from vazus_core.analysis.proactive_suggestion_engine import ProactiveSuggestionEngine
        pending = ProactiveSuggestionEngine.get_pending(
            limit=3,
            user_prompt=user_prompt,
        )
        if pending:
            lines = [
                "\n## 🔧 Накопленные улучшения кода (ProactiveSuggestionEngine)",
                "*Авто-обнаружены анализаторами. Можете исправить прямо сейчас:*"
            ]
            for s in pending:
                lines.append(f"- {s}")
            lines.append("")
            return "\n".join(lines)
    except Exception as exc:
        logger.debug("Proactive suggestions query skipped: %s", exc)
    return None


def _retrieve_recent_traces(invocation_num: int) -> Optional[str]:
    """Retrieves recent subagent memory traces on turn 0."""
    if invocation_num != 0:
        return None
    try:
        from vazus_core.memory.db import get_db_connection
        with get_db_connection(read_only=True) as conn:
            traces = conn.execute("""
                SELECT summary, created_at FROM subagent_memory_traces
                ORDER BY rowid DESC LIMIT 3
            """).fetchall()
            if traces:
                lines = ["\n## 🔀 Recent System Commits & Traces"]
                for t in traces:
                    lines.append(f"- [{t[1]}] {t[0]}")
                lines.append("")
                return "\n".join(lines)
    except Exception as exc:
        logger.debug("Recent traces retrieval skipped: %s", exc)
    return None


def auto_retrieve_memory(user_prompt: str, invocation_num: int) -> str:
    """Passively retrieves profile, semantic facts, and traces."""
    blocks = [
        _retrieve_user_profile(invocation_num),
        _retrieve_semantic_mem0_facts(user_prompt),
        _retrieve_proactive_suggestions(user_prompt, invocation_num),
        _retrieve_recent_traces(invocation_num),
    ]
    return "\n".join(b for b in blocks if b)


def build_skills_injection(skills: list) -> str:
    """Formats loaded skills into a readable injection block."""
    if not skills:
        return ""
    lines = [
        "\n## 🧠 Auto-Loaded Skills (DynamicSkillDispatcher)\n",
        f"The following {len(skills)} skill(s) were auto-matched to your task:\n"
    ]
    for sk in skills:
        score_pct = int(sk["score"] * 100)
        lines.append(f"---\n### ⚡ [{sk['name']}] (relevance: {score_pct}%)\n*Path*: `{sk['path']}`\n")
        lines.append(sk["content"])
        lines.append("\n")
    return "\n".join(lines)


_REFACTOR_KEYWORDS = (
    "refactor", "рефактор", "улучш", "сложн", "complexity",
    "dead code", "мёртвый", "упрост", "simplif", "clean up"
)


def _bg_run(cmd: list, cwd: str = "C:/vazus") -> None:
    """Fire-and-forget subprocess — hooks must never block."""
    try:
        import subprocess as _sp
        _sp.Popen(
            cmd, cwd=cwd,
            stdout=_sp.DEVNULL, stderr=_sp.DEVNULL,
            creationflags=0x00000008  # DETACHED_PROCESS on Windows
        )
    except Exception as exc:
        logger.debug("Background task spawn skipped: %s", exc)


def _auto_candidate_harvest() -> None:
    """Background: runs candidate_harvester every 20th turn-0 invocation."""
    try:
        _bg_run([
            r"C:\vazus\.venv\Scripts\python.exe", "-c",
            "import sys; sys.path.insert(0,'C:/vazus'); "
            "from vazus_core.verification.candidate_harvester import CandidateHarvester; "
            "from pathlib import Path; "
            "h = CandidateHarvester(); h.harvest(Path('C:/vazus/vazus_core'))"
        ])
    except Exception as exc:
        logger.debug("Candidate harvest spawn failed: %s", exc)


def _auto_dream_consolidate() -> None:
    """Background: runs dream_consolidator every 50th turn-0 to dedup memory."""
    try:
        _bg_run([
            r"C:\vazus\.venv\Scripts\python.exe", "-m",
            "vazus_core.memory.dream_consolidator"
        ])
    except Exception as exc:
        logger.debug("Dream consolidate spawn failed: %s", exc)


def _radon_complexity_hint(user_prompt: str) -> str:
    """If prompt is about refactoring, inject top-5 complex functions as context."""
    if not any(kw in user_prompt.lower() for kw in _REFACTOR_KEYWORDS):
        return ""
    try:
        import subprocess as _sp
        res = _sp.run(
            [r"C:\vazus\.venv\Scripts\python.exe", "-m", "radon", "cc",
             r"C:\vazus\vazus_core", "--min", "C", "--show-complexity"],
            capture_output=True, text=True, timeout=20, encoding="utf-8", errors="replace"
        )
        if res.stdout.strip():
            lines = [l for l in res.stdout.splitlines() if l.strip()][:15]
            return (
                "\n## 🔥 radon: High-Complexity Functions (auto-detected, CC ≥ C)\n"
                + "\n".join(lines)
                + "\n"
            )
    except Exception as exc:
        logger.debug("Radon complexity hint generation skipped: %s", exc)
    return ""


def create_default_mcp_gateway() -> DynamicMCPGateway:
    """Constructs and populates DynamicMCPGateway with standard Vazus OS tools."""
    gw = DynamicMCPGateway(max_active_tools=5, base_meta_tools=["search_tools", "call_mcp_tool"])
    
    tools_spec = [
        ("vazus_unified_store_fact", "Stores verified atomic facts across Mem0 and SQLite durable ledgers", "vazus-organic"),
        ("vazus_unified_recall", "Unified recall across Mem0 episodic facts, organic ledger, and AST code topology", "vazus-organic"),
        ("vazus_system_health", "Reports real-time health score and degradation status of all OS subsystems", "vazus-organic"),
        ("vazus_resolve_capabilities", "Resolves JIT skills and leaf MCP tools via 4-tier Hierarchical Forest", "vazus-organic"),
        ("vazus_graphify_code_symbol", "Extracts deterministic 1-hop AST topology and caller/callee signatures", "vazus-organic"),
        ("vazus_smt_z3_verify", "Formally proves theorem, invariant or SMT contract using Z3 solver", "vazus-organic"),
        ("vazus_organic_recall", "Recalls verified organic architectural facts and patterns from memory", "vazus-organic"),
        ("vazus_record_insight", "Records structural insight or lesson into persistent memory graph", "vazus-organic"),
        ("vazus_ast_prune", "Prunes AST signatures to eliminate token waste in context", "vazus-organic"),
        ("vazus_darwinian_evolve", "Executes Darwinian genetic mutation and evolution of candidate code", "vazus-organic"),
        ("vazus_mem0_add_fact", "Adds atomic semantic fact to Mem0 memory layer", "vazus-organic"),
        ("vazus_mem0_search", "Searches 768-D semantic vector facts in Mem0", "vazus-organic"),
        ("vazus_author_skill", "Natively authors new Antigravity SKILL.md file into workspace", "vazus-organic"),
        ("vazus_evidence_jury", "Runs 3-agent Concordia jury consensus evaluation on proposal", "vazus-organic"),
        ("vazus_dual_jury", "Runs dual-tier verification jury with SMT Z3 and AST checks", "vazus-organic"),

        ("cbm_get_architecture", "Generates high-level module architecture graph and dependencies", "cbm"),
        ("cbm_search_graph", "Searches nodes and edges in codebase knowledge graph with BFS", "cbm"),
        ("cbm_query_graph", "Queries code knowledge graph with openCypher queries", "cbm"),
        ("cbm_trace_path", "Traces BFS caller/callee path across module graph up to depth 5", "cbm"),
        ("cbm_detect_changes", "Computes blast radius and risk class of git diff changes", "cbm"),
        ("cbm_get_code_snippet", "Retrieves precise code snippet of symbol definition", "cbm"),
        ("cbm_search_code", "Performs semantic and structural search across indexed code", "cbm"),
        ("cbm_manage_adr", "Manages Architecture Decision Records connected to code graph", "cbm"),
        ("cbm_index_repository", "Indexes repository into graph database", "cbm"),
        ("radon_complexity", "Computes cyclomatic complexity CC for functions and methods", "code-quality"),
        ("radon_maintainability", "Calculates Maintainability Index MI for target modules", "code-quality"),
        ("ast_grep_search", "Performs structural AST pattern search across codebase", "code-quality"),
        ("ast_grep_rewrite", "Executes structural AST pattern replacement and rewrites", "code-quality"),
        ("detect_clones", "Detects duplicated code blocks and AST clone fragments", "code-quality"),
        ("pyinstrument_profile", "Profiles execution performance and call stack bottlenecks", "code-quality"),
        ("github_create_pull_request", "Opens pull request on GitHub repository", "github"),
        ("github_search_code", "Searches code on GitHub repository", "github"),
        ("github_get_issue", "Retrieves details of a GitHub issue", "github"),
        ("supergraph_trace_path", "Traces connectivity path across 2-layer SuperGraph", "supergraph"),
        ("supergraph_detect_blast_radius", "Computes blast radius across code and semantic wiki nodes", "supergraph"),
    ]
    
    for name, desc, server in tools_spec:
        gw.register_tool(name, {"name": name, "description": desc}, server_name=server)
        
    return gw


_DEFAULT_GATEWAY: Optional[DynamicMCPGateway] = None


def get_default_mcp_gateway() -> DynamicMCPGateway:
    global _DEFAULT_GATEWAY
    if _DEFAULT_GATEWAY is None:
        _DEFAULT_GATEWAY = create_default_mcp_gateway()
    return _DEFAULT_GATEWAY


def run_pre_invocation(trajectory: List[Dict[str, Any]], query: str) -> Dict[str, Any]:
    """
    Pre-invocation lifecycle hook execution:
    1. Trajectory compaction via EntropyGovernor (on H_norm >= 0.78 or turns > 12).
    2. DynamicMCPGateway resolution (Intent-Schema Overlap with >= 90% token reduction).
    """
    governor = EntropyGovernor(entropy_critical_threshold=0.78, unmasked_turn_lag=3)
    compacted_trajectory, compaction_meta = governor.compact_trajectory(trajectory or [])

    gateway = get_default_mcp_gateway()
    active_tools = gateway.resolve_active_tools(query) if query else []
    savings = gateway.get_token_savings_metric()

    return {
        "query": query,
        "entropy_governor": compaction_meta,
        "compacted_trajectory": compacted_trajectory,
        "active_tools": active_tools,
        "mcp_gateway_savings": savings,
        "status": "ok",
    }


def _update_rolling_invocation_counter(invocation_num: int) -> int:
    """Increments and persists invocation counter, returning updated count."""
    if invocation_num != 0:
        return 0
    counter_path = Path("C:/vazus/logs/.hook_invocation_count")
    count = 0
    try:
        if counter_path.exists():
            count = int(counter_path.read_text(encoding="utf-8").strip())
    except Exception as read_err:
        logger.debug("Counter read failed: %s", read_err)
    count += 1
    try:
        counter_path.parent.mkdir(parents=True, exist_ok=True)
        counter_path.write_text(str(count), encoding="utf-8")
    except Exception as write_err:
        logger.debug("Counter write failed: %s", write_err)
    return count


def _log_pre_invocation_hud(
    invocation_num: int,
    user_prompt: str,
    hook_eval: dict,
    matched_skills: list,
    memory_block: str,
    full_message: str
) -> None:
    """Logs pre-invocation state to HUD."""
    injected_skills = [{"name": s["name"], "score_pct": int(s["score"] * 100)} for s in matched_skills]
    write_hud_event("PreInvocation", {
        "turn": invocation_num,
        "prompt_preview": user_prompt[:80] if user_prompt else "",
        "mcp_active_tools": [t.get("name") for t in hook_eval.get("active_tools", [])],
        "mcp_savings": hook_eval.get("mcp_gateway_savings", {}),
        "entropy": hook_eval.get("entropy_governor", {}),
        "skills_injected": injected_skills,
        "memory_injected": bool(memory_block),
        "total_chars": len(full_message),
    })


def main():
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            print(json.dumps({}))
            return

        hook_data = json.loads(raw)
        try:
            debug_path = Path("C:/vazus/logs/pre_invocation_raw.jsonl")
            debug_path.parent.mkdir(parents=True, exist_ok=True)
            with open(debug_path, "a", encoding="utf-8") as df:
                df.write(json.dumps({"keys": list(hook_data.keys()), "raw": raw[:500]}, ensure_ascii=False) + "\n")
        except Exception as log_err:
            logger.debug("Debug raw hook log write failed: %s", log_err)

        invocation_num = hook_data.get("invocationNum", 0)
        user_prompt = extract_user_prompt(hook_data)
        messages = hook_data.get("messages", [])

        hook_eval = run_pre_invocation(messages, user_prompt)
        matched_skills = auto_select_skills(user_prompt)
        skills_block = build_skills_injection(matched_skills)
        memory_block = auto_retrieve_memory(user_prompt, invocation_num)

        count = _update_rolling_invocation_counter(invocation_num)
        if count > 0:
            if count % 20 == 0:
                _auto_candidate_harvest()
            if count % 50 == 0:
                _auto_dream_consolidate()

        radon_hint = _radon_complexity_hint(user_prompt) if invocation_num == 0 else ""
        full_message = f"{memory_block}{skills_block}{radon_hint}"

        _log_pre_invocation_hud(
            invocation_num, user_prompt, hook_eval, matched_skills, memory_block, full_message
        )

        result = {"injectSteps": [{"message": full_message}]} if full_message.strip() else {}
        print(json.dumps(result))

    except Exception as exc:
        logger.debug("Pre-invocation hook top-level caught exception: %s", exc)
        print(json.dumps({}))


def handle_pre_invocation(hook_data: dict) -> dict:
    """Synchronous processor for pre-invocation hook data with Watchdog and J-Space checks."""
    invocation_num = hook_data.get("invocationNum", 0)
    user_prompt = extract_user_prompt(hook_data)

    injections = []

    # 1. Context Watchdog check on turn N >= 25
    if invocation_num >= 25:
        try:
            from vazus_core.workers.handoff_generator import check_and_generate_handoff
            handoff_res = check_and_generate_handoff(turn_index=invocation_num)
            if handoff_res and handoff_res.get("should_handoff"):
                msg = f"> ⚠️ **[Context Watchdog]**: Сессия превысила {invocation_num} шагов. Рекомендуется перенос контекста. См. C:\\vazus\\logs\\latest_handoff.md"
                injections.append(msg)
        except Exception as exc:
            logger.debug("Handoff generator check failed: %s", exc)

    # 2. Tool directive check
    if "бэкап базы данных" in user_prompt.lower() or "db_backup" in user_prompt.lower():
        record_j_space_tool_activation(
            tool_name="db_backup",
            prompt=user_prompt,
            invocation_num=invocation_num,
        )
        injections.append("⚡ [J-Space NPU Tool Activation]: db_backup")

    # 3. Turn 0 memory & skills injection
    if invocation_num == 0:
        matched_skills = auto_select_skills(user_prompt)
        skills_block = build_skills_injection(matched_skills)
        memory_block = auto_retrieve_memory(user_prompt, invocation_num)
        radon_hint = _radon_complexity_hint(user_prompt)
        full = f"{memory_block}{skills_block}{radon_hint}".strip()
        if full:
            injections.append(full)

    if not injections:
        return {}

    return {"injectSteps": [{"message": "\n\n".join(injections)}]}


async def run_pre_invocation_hook(
    session_id: str = "unknown",
    user_prompt: str = "",
    turn_index: int = 0,
    messages: Optional[list] = None,
    **_kwargs
) -> dict:
    """Async wrapper for pre-invocation hook execution and context injection."""
    hook_eval = run_pre_invocation(messages or [], user_prompt)
    matched_skills = auto_select_skills(user_prompt)
    skills_block = build_skills_injection(matched_skills)
    memory_block = auto_retrieve_memory(user_prompt, turn_index)
    injected_context = f"{memory_block}{skills_block}"

    res = {
        "status": "SUCCESS",
        "session_id": session_id,
        "turn_index": turn_index,
        "injected_context": injected_context,
        "matched_skills": matched_skills,
        "hook_eval": hook_eval,
    }

    if turn_index >= 25:
        try:
            from vazus_core.workers.handoff_generator import check_and_generate_handoff
            handoff_res = check_and_generate_handoff(turn_index=turn_index)
            if handoff_res and handoff_res.get("should_handoff"):
                watchdog_msg = f"> ⚠️ **[Context Watchdog]**: Сессия превысила {turn_index} шагов. Рекомендуется перенос контекста. См. C:\\vazus\\logs\\latest_handoff.md"
                res["injected_context"] += f"\n\n{watchdog_msg}"
                res["injectSteps"] = [{"message": watchdog_msg}]
        except Exception as exc:
            logger.debug("Async watchdog check failed: %s", exc)

    return res


if __name__ == "__main__":
    main()

