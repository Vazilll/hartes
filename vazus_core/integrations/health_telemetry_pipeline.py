"""
vazus_core.health_telemetry_pipeline — Bridge to services/health_agent/health_telemetry_pipeline.py.
"""
import sys
from pathlib import Path

_HA_DIR = str(Path("C:/vazus/services/health_agent").resolve())
if _HA_DIR not in sys.path:
    sys.path.insert(0, _HA_DIR)

try:
    import services.health_agent.health_telemetry_pipeline as _sh_htp
except ImportError as e:
    raise ImportError(
        f"vazus_core.health_telemetry_pipeline: cannot import from "
        f"'C:/vazus/services/health_agent/health_telemetry_pipeline.py'. "
        f"Ensure the file exists and has no syntax errors. Original error: {e}"
    ) from e

DB_PATH = _sh_htp.DB_PATH
fetch_and_save_fitness_data = _sh_htp.fetch_and_save_fitness_data

class VazusHealthPipelineManager(_sh_htp.VazusHealthPipelineManager):
    def sync_all_google_fit_metrics(self, days_back=4):
        _sh_htp.DB_PATH = getattr(sys.modules[__name__], "DB_PATH", _sh_htp.DB_PATH)
        _sh_htp.fetch_and_save_fitness_data = getattr(sys.modules[__name__], "fetch_and_save_fitness_data", _sh_htp.fetch_and_save_fitness_data)
        self.db_path = getattr(self, "db_path", None) or getattr(sys.modules[__name__], "DB_PATH", _sh_htp.DB_PATH)
        return super().sync_all_google_fit_metrics(days_back=days_back)

    def execute_pipeline(self):
        _sh_htp.DB_PATH = getattr(sys.modules[__name__], "DB_PATH", _sh_htp.DB_PATH)
        _sh_htp.fetch_and_save_fitness_data = getattr(sys.modules[__name__], "fetch_and_save_fitness_data", _sh_htp.fetch_and_save_fitness_data)
        self.db_path = getattr(self, "db_path", None) or getattr(sys.modules[__name__], "DB_PATH", _sh_htp.DB_PATH)
        return super().execute_pipeline()

__all__ = [
    "DB_PATH",
    "VazusHealthPipelineManager",
    "fetch_and_save_fitness_data",
]

