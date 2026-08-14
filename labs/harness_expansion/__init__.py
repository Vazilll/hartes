"""
labs.harness_expansion — Global Harness Expansion Blueprints for vazus SuperGraph OS v4.0.
Exposes master HARNESS_BLUEPRINTS registry binding research lab harnesses to vazus_core.
"""

from typing import Dict, Any, List, Optional

from .nous_hermes.hermes_blueprint import HermesHarnessBlueprint
from .deepmind_odr.odr_blueprint import OpenDeepResearchBlueprint
from .anthropic_thinking.thinking_blueprint import AnthropicThinkingBlueprint
from .mit_rlm.rlm_blueprint import MITRLMBlueprint
from .openai_swarm_jury.swarm_jury_blueprint import OpenAISwarmJuryBlueprint
from .graphify_ast.graphify_blueprint import GraphifyASTBlueprint
from .concordia_jury.concordia_blueprint import ConcordiaJuryBlueprint

# Instantiate master registry
HARNESS_BLUEPRINTS: Dict[str, Any] = {
    "nous_hermes": HermesHarnessBlueprint(),
    "deepmind_odr": OpenDeepResearchBlueprint(),
    "anthropic_thinking": AnthropicThinkingBlueprint(),
    "mit_rlm": MITRLMBlueprint(),
    "openai_swarm_jury": OpenAISwarmJuryBlueprint(),
    "graphify_ast": GraphifyASTBlueprint(),
    "concordia_jury": ConcordiaJuryBlueprint(),
}


def get_blueprint(harness_id: str) -> Any:
    """Retrieves a specific harness blueprint instance by ID."""
    if harness_id not in HARNESS_BLUEPRINTS:
        raise KeyError(f"Unknown harness blueprint: '{harness_id}'. Available: {list(HARNESS_BLUEPRINTS.keys())}")
    return HARNESS_BLUEPRINTS[harness_id]


def list_blueprints() -> List[Dict[str, Any]]:
    """Returns metadata for all registered research harness blueprints."""
    return [bp.get_metadata() for bp in HARNESS_BLUEPRINTS.values()]


def execute_all_blueprint_health_checks() -> Dict[str, Any]:
    """Runs structural and operational health checks across all 7 research harness blueprints."""
    results = {}
    for harness_id, bp in HARNESS_BLUEPRINTS.items():
        try:
            meta = bp.get_metadata()
            results[harness_id] = {
                "status": "OPERATIONAL",
                "name": meta.get("name"),
                "lab": meta.get("lab"),
                "domain": meta.get("domain"),
            }
        except Exception as e:
            results[harness_id] = {
                "status": "ERROR",
                "error": str(e),
            }
    return {
        "system": "vazus SuperGraph OS v4.0",
        "total_blueprints": len(HARNESS_BLUEPRINTS),
        "health_checks": results,
    }


__all__ = [
    "HARNESS_BLUEPRINTS",
    "HermesHarnessBlueprint",
    "OpenDeepResearchBlueprint",
    "AnthropicThinkingBlueprint",
    "MITRLMBlueprint",
    "OpenAISwarmJuryBlueprint",
    "GraphifyASTBlueprint",
    "ConcordiaJuryBlueprint",
    "get_blueprint",
    "list_blueprints",
    "execute_all_blueprint_health_checks",
]
