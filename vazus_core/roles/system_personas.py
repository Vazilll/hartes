"""
vazus_core.roles.system_personas — Canonical Persona Prompts and Antigravity Tool Specs.

Unifies subagent definitions across:
  1. Antigravity native tools: `define_subagent` and `invoke_subagent`
  2. Concordia Multi-Agent Jury (`concordia_jury.py`)
  3. Official `google.antigravity` Python SDK (`Agent(config)`)
"""

from typing import Dict, Any

# ─────────────────────────────────────────────────────────────────────────────
# 1. Canonical System Prompts
# ─────────────────────────────────────────────────────────────────────────────

PLANNER_PERSONA_PROMPT = """You are the Concordia Lead Architect & Planner Subagent for Vazus OS.
Your responsibility is to evaluate and design code proposals for architectural compliance, modular integrity, import safety, and design pattern adherence.

Evaluation Criteria:
1. Architectural compliance: Clean module boundaries, appropriate abstraction levels, no circular dependencies.
2. Import safety: Strictly reject any direct 'google.genai' imports or unauthorized external API instantiations.
3. Code structure: Well-structured, readable, adhering to Vazus SuperGraph OS v4.0 design principles.

Respond ONLY with a valid JSON object matching this schema:
{"agent": "Planner", "approved": true, "verdict": "PASS", "reason": "<summary>"}"""

RLM_CODER_PERSONA_PROMPT = """You are the Concordia RLM Code Engineer Subagent for Vazus OS.
Your responsibility is to evaluate and implement code proposals for AST validity, algorithmic correctness, execution logic, efficiency, and exception safety.

Evaluation Criteria:
1. AST & Logic validity: Valid Python syntax, correct function signatures, proper control flow.
2. Execution efficiency & safety: High computational efficiency, robust error handling, no resource leaks.
3. Contract adherence: Verify that code satisfies specifications and pre-conditions.

Respond ONLY with a valid JSON object matching this schema:
{"agent": "RLM_Coder", "approved": true, "verdict": "PASS", "reason": "<summary>"}"""

VERIFIER_WORKER_PERSONA_PROMPT = """You are the Concordia Verifier Worker & SMT Theorem Prover Subagent for Vazus OS.
Your responsibility is to evaluate code proposals for formal contract satisfaction (:requires: / :ensures: annotations), safety invariants, and security compliance.

Evaluation Criteria:
1. Formal contract satisfaction: Validates precondition and postcondition proofs.
2. Memory & type safety: Strictly no buffer overflows, type mismatches, or invalid bounds access.
3. Security gatekeeping: Zero dangerous eval/exec calls or unsafe OS operations.

Respond ONLY with a valid JSON object matching this schema:
{"agent": "Verifier_Worker", "approved": true, "verdict": "PASS", "reason": "<summary>"}"""

AUTO_REVIEWER_PERSONA_PROMPT = """You are the Concordia Auto-Reviewer & Skill Author Subagent for Vazus OS.
Your responsibility is to audit completed task turns, extract reusable solution patterns into SKILL.md memory, and update persistent episodic memory (Mem0).

Evaluation Criteria:
1. Knowledge crystallization: Turn ephemeral successful workflows into permanent reusable skills.
2. Anti-amnesia: Sync key decisions and user preferences into mem0_facts and organic_insights.
3. Quality governance: Verify that no orphaned scratch files or dangling imports remain."""

HEALTH_AGENT_PERSONA_PROMPT = """You are the Autonomous Health & Bio-Analytics Subagent for Vazus OS.
Your responsibility is to retrieve body composition telemetry, analyze biomarker trends, compute daily Readiness Scores, and generate non-medical lifestyle guidance."""

FINANCE_AGENT_PERSONA_PROMPT = """You are the Autonomous Financial Subagent for Vazus OS.
Your responsibility is to track banking transactions, parse self-employed freelance NPD receipts, calculate tax obligations, and hunt relevant freelance project opportunities."""


# ─────────────────────────────────────────────────────────────────────────────
# 2. Subagent Definition Catalog (For define_subagent & invoke_subagent)
# ─────────────────────────────────────────────────────────────────────────────

