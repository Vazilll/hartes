"""
vazus_core.self_employed_order_hunter — Backward Compatibility Re-export Alias.
Redirects to unified vazus_core.freelance_npd_engine module.
"""


from vazus_core.integrations.freelance_npd_engine import (
    SelfEmployedManager,
    OrderHunterEngine,
    init_self_employed_db,
    DB_PATH as DEFAULT_DB_PATH,
)

# Module-level variable for monkeypatching support
DB_PATH = DEFAULT_DB_PATH

__all__ = [
    "SelfEmployedManager",
    "OrderHunterEngine",
    "init_self_employed_db",
    "DB_PATH",
]
