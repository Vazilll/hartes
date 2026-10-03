import sqlite3
import pytest
from pathlib import Path
from vazus_core.hooks.stop_hook import check_pending_verification

DB_PATH = Path(r"C:\vazus\services\memory\vazus.db")

def test_organic_insights_columns():
    """Verify organic_insights column names match expectations."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cols = [c[1] for c in cur.execute("PRAGMA table_info(organic_insights)").fetchall()]
    conn.close()
    assert "timestamp" in cols
    assert "category" in cols
    assert "insight" in cols

def test_check_pending_verification_executes_without_error():
    """Verify check_pending_verification runs without sqlite operational error."""
    is_pending, reason = check_pending_verification()
    assert isinstance(is_pending, bool)
    assert isinstance(reason, str)
