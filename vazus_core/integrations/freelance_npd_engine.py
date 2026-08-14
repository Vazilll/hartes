"""
vazus_core.freelance_npd_engine — Bridge to services/finance_agent/freelance_npd_engine.py.
"""
try:
    from services.finance_agent.freelance_npd_engine import (
        DB_PATH,
        SelfEmployedManager,
        init_self_employed_db,
        init_freelance_db,
        OrderHunterEngine,
        AutonomousFreelanceEngine,
    )
except ImportError as e:
    raise ImportError(
        f"vazus_core.freelance_npd_engine: cannot import from "
        f"'C:/vazus/services/finance_agent/freelance_npd_engine.py'. "
        f"Ensure the file exists and has no syntax errors. Original error: {e}"
    ) from e

__all__ = [
    "DB_PATH",
    "SelfEmployedManager",
    "init_self_employed_db",
    "init_freelance_db",
    "OrderHunterEngine",
    "AutonomousFreelanceEngine",
]