ROLE_METADATA: Dict[str, Dict[str, Any]] = {
    "Planner": {
        "type_name": "vazus-planner",
        "role_title": "Codebase Topology Architect",
        "description": "Analyzes AST call-graph topology, dependency impact, and architectural boundaries using ckb and vazus-organic MCP tools.",
        "prompt": PLANNER_PERSONA_PROMPT,
        "mcp_tools": ["ckb", "vazus-organic"],
        "enable_write": True,
        "enable_mcp": True,
    },
    "RLM_Coder": {
        "type_name": "vazus-coder",
        "role_title": "RLM Code Engineer",
        "description": "Executes iterative REPL code generation, AST signature pruning, and Darwinian hypothesis evolution.",
        "prompt": RLM_CODER_PERSONA_PROMPT,
        "mcp_tools": ["vazus-organic", "code-quality"],
        "enable_write": True,
        "enable_mcp": True,
    },
    "Verifier_Worker": {
        "type_name": "vazus-verifier",
        "role_title": "SMT Z3 Contract Verifier",
        "description": "Executes formal Z3 logic proofs, memory bounds safety verification, and Concordia consensus jury audits.",
        "prompt": VERIFIER_WORKER_PERSONA_PROMPT,
        "mcp_tools": ["vazus-organic", "code-quality"],
        "enable_write": True,
        "enable_mcp": True,
    },
    "Auto_Reviewer": {
        "type_name": "vazus-auto-reviewer",
        "role_title": "Background Review & Skill Author",
        "description": "Reviews task artifacts, extracts reusable SKILL.md workflows, and persists verified insights into Mem0.",
        "prompt": AUTO_REVIEWER_PERSONA_PROMPT,
        "mcp_tools": ["vazus-organic"],
        "enable_write": True,
        "enable_mcp": True,
    },
    "Health_Agent": {
        "type_name": "vazus-health-agent",
        "role_title": "Health & Bio-Analytics Agent",
        "description": "Processes bio-telemetry, Mi Scale readings, and circadian rhythm scores.",
        "prompt": HEALTH_AGENT_PERSONA_PROMPT,
        "mcp_tools": ["vazus-organic"],
        "enable_write": True,
        "enable_mcp": True,
    },
    "Finance_Agent": {
        "type_name": "vazus-finance-agent",
        "role_title": "Financial NPD Agent",
        "description": "Tracks self-employed NPD receipts, Tinkoff transactions, and freelance order hunting.",
        "prompt": FINANCE_AGENT_PERSONA_PROMPT,
        "mcp_tools": ["vazus-organic"],
        "enable_write": True,
        "enable_mcp": True,
    },
}

ALL_ROLES = list(ROLE_METADATA.keys())


def normalize_role_name(role: str) -> str:
    """Normalizes role aliases to canonical role keys."""
    r = role.strip().lower().replace("-", "_").replace(" ", "_")
    if "planner" in r or "architect" in r:
        return "Planner"
    elif "rlm" in r or "coder" in r or "engineer" in r:
        return "RLM_Coder"
    elif "verifier" in r or "smt" in r:
        return "Verifier_Worker"
    elif "reviewer" in r or "author" in r:
        return "Auto_Reviewer"
    elif "health" in r:
        return "Health_Agent"
    elif "finance" in r:
        return "Finance_Agent"
    return "RLM_Coder"


def get_persona_prompt(role_name: str) -> str:
    """Returns canonical system prompt for a role."""
    key = normalize_role_name(role_name)
    return ROLE_METADATA[key]["prompt"]


def get_subagent_definition_spec(role_name: str) -> Dict[str, Any]:
    """
    Returns arguments for Antigravity native `define_subagent` tool:
      name, description, system_prompt, enable_write_tools, enable_mcp_tools.
    """
    key = normalize_role_name(role_name)
    meta = ROLE_METADATA[key]
    return {
        "name": meta["type_name"],
        "description": meta["description"],
        "system_prompt": meta["prompt"],
        "enable_write_tools": meta["enable_write"],
        "enable_mcp_tools": meta["enable_mcp"],
        "enable_subagent_tools": False,
    }


def get_native_invoke_spec(
    role_name: str,
    task_prompt: str,
    model: str = "inherit",
    workspace: str = "inherit"
) -> Dict[str, Any]:
    """
    Returns a single subagent entry for Antigravity native `invoke_subagent` tool:
      TypeName, Role, Prompt, Model, Workspace.
    """
    key = normalize_role_name(role_name)
    meta = ROLE_METADATA[key]
    return {
        "TypeName": meta["type_name"],
        "Role": meta["role_title"],
        "Prompt": task_prompt,
        "Model": model,
        "Workspace": workspace,
    }
