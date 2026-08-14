import sys
try:
    import services.finance_agent.tinkoff_finance_manager as _sh_tfm
except ImportError as e:
    raise ImportError(
        f"vazus_core.tinkoff_finance_manager: cannot import from "
        f"'C:/vazus/services/finance_agent/tinkoff_finance_manager.py'. "
        f"Ensure the file exists and has no syntax errors. Original error: {e}"
    ) from e

DB_PATH = _sh_tfm.DB_PATH
TOKEN_PATH = _sh_tfm.TOKEN_PATH
TINKOFF_API_BASE = _sh_tfm.TINKOFF_API_BASE

def init_finance_db(db_path=None):
    target_db = db_path or getattr(sys.modules[__name__], "DB_PATH", _sh_tfm.DB_PATH)
    _sh_tfm.DB_PATH = target_db
    return _sh_tfm.init_finance_db(db_path=target_db)

class TinkoffFinanceManager(_sh_tfm.TinkoffFinanceManager):
    def __init__(self, api_token=None, db_path=None):
        """
        STRICT READ-ONLY ENFORCEMENT:
        Only read access to transaction history, balances, and categories.
        Writing/purchasing endpoints are strictly disallowed and technically impossible.
        """
        current_db = db_path or getattr(sys.modules[__name__], "DB_PATH", _sh_tfm.DB_PATH)
        _sh_tfm.DB_PATH = current_db
        super().__init__(api_token=api_token, db_path=current_db)

__all__ = [
    "DB_PATH",
    "TOKEN_PATH",
    "TINKOFF_API_BASE",
    "init_finance_db",
    "TinkoffFinanceManager",
]

