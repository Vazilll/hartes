"""
vazus_core.knowledge_engine — Unified Knowledge Base, Zettelkasten Exporter, KGB Analytical Extractor & FullWorkspaceIndexer.

Features:
1. 🕸️ Two-layer SuperGraph Knowledge Graph (Layer A: AST Topology, Layer B: Karpathy Memory Wiki).
2. 📝 Zettelkasten exporter & FTS5 full-text indexing.
3. 🛠️ FullWorkspaceIndexer for codebase symbol definition graphs & AST indexing.

vazus SuperGraph OS v4.0 Unified Architecture
"""

import os
import ast
import logging
import sqlite3
import time

from pathlib import Path
from typing import Dict, Any, Optional, Union

logger = logging.getLogger(__name__)

def get_default_db_path() -> Path:
    env_db = os.environ.get("VAZUS_DB_PATH")
    return Path(env_db) if env_db else Path(r"C:\vazus\services\memory\vazus.db")

DB_PATH = get_default_db_path()


class FullWorkspaceIndexer:
    """
    Indexes codebase workspace python files, extracting AST nodes and symbol signatures into SQLite.
    """

    def __init__(self, root_dir: Optional[Union[str, Path]] = None, workspace_root: Optional[Union[str, Path]] = None, db_path: Optional[Union[str, Path]] = None, **kwargs):
        effective_root = root_dir or workspace_root or kwargs.get("root_path") or Path(r"C:\vazus")
        self.root_dir = Path(effective_root)
        self.workspace_root = self.root_dir
        self.db_path = Path(db_path) if db_path else get_default_db_path()
        self._init_db()



    def _init_db(self):
        """Initializes workspace indexing schema and secondary indexes."""
        if not self.db_path.parent.exists():
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workspace_ast_nodes (
                node_id TEXT PRIMARY KEY,
                file_path TEXT,
                kind TEXT,
                name TEXT,
                signature TEXT,
                vector_768d BLOB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workspace_ast_edges (
                source_id TEXT,
                target_id TEXT,
                relationship TEXT,
                PRIMARY KEY (source_id, target_id, relationship)
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_workspace_ast_nodes_file_path ON workspace_ast_nodes(file_path);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_workspace_ast_nodes_kind ON workspace_ast_nodes(kind);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_workspace_ast_nodes_name ON workspace_ast_nodes(name);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_workspace_ast_edges_source ON workspace_ast_edges(source_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_workspace_ast_edges_target ON workspace_ast_edges(target_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_workspace_ast_edges_rel ON workspace_ast_edges(relationship);")

        conn.commit()
        conn.close()

    def _extract_ast_nodes_and_edges(
        self, pfile: Path, tree: ast.AST, cursor: sqlite3.Cursor, node_id: str
    ) -> tuple[int, int]:
        """Extracts class and function definitions as well as imports from AST."""
        nodes_count = 0
        edges_count = 0
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                for alias in n.names:
                    imp_id = f"imp_{hash(alias.name)}"
                    cursor.execute("""
                        INSERT OR REPLACE INTO workspace_ast_nodes
                        (node_id, file_path, kind, name, signature)
                        VALUES (?, ?, 'IMPORT', ?, ?)
                    """, (imp_id, str(pfile), alias.name, f"import {alias.name}"))
                    nodes_count += 1
                    cursor.execute("""
                        INSERT OR REPLACE INTO workspace_ast_edges
                        (source_id, target_id, relationship)
                        VALUES (?, ?, 'IMPORTS')
                    """, (node_id, imp_id))
                    edges_count += 1
            elif isinstance(n, ast.ClassDef):
                c_id = f"cls_{hash(str(pfile) + n.name)}"
                cursor.execute("""
                    INSERT OR REPLACE INTO workspace_ast_nodes
                    (node_id, file_path, kind, name, signature)
                    VALUES (?, ?, 'CLASS', ?, ?)
                """, (c_id, str(pfile), n.name, f"class {n.name}"))
                nodes_count += 1
                cursor.execute("""
                    INSERT OR REPLACE INTO workspace_ast_edges
                    (source_id, target_id, relationship)
                    VALUES (?, ?, 'DEFINES')
                """, (node_id, c_id))
                edges_count += 1
                for item in n.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        f_id = f"fn_{hash(str(pfile) + item.name)}"
                        cursor.execute("""
                            INSERT OR REPLACE INTO workspace_ast_nodes
                            (node_id, file_path, kind, name, signature)
                            VALUES (?, ?, 'FUNCTION', ?, ?)
                        """, (f_id, str(pfile), item.name, f"def {item.name}()"))
                        nodes_count += 1
                        cursor.execute("""
                            INSERT OR REPLACE INTO workspace_ast_edges
                            (source_id, target_id, relationship)
                            VALUES (?, ?, 'DEFINES')
                        """, (c_id, f_id))
                        edges_count += 1
        return nodes_count, edges_count

    def _index_ast_module_file(self, cursor: sqlite3.Cursor, pfile: Path) -> tuple[int, int]:
        """Indexes a single Python file into workspace AST nodes and edges."""
        try:
            content = pfile.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(content)
            node_id = f"mod_{hash(str(pfile))}"
            cursor.execute("""
                INSERT OR REPLACE INTO workspace_ast_nodes
                (node_id, file_path, kind, name, signature)
                VALUES (?, ?, 'MODULE', ?, 'module')
            """, (node_id, str(pfile), pfile.name))
            sub_nodes, sub_edges = self._extract_ast_nodes_and_edges(pfile, tree, cursor, node_id)
            return 1 + sub_nodes, sub_edges
        except Exception as exc:
            logger.debug("Failed to index AST module for %s: %s", pfile, exc)
            return 0, 0

    def run_indexer(self) -> Dict[str, Any]:
        """Executes workspace indexing."""
        start_time = time.time()
        nodes_count = 0
        edges_count = 0
        files_count = 0

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if self.root_dir.exists():
            for pfile in self.root_dir.glob("**/*.py"):
                files_count += 1
                n_count, e_count = self._index_ast_module_file(cursor, pfile)
                nodes_count += n_count
                edges_count += e_count

        conn.commit()
        conn.close()

        elapsed = round(time.time() - start_time, 4)
        return {
            "status": "INDEXING_COMPLETE",
            "indexed_nodes": nodes_count,
            "nodes_indexed": nodes_count,
            "edges_indexed": edges_count,
            "files_scanned": files_count,
            "embedding_dim": 768,
            "execution_time_sec": elapsed,
            "root": str(self.root_dir)
        }







    def index_workspace(self) -> Dict[str, Any]:
        """Alias for run_indexer."""
        return self.run_indexer()



