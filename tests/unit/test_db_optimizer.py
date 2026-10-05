import sqlite3
import pytest
from pathlib import Path
from vazus_core.maintenance.db_optimizer import optimize_database


def test_optimize_database_nonexistent():
    res = optimize_database(db_path="nonexistent_db_12345.db")
    assert res["status"] == "skipped"
    assert res["reason"] == "db_not_found"


def test_optimize_database_valid_sqlite(tmp_path):
    test_db = tmp_path / "test_opt.db"
    conn = sqlite3.connect(str(test_db))
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, name TEXT);")
    conn.execute("INSERT INTO sample (name) VALUES ('alpha'), ('beta');")
    conn.commit()
    conn.close()

    res = optimize_database(db_path=test_db)
    assert res["status"] == "ok"
    assert res["optimized"] is True
    assert res["shrunk"] is True
    assert "elapsed_ms" in res
    assert res["elapsed_ms"] >= 0.0
    assert "checkpoint" in res
