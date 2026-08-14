"""
vazus_core.self_employed_order_hunter — Bridge to services/finance_agent/self_employed_order_hunter.py.
"""
try:
    from services.finance_agent.self_employed_order_hunter import (
        SelfEmployedManager,
        OrderHunterEngine,
        init_self_employed_db,
        DB_PATH,
    )
except ImportError as e:
    raise ImportError(
        f"vazus_core.self_employed_order_hunter: cannot import from "
        f"'C:/vazus/services/finance_agent/self_employed_order_hunter.py'. "
        f"Ensure the file exists and has no syntax errors. Original error: {e}"
    ) from e

__all__ = [
    "SelfEmployedManager",
    "OrderHunterEngine",
    "init_self_employed_db",
    "DB_PATH",
]

