#!/usr/bin/env bash
# ==============================================================================
# Vazus SuperGraph OS — Container Entrypoint & Lifecycle Controller
# ==============================================================================
set -e

echo "=========================================================="
echo "  🚀 Starting Vazus SuperGraph OS (Production Container)  "
echo "=========================================================="

VAZUS_ROOT="${VAZUS_ROOT:-/app}"
VAZUS_DB_PATH="${VAZUS_DB_PATH:-$VAZUS_ROOT/services/memory/vazus.db}"
PORT="${PORT:-8000}"
HOST="${HOST:-0.0.0.0}"

# 1. Ensure required runtime directories exist
mkdir -p "$VAZUS_ROOT/data/logs" "$VAZUS_ROOT/data/cache" "$VAZUS_ROOT/services/memory"

# 2. Database schema initialization & integrity check
if [ ! -f "$VAZUS_DB_PATH" ]; then
    echo "[Vazus Init] Canonical database not found at $VAZUS_DB_PATH."
    echo "[Vazus Init] Initializing fresh database schemas..."
    python -c "
import sys
from pathlib import Path
from vazus_core.memory.db import get_db_connection, init_db_schemas

db_path = '$VAZUS_DB_PATH'
Path(db_path).parent.mkdir(parents=True, exist_ok=True)
conn = get_db_connection(db_path)
init_db_schemas(conn, db_path=db_path)
conn.close()
print('[Vazus Init] Schema initialization complete.')
"
else
    echo "[Vazus Init] Verifying database integrity at $VAZUS_DB_PATH..."
    python -c "
import sqlite3
try:
    conn = sqlite3.connect('$VAZUS_DB_PATH', timeout=10.0)
    cur = conn.cursor()
    cur.execute('PRAGMA integrity_check;')
    status = cur.fetchone()[0]
    conn.execute('PRAGMA wal_checkpoint(PASSIVE);')
    conn.close()
    print(f'[Vazus Init] Database integrity verified: {status}')
except Exception as e:
    print(f'[Vazus Init] Warning: Database check encountered: {e}', file=sys.stderr)
"
fi

# 3. Verify Formal Verification Substrate (Z3 SMT)
python -c "
import z3
print(f'[Vazus Init] SMT Verification Substrate active. Z3 version: {z3.get_version_string()}')
"

# 4. Graceful Shutdown Signal Trap (WAL Checkpoint & Flush)
shutdown_handler() {
    echo ""
    echo "[Vazus Shutdown] Caught termination signal (SIGTERM/SIGINT)."
    echo "[Vazus Shutdown] Checkpointing SQLite WAL and flushing state..."
    python -c "
import sqlite3
try:
    conn = sqlite3.connect('$VAZUS_DB_PATH', timeout=5.0)
    conn.execute('PRAGMA wal_checkpoint(TRUNCATE);')
    conn.close()
    print('[Vazus Shutdown] Database checkpoint complete.')
except Exception as e:
    print(f'[Vazus Shutdown] Checkpoint warning: {e}')
" 2>/dev/null || true
    echo "[Vazus Shutdown] Bye!"
    exit 0
}

trap shutdown_handler SIGTERM SIGINT

# 5. Hand off to container process
echo "[Vazus Init] Executing container command: $@"
exec "$@"
