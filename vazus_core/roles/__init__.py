"""
vazus_core.roles — Canonical Subagent Roles and Personas for Vazus OS and Google Antigravity.
"""

from vazus_core.roles.system_personas import (
    PLANNER_PERSONA_PROMPT,
    RLM_CODER_PERSONA_PROMPT,
    VERIFIER_WORKER_PERSONA_PROMPT,
    AUTO_REVIEWER_PERSONA_PROMPT,
    HEALTH_AGENT_PERSONA_PROMPT,
    FINANCE_AGENT_PERSONA_PROMPT,
    get_persona_prompt,
    get_subagent_definition_spec,
    get_native_invoke_spec,
    ALL_ROLES,
)

__all__ = [
    "PLANNER_PERSONA_PROMPT",
    "RLM_CODER_PERSONA_PROMPT",
    "VERIFIER_WORKER_PERSONA_PROMPT",
    "AUTO_REVIEWER_PERSONA_PROMPT",
    "HEALTH_AGENT_PERSONA_PROMPT",
    "FINANCE_AGENT_PERSONA_PROMPT",
    "get_persona_prompt",
    "get_subagent_definition_spec",
    "get_native_invoke_spec",
    "ALL_ROLES",
]
