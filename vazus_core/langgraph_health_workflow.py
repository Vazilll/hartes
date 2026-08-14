import sys
from pathlib import Path

_HA_DIR = str(Path("C:/vazus/services/health_agent").resolve())
if _HA_DIR not in sys.path:
    sys.path.insert(0, _HA_DIR)

try:
    import services.health_agent.langgraph_health_workflow as _sh_lgw
except ImportError as e:
    raise ImportError(
        f"vazus_core.langgraph_health_workflow: cannot import from "
        f"'C:/vazus/services/health_agent/langgraph_health_workflow.py'. "
        f"Ensure the file exists and has no syntax errors. Original error: {e}"
    ) from e

DB_PATH = _sh_lgw.DB_PATH
fetch_and_save_fitness_data = _sh_lgw.fetch_and_save_fitness_data
GoogleGemmaLocalEngine = _sh_lgw.GoogleGemmaLocalEngine

class LangGraphHealthMultiAgentWorkflow(_sh_lgw.LangGraphHealthMultiAgentWorkflow):
    def agent_1_telemetry_ingestor(self, *args, **kwargs):
        _sh_lgw.DB_PATH = getattr(sys.modules[__name__], "DB_PATH", _sh_lgw.DB_PATH)
        _sh_lgw.fetch_and_save_fitness_data = getattr(sys.modules[__name__], "fetch_and_save_fitness_data", _sh_lgw.fetch_and_save_fitness_data)
        _sh_lgw.GoogleGemmaLocalEngine = getattr(sys.modules[__name__], "GoogleGemmaLocalEngine", _sh_lgw.GoogleGemmaLocalEngine)
        self.db_path = getattr(self, "db_path", None) or getattr(sys.modules[__name__], "DB_PATH", _sh_lgw.DB_PATH)
        return super().agent_1_telemetry_ingestor(*args, **kwargs)

    def execute_full_workflow(self, *args, **kwargs):
        _sh_lgw.DB_PATH = getattr(sys.modules[__name__], "DB_PATH", _sh_lgw.DB_PATH)
        _sh_lgw.fetch_and_save_fitness_data = getattr(sys.modules[__name__], "fetch_and_save_fitness_data", _sh_lgw.fetch_and_save_fitness_data)
        _sh_lgw.GoogleGemmaLocalEngine = getattr(sys.modules[__name__], "GoogleGemmaLocalEngine", _sh_lgw.GoogleGemmaLocalEngine)
        self.db_path = getattr(self, "db_path", None) or getattr(sys.modules[__name__], "DB_PATH", _sh_lgw.DB_PATH)
        return super().execute_full_workflow(*args, **kwargs)

__all__ = [
    "DB_PATH",
    "LangGraphHealthMultiAgentWorkflow",
    "fetch_and_save_fitness_data",
    "GoogleGemmaLocalEngine",
]

