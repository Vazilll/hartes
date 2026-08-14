"""
vazus_core.autonomous_freelance_engine — Bridge to services/finance_agent/autonomous_freelance_engine.py.
"""
try:
    from services.finance_agent.autonomous_freelance_engine import (
        AutonomousFreelanceEngine,
        init_freelance_db,
        DB_PATH,
    )
except ImportError as e:
    raise ImportError(
        f"vazus_core.autonomous_freelance_engine: cannot import from "
        f"'C:/vazus/services/finance_agent/autonomous_freelance_engine.py'. "
        f"Ensure the file exists and has no syntax errors. Original error: {e}"
    ) from e

__all__ = [
    "AutonomousFreelanceEngine",
    "init_freelance_db",
    "DB_PATH",
]

