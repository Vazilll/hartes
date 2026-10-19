"""vazus_core — Personal Digital Twin Core (Memory, Finance, Health, MIREA Integrations)."""

import sys
import importlib
import importlib.abc
import importlib.util

_SUBPKG_MAP = {
    "config": "engine", "exceptions": "engine", "utils": "engine", "scheduler": "engine",
    "embeddings": "memory", "organic_memory_bridge": "memory", "db": "memory",
    "mem0_memory_engine": "memory", "knowledge_engine": "memory",
    "multimodal_resolver": "memory", "reactive_parameters": "memory",
    "jules_client": "workers",
    "telegram_indexer": "integrations", "telegram_notifier": "integrations",
    "tinkoff_finance_manager": "integrations", "freelance_npd_engine": "integrations",
    "self_employed_order_hunter": "integrations", "autonomous_freelance_engine": "integrations",
    "ble_mi_scale_scanner": "integrations", "health_telemetry_pipeline": "integrations",
    "google_super_sync_engine": "integrations", "google_sync_hub": "integrations",
    "google_multimodal_vision": "integrations", "mirea_student_manager": "integrations",
    "mirea_exporter": "integrations", "cognitive_tutor_engine": "integrations",
    "notebook_synthesis_engine": "integrations", "tts_podcast_generator": "integrations",
    "statement_parser": "integrations", "gemma_local_processor": "integrations",
    "repo_indexer": "integrations", "tui_preview_renderer": "integrations",
    "skill_author": "integrations", "google_sync_engine": "integrations",
    "grpc_health_servicer": "integrations", "nutrition_tracker": "integrations",
    "langgraph_health_workflow": "integrations",
}


class _VazusCoreAliasLoader(importlib.abc.InspectLoader):
    def __init__(self, target_fullname, target_spec=None):
        self.target_fullname = target_fullname
        self.target_spec = target_spec

    def create_module(self, spec):
        _ = spec
        return None

    def exec_module(self, module):
        target_mod = importlib.import_module(self.target_fullname)
        sys.modules[module.__name__] = target_mod
        module.__dict__.update(target_mod.__dict__)


class _VazusCoreSubpackageFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        _ = (path, target)
        if fullname.startswith("vazus_core."):
            parts = fullname.split(".")
            if len(parts) == 2 and parts[1] in _SUBPKG_MAP:
                target_fullname = f"vazus_core.{_SUBPKG_MAP[parts[1]]}.{parts[1]}"
                target_spec = importlib.util.find_spec(target_fullname)
                if target_spec is not None:
                    return importlib.machinery.ModuleSpec(
                        name=fullname,
                        loader=_VazusCoreAliasLoader(target_fullname, target_spec),
                        origin=target_spec.origin,
                    )
        return None


if not any(isinstance(x, _VazusCoreSubpackageFinder) for x in sys.meta_path):
    sys.meta_path.insert(0, _VazusCoreSubpackageFinder())

from vazus_core.memory.db import get_db_connection
from vazus_core.engine.exceptions import (
    VazusBaseException,
    DatabaseLockError,
    EmbeddingError,
    SessionRequiredError,
    ScheduleFetchError,
)
from vazus_core import engine, memory, workers, integrations

__version__ = "4.1.0"
__all__ = [
    "get_db_connection",
    "VazusBaseException",
    "DatabaseLockError",
    "EmbeddingError",
    "SessionRequiredError",
    "ScheduleFetchError",
    "engine",
    "memory",
    "workers",
    "integrations",
]
