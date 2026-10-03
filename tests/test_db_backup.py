import os
import sqlite3
import pytest
from pathlib import Path
from vazus_core.workers.db_backup import run_backup, get_backup_status

def test_db_backup_execution(tmp_path):
    # Create a dummy sqlite db
    test_db = tmp_path / "test_vazus.db"
    conn = sqlite3.connect(str(test_db))
    conn.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY, val TEXT)")
    conn.execute("INSERT INTO test_table (val) VALUES ('hello')")
    conn.commit()
    conn.close()

    backup_dir = tmp_path / "backups"
    result = run_backup(
        db_path=test_db,
        backup_dir=backup_dir,
        max_backups=3,
        verify=True,
        sync_gdrive=False,
    )

    assert result["success"] is True
    assert result["integrity_ok"] is True
    assert os.path.exists(result["backup_path"])

    # Check status
    status = get_backup_status(backup_dir=backup_dir)
    assert status["total_backups"] == 1
    assert status["latest"] == result["backup_path"]
