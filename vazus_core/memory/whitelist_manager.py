"""
vazus_core.memory.whitelist_manager
Layer 5 Component: Adaptive Symbol Whitelist & Anti-Pattern Manager.

Maintains the persistent whitelist of protected symbols that must never be excised
(due to dynamic dispatch, framework entrypoints, reflection, or failed Z3 contracts).
"""

import logging
from typing import Set

from vazus_core.memory.db import DEFAULT_VAZUS_DB, get_db_connection

logger = logging.getLogger("vazus_core.memory")

DEFAULT_PROTECTED_SYMBOLS = {
    "__init__",
    "__call__",
    "__enter__",
    "__exit__",
    "__repr__",
    "__str__",
    "__eq__",
    "__hash__",
    "main",
    "app",
    "handler",
    "lifespan",
    "get_db_connection",
    "init_db_schemas",
}


class WhitelistManager:
    """
    Manages protected symbols and records counterexamples in vazus.db.
    """

    def __init__(self, db_path: str = DEFAULT_VAZUS_DB):
        import os

        self.db_path = db_path if db_path != DEFAULT_VAZUS_DB else os.getenv("VAZUS_DB_PATH", DEFAULT_VAZUS_DB)
        self._init_db_schema()

    def _init_db_schema(self) -> None:
        """Initializes protected_whitelist table in vazus.db."""
        try:
            conn = get_db_connection(self.db_path)
            with conn:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS protected_whitelist (
                        symbol_name TEXT PRIMARY KEY,
                        reason TEXT,
                        source TEXT,
                        created_at REAL
                    );
                """)
                # Pre-populate default symbols
                import time

                now = time.time()
                for sym in DEFAULT_PROTECTED_SYMBOLS:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO protected_whitelist (symbol_name, reason, source, created_at)
                        VALUES (?, 'Built-in protocol / entrypoint', 'system', ?)
                    """,
                        (sym, now),
                    )
        except Exception as e:
            logger.warning(f"Error initializing protected_whitelist schema: {e}")

    def get_whitelist(self) -> Set[str]:
        """Returns all protected symbol names."""
        try:
            conn = get_db_connection(self.db_path)
            cur = conn.cursor()
            cur.execute("SELECT symbol_name FROM protected_whitelist;")
            return {row[0] for row in cur.fetchall()}
        except Exception as e:
            logger.warning(f"Error reading whitelist: {e}")
            return set(DEFAULT_PROTECTED_SYMBOLS)

    def add_to_whitelist(self, symbol_name: str, reason: str, source: str = "reflexion") -> bool:
        """Adds a symbol to the protected whitelist."""
        import time

        try:
            conn = get_db_connection(self.db_path)
            with conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO protected_whitelist (symbol_name, reason, source, created_at)
                    VALUES (?, ?, ?, ?)
                """,
                    (symbol_name, reason, source, time.time()),
                )
            logger.info(f"Added '{symbol_name}' to protected whitelist: {reason}")
            return True
        except Exception as e:
            logger.error(f"Failed to add '{symbol_name}' to whitelist: {e}")
            return False

    def is_protected(self, symbol_name: str) -> bool:
        """Checks if a symbol is in the protected whitelist."""
        if symbol_name.startswith("__") and symbol_name.endswith("__"):
            return True
        whitelist = self.get_whitelist()
        return symbol_name in whitelist
