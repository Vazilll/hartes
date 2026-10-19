import sys
try:
    import services.health_agent.grpc_health_servicer as _sh_ghs
except ImportError as e:
    raise ImportError(
        f"vazus_core.grpc_health_servicer: cannot import from "
        f"'/home/tarhes/Проекты/vazus/services/health_agent/grpc_health_servicer.py'. "
        f"Ensure the file exists and has no syntax errors. Original error: {e}"
    ) from e

DB_PATH = _sh_ghs.DB_PATH
serve_grpc_health_server = _sh_ghs.serve_grpc_health_server
fetch_and_save_fitness_data = _sh_ghs.fetch_and_save_fitness_data

class AsyncHealthTelemetryServicer(_sh_ghs.AsyncHealthTelemetryServicer):
    async def SyncGoogleFitData(self, request, context):
        _sh_ghs.DB_PATH = getattr(sys.modules[__name__], "DB_PATH", _sh_ghs.DB_PATH)
        _sh_ghs.fetch_and_save_fitness_data = getattr(sys.modules[__name__], "fetch_and_save_fitness_data", _sh_ghs.fetch_and_save_fitness_data)
        return await super().SyncGoogleFitData(request, context)

    def _log_grpc_sync_to_db(self, readiness, steps, active_min):
        _sh_ghs.DB_PATH = getattr(sys.modules[__name__], "DB_PATH", _sh_ghs.DB_PATH)
        return super()._log_grpc_sync_to_db(readiness, steps, active_min)

__all__ = [
    "DB_PATH",
    "AsyncHealthTelemetryServicer",
    "serve_grpc_health_server",
    "fetch_and_save_fitness_data",
]

