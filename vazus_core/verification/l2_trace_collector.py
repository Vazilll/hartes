"""
vazus_core.verification.l2_trace_collector — L2 Production Wiring
Интегрирует viztracer в pre-commit pipeline: записывает runtime trace
тестируемых файлов и сохраняет call-edges в vazus.db telemetry_call_edges.

Вызывается из precommit_gate.py автоматически при VAZUS_L2_TRACE=1.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

# Resolve VAZUS_ROOT
_ROOT = Path(os.getenv("VAZUS_WORKSPACE_DIR", r"C:\vazus"))
_DB = Path(os.getenv("VAZUS_DB_PATH", str(_ROOT / "services" / "memory" / "vazus.db")))
_VENV = _ROOT / ".venv" / "Scripts" / "python.exe"


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB), timeout=15)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS telemetry_call_edges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            caller TEXT NOT NULL,
            callee TEXT NOT NULL,
            source_file TEXT,
            line_no INTEGER,
            run_id TEXT,
            recorded_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS telemetry_function_hits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            func_name TEXT NOT NULL,
            module TEXT,
            hit_count INTEGER DEFAULT 1,
            run_id TEXT,
            recorded_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    return conn


def _exec_viztracer(*cmd_parts: str) -> None:
    """Executes viztracer subprocess in isolated workspace."""
    subprocess.run(
        list(cmd_parts),
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(_ROOT),
        env={**os.environ, "PYTHONPATH": str(_ROOT)},
    )


def _parse_and_persist_trace_events(trace_file: Path, run_id: str) -> tuple[int, int]:
    """Parses JSON trace events and saves call edges and hits into SQLite."""
    edges_written = 0
    hits_written = 0
    with open(trace_file, encoding="utf-8") as tf:
        data = json.load(tf)

    events = data.get("traceEvents", [])
    conn = _get_conn()
    call_stack: list[str] = []
    func_hits: dict[str, int] = {}
    edges: list[tuple[str, str, str, Optional[int]]] = []

    for ev in events:
        if ev.get("ph") == "B":
            name = ev.get("name", "?")
            src = ev.get("args", {}).get("src", "")
            lineno = ev.get("args", {}).get("lineno")
            if call_stack:
                edges.append((call_stack[-1], name, src, lineno))
            call_stack.append(name)
            func_hits[name] = func_hits.get(name, 0) + 1
        elif ev.get("ph") == "E":
            if call_stack:
                call_stack.pop()

    seen_edges: set[tuple[str, str]] = set()
    for caller, callee, src, lineno in edges:
        key = (caller, callee)
        if key not in seen_edges:
            seen_edges.add(key)
            conn.execute(
                "INSERT OR IGNORE INTO telemetry_call_edges (caller, callee, source_file, line_no, run_id) VALUES (?, ?, ?, ?, ?)",
                (caller, callee, src, lineno, run_id),
            )
            edges_written += 1

    for func, count in func_hits.items():
        conn.execute(
            "INSERT INTO telemetry_function_hits (func_name, hit_count, run_id) VALUES (?, ?, ?)", (func, count, run_id)
        )
        hits_written += 1

    conn.commit()
    conn.close()
    return edges_written, hits_written


def collect_trace_for_test(test_path: Path, timeout: int = 60) -> dict:
    """Runs pytest under viztracer and persists call edges into vazus.db."""
    if not _VENV.exists():
        return {"edges": 0, "hits": 0, "run_id": "", "error": "venv not found"}

    run_id = hashlib.md5(str(test_path).encode()).hexdigest()[:12]

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, dir=tempfile.gettempdir()) as f:
        trace_file = Path(f.name)

    try:
        _exec_viztracer(
            str(_VENV),
            "-m",
            "viztracer",
            "--output_file",
            str(trace_file),
            "--tracer_entries",
            "50000",
            "--ignore_frozen",
            "-m",
            "pytest",
            str(test_path),
            "-x",
            "-q",
            "--tb=no",
            "--no-header",
        )
    except subprocess.TimeoutExpired:
        trace_file.unlink(missing_ok=True)
        return {"edges": 0, "hits": 0, "run_id": run_id, "error": "timeout"}
    except Exception as e:
        trace_file.unlink(missing_ok=True)
        return {"edges": 0, "hits": 0, "run_id": run_id, "error": str(e)}

    edges_written = 0
    hits_written = 0
    if trace_file.exists() and trace_file.stat().st_size > 0:
        try:
            edges_written, hits_written = _parse_and_persist_trace_events(trace_file, run_id)
        except Exception as e:
            trace_file.unlink(missing_ok=True)
            return {"edges": 0, "hits": 0, "run_id": run_id, "error": str(e)}

    trace_file.unlink(missing_ok=True)
    return {"edges": edges_written, "hits": hits_written, "run_id": run_id}


def run_l2_for_staged_tests(test_files: list[Path], max_files: int = 5) -> dict:
    """
    Запускает L2 trace collection для первых max_files тест-файлов.
    Используется из precommit_gate.py при VAZUS_L2_TRACE=1.
    Returns summary dict.
    """
    total_edges = 0
    total_hits = 0
    results = []

    for tf in test_files[:max_files]:
        res = collect_trace_for_test(tf, timeout=90)
        results.append({"file": str(tf), **res})
        total_edges += res.get("edges", 0)
        total_hits += res.get("hits", 0)

    return {"total_edges": total_edges, "total_hits": total_hits, "files": results}


if __name__ == "__main__":
    # Quick smoke test: trace tests/test_precommit_gate.py
    test = _ROOT / "tests" / "test_precommit_gate.py"
    if test.exists():
        result = collect_trace_for_test(test, timeout=120)
        print(f"L2 trace result: {result}")
    else:
        print("No test file found for smoke test")
