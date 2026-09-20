"""
vazus_core — Unified SuperGraph OS Core Engine v4.0.0

Structured Subpackages:
- engine: Core async runtime, subagent framework, model selector, orchestrators.
- verification: SMT Z3 verifiers, Concordia Jury, AST pruner, git provenance.
- memory: Auto improver, vector embeddings, AVX-512 cosine similarity, organic memory DB.
- workers: REPL engine, self-healing REPL, subagent bridges, sidecars.
- integrations: Services, Telegram, Finance, Health, MIREA, Google sync.
"""

import sys
import importlib
import importlib.abc
import importlib.util

_SUBPKG_MAP = {
    # engine
    "subagent_framework": "engine", "model_selector": "engine", "reasoning_effort_controller": "engine",
    "circuit_breaker": "engine", "llm_client": "engine", "config": "engine", "exceptions": "engine",
    "utils": "engine", "supergraph_master_orchestrator": "engine", "supergraph_linker": "engine",
    "dynamic_skill_dispatcher": "engine", "unified_reasoning_pipeline": "engine", "ast_repo_mapper": "engine",
    "operator_dag": "engine", "silicon_orchestrator": "engine", "gemma4_npu_engine": "engine",
    "graphify_engine": "engine", "global_j_workspace": "engine",
    # verification
    "smt_z3_verifier": "verification", "concordia_jury": "verification", "sota2027_jury": "verification",
    "ast_pruner": "verification", "git_provenance": "verification", "safety_guardrail": "verification",
    "rollback_guardrail": "verification", "empirical_benchmark": "verification", "precommit_gate": "verification",
    "worktree_sandbox": "verification",
    # memory
    "auto_improver": "memory", "embeddings": "memory", "avx512_cosine": "memory",
    "organic_memory_bridge": "memory", "db": "memory",
    "mem0_memory_engine": "memory", "knowledge_engine": "memory", "multimodal_knowledge": "memory",
    "multimodal_resolver": "memory", "dialogue_persister": "memory",
    "zettelkasten_exporter": "memory", "j_space_vector_index": "memory",
    "dream_consolidator": "memory", "agent_memory_bank": "memory",
    "magma_graph": "memory", "whitelist_manager": "memory",
    "unified_memory_gateway": "memory",
    # workers
    "repl_engine": "workers", "self_healing_repl": "workers", "subagent_auto_trigger": "workers",
    "subagent_reflexion": "workers", "agent_handoff": "workers", "agent_system_bridge": "workers",
    "background_review_hook": "workers", "daemon_sidecar": "workers", "system_daemon": "workers",
    "jules_client": "workers", "subagent_verifier_bridge": "workers",
    "subagent_rlm_bridge": "workers", "subagent_research_bridge": "workers", "subprocess_repl": "workers",
    # evolution
    "darwinian_evolver": "evolution", "synaptic_evolver": "evolution",
    # integrations
    "telegram_indexer": "integrations", "telegram_notifier": "integrations", "tinkoff_finance_manager": "integrations",
    "freelance_npd_engine": "integrations", "self_employed_order_hunter": "integrations",
    "autonomous_freelance_engine": "integrations", "ble_mi_scale_scanner": "integrations",
    "health_telemetry_pipeline": "integrations", "google_super_sync_engine": "integrations",
    "google_sync_hub": "integrations", "google_multimodal_vision": "integrations",
    "mirea_student_manager": "integrations", "mirea_exporter": "integrations",
    "cognitive_tutor_engine": "integrations", "notebook_synthesis_engine": "integrations",
    "tts_podcast_generator": "integrations", "kgb_analytical_extractor": "integrations",
    "statement_parser": "integrations", "storm_interviewer": "integrations",
    "gemma_local_processor": "integrations", "repo_indexer": "integrations",
    "cli_pixel_visualizer": "integrations", "tui_preview_renderer": "integrations",
    "agy_customizations_hud": "integrations", "skill_author": "integrations",
    "socratic_partner": "integrations"
}

class _VazusCoreAliasLoader(importlib.abc.InspectLoader):
    def __init__(self, target_fullname, target_spec=None):
        self.target_fullname = target_fullname
        self.target_spec = target_spec

    def create_module(self, spec):
        _ = spec  # importlib hook signature; kept for interface compliance
        return None

    def exec_module(self, module):
        target_mod = importlib.import_module(self.target_fullname)
        sys.modules[module.__name__] = target_mod
        module.__dict__.update(target_mod.__dict__)

    def get_code(self, fullname):
        if self.target_spec and hasattr(self.target_spec.loader, "get_code"):
            return self.target_spec.loader.get_code(self.target_fullname)
        return None

    def get_source(self, fullname):
        if self.target_spec and hasattr(self.target_spec.loader, "get_source"):
            return self.target_spec.loader.get_source(self.target_fullname)
        return None

    def is_package(self, fullname):
        if self.target_spec and hasattr(self.target_spec.loader, "is_package"):
            return self.target_spec.loader.is_package(self.target_fullname)
        return False


class _VazusCoreSubpackageFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        _ = (path, target)  # importlib hook signature; kept for interface compliance
        if fullname.startswith("vazus_core."):
            parts = fullname.split(".")
            if len(parts) == 2:
                mod_name = parts[1]
                if mod_name in _SUBPKG_MAP:
                    target_fullname = f"vazus_core.{_SUBPKG_MAP[mod_name]}.{mod_name}"
                    target_spec = importlib.util.find_spec(target_fullname)
                    if target_spec is not None:
                        return importlib.machinery.ModuleSpec(
                            name=fullname,
                            loader=_VazusCoreAliasLoader(target_fullname, target_spec),
                            origin=target_spec.origin
                        )
        return None


if not any(isinstance(x, _VazusCoreSubpackageFinder) for x in sys.meta_path):
    sys.meta_path.insert(0, _VazusCoreSubpackageFinder())

from vazus_core.memory.db import get_db_connection
from vazus_core.verification.ast_pruner import DocstringAndBodyPruner
from vazus_core.engine.supergraph_linker import SuperGraphLinker
from vazus_core.verification.concordia_jury import ConcordiaJury
from vazus_core.engine.unified_reasoning_pipeline import UnifiedReasoningPipeline
from vazus_core.engine.exceptions import (
    VazusBaseException,
    DatabaseLockError,
    EmbeddingError,
    JuryConsensusError,
    SMTVerificationError,
    SubagentExecutionError,
    SessionRequiredError,
    ScheduleFetchError
)

from vazus_core import engine
from vazus_core import verification
from vazus_core import memory
from vazus_core import workers
from vazus_core import integrations

__version__ = "4.0.0"
__all__ = [
    "get_db_connection",
    "DocstringAndBodyPruner",
    "SuperGraphLinker",
    "ConcordiaJury",
    "UnifiedReasoningPipeline",
    "VazusBaseException",
    "DatabaseLockError",
    "EmbeddingError",
    "JuryConsensusError",
    "SMTVerificationError",
    "SubagentExecutionError",
    "SessionRequiredError",
    "ScheduleFetchError",
    "engine",
    "verification",
    "memory",
    "workers",
    "integrations",
]

