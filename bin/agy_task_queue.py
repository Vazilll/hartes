#!/usr/bin/env python3
"""Agy ↔ Hermes Task Queue Bridge — SQLite-based cross-agent messaging.
Использует существующую таблицу agent_messages в C:\dnts\memory\dnts.db.

Hermes:   INSERT tasks → Agy polls → Agy processes → UPDATE result
Agy:      cron script polls pending, runs sub-agents, writes back
"""

import sqlite3, json, os, sys, datetime, uuid
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

DB_PATH = r"C:\dnts\memory\dnts.db"

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def ensure_schema():
    """Проверяет существование таблицы agent_messages."""
    conn = get_db()
    conn.execute("SELECT 1 FROM agent_messages LIMIT 1")
    conn.close()

# ─── Hermes API ──────────────────────────────────────────────────────

def submit_task(task_id: str, command: str, prompt: str, context: str = "") -> str:
    """Hermes submits a task to Agy."""
    payload = json.dumps({
        "command": command,
        "prompt": prompt,
        "context": context,
        "submitted_at": datetime.datetime.now().isoformat()
    })
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO agent_messages (id, from_id, to_id, content, status) VALUES (?, ?, ?, ?, 'pending')",
        (task_id, 'hermes', 'agy', payload)
    )
    conn.commit()
    conn.close()
    return task_id

def poll_result(task_id: str, timeout: int = 300, interval: int = 5) -> dict:
    """Poll for task completion. Returns {'status': 'completed'|'failed'|'pending', 'result': ..., 'progress': ...}"""
    import time
    conn = get_db()
    deadline = time.time() + timeout
    while time.time() < deadline:
        row = conn.execute(
            "SELECT status, result, progress, content, updated_at FROM agent_messages WHERE id=?",
            (task_id,)
        ).fetchone()
        if row:
            status = row['status']
            if status == 'completed':
                conn.close()
                return {"status": "completed", "result": row['result'], "progress": row['progress']}
            elif status == 'failed':
                conn.close()
                return {"status": "failed", "error": row['result'], "progress": row['progress']}
            elif status == 'running':
                # still running, check progress
                pass
        time.sleep(interval)
    conn.close()
    return {"status": "timeout", "result": None}

def list_pending() -> list:
    """List all pending tasks for Agy."""
    conn = get_db()
    rows = conn.execute(
        "SELECT id, from_id, content, created_at FROM agent_messages WHERE to_id='agy' AND status='pending' ORDER BY created_at ASC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def list_completed(limit: int = 10) -> list:
    """List recently completed tasks."""
    conn = get_db()
    rows = conn.execute(
        "SELECT id, from_id, content, result, created_at FROM agent_messages WHERE status='completed' ORDER BY created_at DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ─── Agy API (for the cron script) ──────────────────────────────────

def claim_task(agent_id: str = 'agy') -> dict | None:
    """Agy claims the next pending task. Atomic UPDATE with status check."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id, from_id, content FROM agent_messages WHERE to_id=? AND status='pending' ORDER BY created_at ASC LIMIT 1",
            (agent_id,)
        ).fetchone()
        if not row:
            return None
        task_id = row['id']
        conn.execute(
            "UPDATE agent_messages SET status='running' WHERE id=? AND status='pending'",
            (task_id,)
        )
        conn.commit()
        # Verify we got it
        updated = conn.execute("SELECT status FROM agent_messages WHERE id=?", (task_id,)).fetchone()
        if updated and updated['status'] == 'running':
            return {"id": row['id'], "from_id": row['from_id'], "content": row['content']}
        return None
    finally:
        conn.close()

def update_progress(task_id: str, progress: str):
    """Agy reports progress."""
    conn = get_db()
    conn.execute(
        "UPDATE agent_messages SET progress=? WHERE id=?",
        (progress, task_id)
    )
    conn.commit()
    conn.close()

def complete_task(task_id: str, result: str):
    """Agy marks task as completed."""
    conn = get_db()
    conn.execute(
        "UPDATE agent_messages SET status='completed', result=? WHERE id=?",
        (result, task_id)
    )
    conn.commit()
    conn.close()

def fail_task(task_id: str, error: str):
    """Agy marks task as failed."""
    conn = get_db()
    conn.execute(
        "UPDATE agent_messages SET status='failed', result=? WHERE id=?",
        (error, task_id)
    )
    conn.commit()
    conn.close()

# ─── CLI ──────────────────────────────────────────────────────────────

if __name__ == '__main__':
    ensure_schema()
    if len(sys.argv) < 2:
        print("Usage:")
        print("  submit <task_id> <command> <prompt> [context]")
        print("  poll <task_id> [timeout=300]")
        print("  list-pending")
        print("  list-completed")
        print("  claim [agent_id=agy]")
        print("  complete <task_id> <result>")
        print("  fail <task_id> <error>")
        print("  progress <task_id> <status>")
        sys.exit(1)

    action = sys.argv[1]
    if action == 'submit':
        task_id = sys.argv[2] if len(sys.argv) > 2 else f"task_{uuid.uuid4().hex[:8]}"
        command = sys.argv[3] if len(sys.argv) > 3 else "research"
        prompt = sys.argv[4] if len(sys.argv) > 4 else ""
        context = sys.argv[5] if len(sys.argv) > 5 else ""
        tid = submit_task(task_id, command, prompt, context)
        print(f"✅ Task submitted: {tid}")
    elif action == 'poll':
        task_id = sys.argv[2]
        timeout = int(sys.argv[3]) if len(sys.argv) > 3 else 300
        result = poll_result(task_id, timeout)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif action == 'list-pending':
        tasks = list_pending()
        print(json.dumps(tasks, ensure_ascii=False, indent=2))
    elif action == 'list-completed':
        tasks = list_completed()
        print(json.dumps(tasks, ensure_ascii=False, indent=2))
    elif action == 'claim':
        agent_id = sys.argv[2] if len(sys.argv) > 2 else 'agy'
        task = claim_task(agent_id)
        if task:
            print(json.dumps(task, ensure_ascii=False, indent=2))
        else:
            print("No pending tasks")
    elif action == 'complete':
        complete_task(sys.argv[2], sys.argv[3])
        print("✅ Task completed")
    elif action == 'fail':
        fail_task(sys.argv[2], sys.argv[3])
        print("❌ Task failed")
    elif action == 'progress':
        update_progress(sys.argv[2], sys.argv[3])
        print("📊 Progress updated")
