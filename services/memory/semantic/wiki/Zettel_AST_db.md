---
id: Zettel_AST_db
title: AST Pruned Skeleton - db.py
date: 2026-10-05
domain: ast_code
tags: [ast, code, ast_pruner, db]
status: VERIFIED
sources: [ASTPruner, SuperGraph OS]
---

# AST Pruned Skeleton for `db.py`

## Core Metrics
- **Total AST Nodes**: 3004
- **Pruned AST Nodes**: 448
- **Token Reduction**: 89.82%
- **Syntax Valid**: `True`

## Pruned Signatures
```python
"""vazus_core.db - Unified Thread-Safe Database Access Layer"""

import os

import sqlite3

import logging

import threading

import numpy as np

try:
    import sqlite_vec
except ImportError:
    sqlite_vec = None

from pathlib import Path

from typing import Optional

logger = logging.getLogger("vazus_core.db")

DEFAULT_VAZUS_DB: str = _default_db_path()

class SharedConnectionProxy:
    """Thread-local SQLite connection proxy that prevents C-extension re-loading memory leaks."""
    def __init__(self, conn: sqlite3.Connection, cache_key: Optional[tuple]=None):
        ...
    def close(self):
        ...
    def force_close(self):
        ...
    def __enter__(self):
        return self._conn.__enter__()
    def __exit__(self, exc_type, exc_val, exc_tb):
        return self._conn.__exit__(exc_type, exc_val, exc_tb)
    def __getattr__(self, name):
        return getattr(self._conn, name)

def init_db_schemas(conn: sqlite3.Connection | SharedConnectionProxy, db_path: str | Path | None=None) -> None:
    """Ensures organic_insights, kg_nodes, kg_edges tables and associated indexes"""
    ...

def get_db_connection(
    db_path: str | Path | None=None,
    timeout: float=60.0,
    read_only: bool=False,
    use_cache: bool=True
) -> sqlite3.Connection | SharedConnectionProxy:
    """Creates or retrieves a WAL-enabled SQLite connection with busy_timeout."""
    return SharedConnectionProxy(raw_conn)

def close_all_thread_connections() -> None:
    """Closes and clears all thread-local cached connection handles in the current thread."""
    ...

def pack_vector_f32(vec: list) -> bytes:
    """Packs list of floats into raw binary float32 BLOB (3,072 bytes for 768D vector)."""
    return np.array(vec, dtype=np.float32).tobytes()

def unpack_vector_f32(blob: bytes) -> list:
    """Unpacks raw binary float32 BLOB back to list of floats."""
    return np.frombuffer(blob, dtype=np.float32).tolist()
```

## Related Notes & Wikilinks
- [[Research_SuperGraph_Memory_Wiki_and_AST|SuperGraph Memory & AST Integration]]
- [[RLM_Code_Task_Refactor_AST_pruner|AST Pruner Refactor Task]]
- [[Zettel_AST_db|Self Reference]]
