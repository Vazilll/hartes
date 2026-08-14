"""
vazus_core.repo_indexer — Native Repository & Codebase Indexer Engine for Vazus OS.

Scans any target codebase directory, extracts AST signatures, docstrings, and markdown notes,
computes 768D vector embeddings via UnifiedEmbeddingManager, and persists nodes & edges
into canonical vazus.db (workspace_ast_nodes, kg_nodes) and SQLite-vec vector storage.
"""

import os
import sys
import json
import sqlite3
import hashlib
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

VAZUS_DIR = Path("C:/vazus")
if str(VAZUS_DIR) not in sys.path:
    sys.path.insert(0, str(VAZUS_DIR))

from vazus_core.embeddings import UnifiedEmbeddingManager
from vazus_core.ast_pruner import ASTPruner

DEFAULT_DB_PATH = Path("C:/vazus/services/memory/vazus.db")
EXCLUDED_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".agents", "dist", "build", "coverage", ".next"}
SUPPORTED_EXTENSIONS = {".py", ".md", ".json", ".ts", ".js", ".sql", ".sh", ".ps1"}


class CodebaseRepositoryIndexer:
    """Indexes source code and documentation into Vazus OS 768D SuperGraph Memory."""

    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self.embedder = UnifiedEmbeddingManager(dimension=768)

    def _init_db(self, conn: sqlite3.Connection):
        """Ensures required tables exist in vazus.db and loads sqlite-vec extension if available."""
        try:
            import sqlite_vec
            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
        except Exception:
            pass

        conn.executescript("""
            CREATE TABLE IF NOT EXISTS workspace_ast_nodes (
                node_id TEXT PRIMARY KEY,
                file_path TEXT,
                kind TEXT,
                name TEXT,
                signature TEXT,
                vector_768d BLOB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS workspace_ast_edges (
                source_id TEXT,
                target_id TEXT,
                relationship TEXT,
                PRIMARY KEY (source_id, target_id, relationship)
            );

            CREATE TABLE IF NOT EXISTS kg_nodes (
                id TEXT PRIMARY KEY,
                name TEXT,
                domain TEXT,
                node_type TEXT,
                description TEXT,
                tags TEXT,
                properties TEXT,
                embedding_json TEXT
            );
        """)
        conn.commit()

    def index_directory(
        self,
        directory_path: str,
        project_name: str = "vazus",
        max_files: int = 500
    ) -> Dict[str, Any]:
        """
        Scans directory_path recursively, parses code AST signatures and docs,
        computes 768D embeddings, and persists them into vazus.db.
        """
        start_time = time.time()
        target_dir = Path(directory_path).resolve()

        if not target_dir.exists() or not target_dir.is_dir():
            return {
                "status": "ERROR",
                "error": f"Directory not found: {directory_path}",
                "indexed_files": 0
            }

        indexed_files = 0
        ast_nodes_created = 0
        kg_nodes_created = 0
        embeddings_generated = 0
        errors = []

        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            self._init_db(conn)
            cursor = conn.cursor()

            for root, dirs, files in os.walk(target_dir):
                # Filter out excluded directories in-place
                dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS and not d.startswith(".")]

                for fname in files:
                    if indexed_files >= max_files:
                        break

                    ext = Path(fname).suffix.lower()
                    if ext not in SUPPORTED_EXTENSIONS:
                        continue

                    fpath = Path(root) / fname
                    rel_path = str(fpath.relative_to(target_dir)).replace("\\", "/")

                    try:
                        with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                            content = f.read()

                        if not content.strip():
                            continue

                        indexed_files += 1

                        if ext == ".py":
                            # Process Python AST signatures
                            try:
                                pruned_code, stats = ASTPruner.prune_code_string(content, docstring_mode="summary")
                                node_id = f"ast:{project_name}:{rel_path}"
                                sig_text = f"File: {rel_path}\nSignatures:\n{pruned_code[:1000]}"
                                emb_vec = self.embedder.embed_query(sig_text)
                                embeddings_generated += 1

                                cursor.execute("""
                                    INSERT OR REPLACE INTO workspace_ast_nodes (node_id, file_path, kind, name, signature, vector_768d)
                                    VALUES (?, ?, ?, ?, ?, ?)
                                """, (node_id, rel_path, "python_file", fname, pruned_code[:2000], json.dumps(emb_vec)))
                                ast_nodes_created += 1

                                cursor.execute("""
                                    INSERT OR REPLACE INTO kg_nodes (id, name, domain, node_type, description, tags, properties, embedding_json)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                                """, (
                                    node_id,
                                    fname,
                                    "codebase",
                                    "python_module",
                                    f"Module {rel_path} ({stats.get('pruned_chars', 0)} chars pruned)",
                                    f"python,code,{project_name}",
                                    json.dumps({"path": rel_path, "stats": stats}),
                                    json.dumps(emb_vec)
                                ))
                                kg_nodes_created += 1
                            except Exception as pe:
                                errors.append(f"{rel_path}: {pe}")

                        elif ext in (".md", ".json", ".sql", ".ts", ".js"):
                            node_id = f"doc:{project_name}:{rel_path}"
                            doc_summary = content[:800]
                            emb_vec = self.embedder.embed_query(f"{fname}\n{doc_summary}")
                            embeddings_generated += 1

                            cursor.execute("""
                                INSERT OR REPLACE INTO kg_nodes (id, name, domain, node_type, description, tags, properties, embedding_json)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                node_id,
                                fname,
                                "documentation",
                                "document",
                                doc_summary,
                                f"docs,{ext[1:]},{project_name}",
                                json.dumps({"path": rel_path, "size": len(content)}),
                                json.dumps(emb_vec)
                            ))
                            kg_nodes_created += 1

                    except Exception as fe:
                        errors.append(f"{rel_path}: {fe}")

            conn.commit()

        elapsed = round(time.time() - start_time, 2)
        return {
            "status": "SUCCESS",
            "directory": str(target_dir),
            "project_name": project_name,
            "indexed_files": indexed_files,
            "ast_nodes_created": ast_nodes_created,
            "kg_nodes_created": kg_nodes_created,
            "embeddings_generated": embeddings_generated,
            "elapsed_seconds": elapsed,
            "db_path": str(self.db_path),
            "errors": errors[:10]
        }


def index_repository(directory_path: str, project_name: str = "vazus", max_files: int = 500) -> Dict[str, Any]:
    """Public helper function for repository indexing."""
    indexer = CodebaseRepositoryIndexer()
    return indexer.index_directory(directory_path, project_name=project_name, max_files=max_files)
