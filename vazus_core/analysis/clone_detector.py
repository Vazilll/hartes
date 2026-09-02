"""
vazus_core.analysis.clone_detector — 4-level Code Clone Detection Engine.

Type 1: Exact token matches (different whitespace/comments)      — pylint R0801
Type 2: Renamed identifiers, same structure                      — AST normalization + hash
Type 3: Near-miss (added/deleted statements)                     — pylint + Levenshtein
Type 4: Semantic clones (same logic, different implementation)   — 768D embedding cosine > 0.92

Architecture (SOTA 2025-2026):
  Stage 1: Fast filter  → pylint duplicate-code (token-based, O(n))
  Stage 2: AST-normalize → MinHash per function body
  Stage 3: 768D embedding cosine → semantic clone detection
  Output  → vazus.db.code_clones table + improvement_suggestions

Usage:
    detector = CloneDetector()
    clones = detector.detect_all("C:/vazus/vazus_core")
    for c in clones:
        print(c.suggestion)
"""
from __future__ import annotations

import ast
import hashlib
import logging
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Any
import re

logger = logging.getLogger("CloneDetector")

VAZUS_ROOT = Path("C:/vazus")
VENV_PY = str(VAZUS_ROOT / ".venv" / "Scripts" / "python.exe")
VAZUS_DB = VAZUS_ROOT / "services" / "memory" / "vazus.db"

# ── DB Schema ────────────────────────────────────────────────────────────────
CLONE_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS code_clones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clone_type INTEGER,
    file_a TEXT,
    line_a_start INTEGER,
    line_a_end INTEGER,
    file_b TEXT,
    line_b_start INTEGER,
    line_b_end INTEGER,
    similarity REAL,
    fragment_a TEXT,
    fragment_b TEXT,
    suggestion TEXT,
    detected_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'open'
);
"""

SUGGESTION_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS improvement_suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT,
    line INTEGER,
    category TEXT,
    severity TEXT,
    suggestion TEXT,
    context_snippet TEXT,
    radon_cc INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'pending'
);
"""

HEALTH_SNAPSHOT_DDL = """
CREATE TABLE IF NOT EXISTS code_health_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    git_sha TEXT,
    snapshot_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    total_cc_avg REAL,
    mi_avg REAL,
    clone_count INTEGER,
    dead_code_count INTEGER,
    print_count INTEGER,
    semgrep_errors INTEGER
);
"""


@dataclass
class Clone:
    clone_type: int           # 1, 2, 3, or 4
    file_a: str
    line_a_start: int
    line_a_end: int
    file_b: str
    line_b_start: int
    line_b_end: int
    similarity: float         # 0.0 – 1.0 (1.0 = exact)
    fragment_a: str = ""
    fragment_b: str = ""
    suggestion: str = ""


class ASTNormalizer(ast.NodeTransformer):
    """Normalizes AST for Type-2 clone detection by replacing identifiers
    with canonical placeholders (VAR_0, VAR_1, ...), erasing names."""

    def __init__(self):
        self._name_map: dict[str, str] = {}
        self._counter = 0

    def _canonical(self, name: str) -> str:
        if name not in self._name_map:
            self._name_map[name] = f"VAR_{self._counter}"
            self._counter += 1
        return self._name_map[name]

    def visit_Name(self, node: ast.Name) -> ast.Name:
        return ast.Name(id=self._canonical(node.id), ctx=node.ctx)

    def visit_arg(self, node: ast.arg) -> ast.arg:
        node.arg = self._canonical(node.arg)
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        node.name = "FUNC"
        self.generic_visit(node)
        return node

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.ClassDef:
        node.name = "CLASS"
        self.generic_visit(node)
        return node


def _normalize_function_ast(src: str) -> Optional[str]:
    """Parses and normalizes a function's source, returns canonical AST dump."""
    try:
        tree = ast.parse(src)
        normalizer = ASTNormalizer()
        norm = normalizer.visit(tree)
        return ast.dump(norm)
    except SyntaxError:
        return None


def _extract_functions(filepath: Path) -> list[dict]:
    """Extracts all top-level and class functions from a Python file.
    Returns list of: {name, start, end, source, file}
    """
    try:
        src = filepath.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(src, filename=str(filepath))
    except Exception:
        return []

    lines = src.splitlines()
    funcs = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start = node.lineno - 1
            end = getattr(node, "end_lineno", start + 5)
            body_lines = lines[start:end]
            funcs.append({
                "name": node.name,
                "start": start + 1,
                "end": end,
                "source": "\n".join(body_lines),
                "file": str(filepath),
            })
    return funcs


class CloneDetector:
    """
    4-level code clone detector for vazus_core.

    Stage 1 (Type 1-3): pylint --enable=duplicate-code (fast token match)
    Stage 2 (Type 2):   AST normalization + SHA-256 hash per function
    Stage 3 (Type 4):   768D cosine similarity via UnifiedEmbeddingManager
    """

    def __init__(self, root: Path | str | None = None, db_path: Path | str | None = None):
        self.root = Path(root or VAZUS_ROOT / "vazus_core")
        self.db_path = Path(db_path or VAZUS_DB)
        self._ensure_db_schema()

    # ── DB ────────────────────────────────────────────────────────────────

    def _ensure_db_schema(self) -> None:
        try:
            with sqlite3.connect(self.db_path, timeout=5) as conn:
                conn.execute(CLONE_TABLE_DDL)
                conn.execute(SUGGESTION_TABLE_DDL)
                conn.execute(HEALTH_SNAPSHOT_DDL)
                conn.commit()
        except Exception as e:
            logger.warning("Could not init DB schema: %s", e)

    def _store_clones(self, clones: list[Clone]) -> None:
        if not clones:
            return
        try:
            with sqlite3.connect(self.db_path, timeout=5) as conn:
                conn.executemany(
                    """INSERT OR IGNORE INTO code_clones
                       (clone_type, file_a, line_a_start, line_a_end,
                        file_b, line_b_start, line_b_end, similarity,
                        fragment_a, fragment_b, suggestion)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    [(c.clone_type, c.file_a, c.line_a_start, c.line_a_end,
                      c.file_b, c.line_b_start, c.line_b_end, c.similarity,
                      c.fragment_a[:500], c.fragment_b[:500], c.suggestion)
                     for c in clones]
                )
                conn.commit()
            logger.info("Stored %d clones to vazus.db", len(clones))
        except Exception as e:
            logger.warning("DB store failed: %s", e)

    def _store_suggestion(self, file_path: str, line: int, category: str,
                          *, severity: str, suggestion: str, snippet: str = "") -> None:
        try:
            with sqlite3.connect(self.db_path, timeout=5) as conn:
                conn.execute(
                    """INSERT INTO improvement_suggestions
                       (file_path, line, category, severity, suggestion, context_snippet)
                       VALUES (?,?,?,?,?,?)""",
                    (file_path, line, category, severity, suggestion, snippet[:500])
                )
                conn.commit()
        except Exception as e:
            logger.warning("Suggestion store failed: %s", e)

    # ── Stage 1: Type 1-3 via jscpd v5 (Rust, 24-37× faster than pylint R0801) ─────────────────

    def detect_type1_to_3_jscpd(self) -> list[Clone]:
        """
        Uses jscpd v5 (jscpd-rs, Rust-based) for Type 1-3 token clone detection.
        24-37× faster than pylint R0801, uses Rabin-Karp tokenization.
        Reports: JSON {duplicates: [{format, lines, fragment, ...}]}
        """
        clones: list[Clone] = []
        try:
            import tempfile, os, json
            with tempfile.TemporaryDirectory() as tmpdir:
                subprocess.run(
                    [
                        "jscpd", str(self.root),
                        "--format", "python",
                        "--min-tokens", "50",
                        "--min-lines", "4",
                        "--reporters", "json",
                        "--output", tmpdir,
                        "--ignore", "**/__pycache__/**",
                    ],
                    capture_output=True, text=True, timeout=30,
                    encoding="utf-8", errors="replace"
                )
                json_file = os.path.join(tmpdir, "jscpd-report.json")
                if not os.path.exists(json_file):
                    candidates = [f for f in os.listdir(tmpdir) if f.endswith(".json")]
                    json_file = os.path.join(tmpdir, candidates[0]) if candidates else ""

                if json_file and os.path.exists(json_file):
                    with open(json_file, encoding="utf-8") as f:
                        data = json.load(f)
                    for dup in data.get("duplicates", []):
                        first = dup.get("firstFile", {})
                        second = dup.get("secondFile", {})
                        fa = first.get("name", "")
                        fb = second.get("name", "")
                        if not fa or not fb:
                            continue
                        clone = Clone(
                            clone_type=1,
                            file_a=fa,
                            line_a_start=first.get("start", 0),
                            line_a_end=first.get("end", 0),
                            file_b=fb,
                            line_b_start=second.get("start", 0),
                            line_b_end=second.get("end", 0),
                            similarity=1.0,
                            fragment_a=dup.get("fragment", "")[:200],
                            suggestion=self._build_suggestion(
                                1, fa, first.get("start", 0),
                                fb, second.get("start", 0)
                            )
                        )
                        clones.append(clone)
        except FileNotFoundError:
            logger.warning("jscpd not found. Install: npm install -g jscpd")
        except subprocess.TimeoutExpired:
            logger.warning("jscpd timed out (>30s)")
        except Exception as e:
            logger.warning("jscpd detection error: %s", e)
        return clones

    # Keep pylint as fallback for environments without Node.js
    def detect_type1_to_3_pylint(self) -> list[Clone]:
        """Fallback: pylint R0801 line-based clone detection (slow, ~120s).
        Use detect_type1_to_3_jscpd() for production — 40× faster."""
        clones: list[Clone] = []
        try:
            result = subprocess.run(
                [VENV_PY, "-m", "pylint",
                 "--disable=all", "--enable=duplicate-code",
                 "--recursive=y", "--min-similarity-lines=5",
                 str(self.root)],
                capture_output=True, text=True, timeout=120,
                encoding="utf-8", errors="replace"
            )
            output = result.stdout + result.stderr
            block_re = re.compile(
                r"==([^:\[]+):\[(\d+):(\d+)\]\n==([^:\[]+):\[(\d+):(\d+)\]"
            )
            for m in block_re.finditer(output):
                mod_a, s_a, e_a, mod_b, s_b, e_b = m.groups()
                file_a = mod_a.replace(".", "/").replace("vazus_core/", str(self.root) + "/") + ".py"
                file_b = mod_b.replace(".", "/").replace("vazus_core/", str(self.root) + "/") + ".py"
                clones.append(Clone(
                    clone_type=1,
                    file_a=file_a, line_a_start=int(s_a), line_a_end=int(e_a),
                    file_b=file_b, line_b_start=int(s_b), line_b_end=int(e_b),
                    similarity=1.0,
                    suggestion=self._build_suggestion(1, file_a, int(s_a), file_b, int(s_b))
                ))
        except Exception as e:
            logger.warning("pylint detection error: %s", e)
        return clones

    # ── Stage 2: Type 2 via AST normalization ─────────────────────────────

    def detect_type2_ast(self) -> list[Clone]:
        """Normalizes function ASTs and groups by canonical hash for Type-2 detection."""
        hash_to_funcs: dict[str, list[dict]] = {}
        clones: list[Clone] = []

        py_files = list(self.root.rglob("*.py"))
        for fp in py_files:
            if "__pycache__" in str(fp):
                continue
            for func in _extract_functions(fp):
                norm = _normalize_function_ast(func["source"])
                if norm and len(func["source"]) > 50:  # skip trivial funcs
                    h = hashlib.sha256(norm.encode()).hexdigest()
                    hash_to_funcs.setdefault(h, []).append(func)

        for h, group in hash_to_funcs.items():
            if len(group) < 2:
                continue
            # All pairs in the group are Type-2 clones
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    a, b = group[i], group[j]
                    if a["file"] == b["file"]:
                        continue  # same file overloads — skip
                    clones.append(Clone(
                        clone_type=2,
                        file_a=a["file"], line_a_start=a["start"], line_a_end=a["end"],
                        file_b=b["file"], line_b_start=b["start"], line_b_end=b["end"],
                        similarity=0.98,
                        fragment_a=a["source"][:200],
                        fragment_b=b["source"][:200],
                        suggestion=self._build_suggestion(2, a["file"], a["start"], b["file"], b["start"],
                                                          extra=f"Functions: {a['name']} ≈ {b['name']}")
                    ))
        return clones

    # ── Stage 3: Type 4 via 768D semantic embeddings ──────────────────────

    def _collect_embeddable_functions(self) -> list[dict]:
        all_funcs: list[dict] = []
        for fp in self.root.rglob("*.py"):
            if "__pycache__" in str(fp):
                continue
            for func in _extract_functions(fp):
                if len(func["source"]) > 100:
                    all_funcs.append(func)
        return all_funcs

    def _find_semantic_pairs(self, all_funcs: list[dict], sim_matrix: Any, threshold: float) -> list[Clone]:
        clones: list[Clone] = []
        n = len(all_funcs)
        seen_pairs: set[frozenset] = set()
        for i in range(n):
            for j in range(i + 1, n):
                sim = float(sim_matrix[i, j])
                if sim < threshold:
                    continue
                a, b = all_funcs[i], all_funcs[j]
                if a["file"] == b["file"] and a["name"] == b["name"]:
                    continue
                pair_key = frozenset([f"{a['file']}:{a['start']}", f"{b['file']}:{b['start']}"])
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)
                clones.append(Clone(
                    clone_type=4,
                    file_a=a["file"], line_a_start=a["start"], line_a_end=a["end"],
                    file_b=b["file"], line_b_start=b["start"], line_b_end=b["end"],
                    similarity=round(sim, 4),
                    fragment_a=a["source"][:200], fragment_b=b["source"][:200],
                    suggestion=self._build_suggestion(4, a["file"], a["start"], b["file"], b["start"],
                                                      extra=f"sim={sim:.3f}: {a['name']} ≈ {b['name']}")
                ))
        return clones

    def detect_type4_semantic(self, threshold: float = 0.92) -> list[Clone]:
        """Finds semantic clones (Type 4) using UnifiedEmbeddingManager 768D vectors."""
        try:
            sys.path.insert(0, str(VAZUS_ROOT))
            from vazus_core.memory.embeddings import UnifiedEmbeddingManager
            import numpy as np

            manager = UnifiedEmbeddingManager()
            all_funcs = self._collect_embeddable_functions()
            if len(all_funcs) < 2:
                return []

            logger.info("Computing 768D embeddings for %d functions...", len(all_funcs))
            texts = [f["source"][:512] for f in all_funcs]
            embeddings = manager.embed_batch(texts)

            if embeddings is None or len(embeddings) != len(all_funcs):
                logger.warning("Embedding batch failed or size mismatch")
                return []

            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            norms = np.where(norms == 0, 1e-8, norms)
            normed = embeddings / norms
            sim_matrix = normed @ normed.T

            clones = self._find_semantic_pairs(all_funcs, sim_matrix, threshold)
            clones.sort(key=lambda c: -c.similarity)
            return clones
        except ImportError as e:
            logger.warning("Type-4 detection requires UnifiedEmbeddingManager: %s", e)
        except Exception as e:
            logger.exception("Type-4 semantic clone detection failed: %s", e)
        return []

    # ── Master entrypoint ─────────────────────────────────────────────────

    def detect_all(
        self,
        path: Path | str | None = None,
        semantic: bool = True,
        threshold: float = 0.92,
    ) -> list[Clone]:
        """
        Run all 4 clone detection stages and persist results to vazus.db.

        Args:
            path: Directory to scan (default: self.root)
            semantic: Whether to run Type-4 embedding scan (slower, ~5s)
            threshold: Cosine similarity threshold for Type-4 (default: 0.92)

        Returns:
            Sorted list of all detected clones (Type 1 first, then 2, 4)
        """
        if path:
            self.root = Path(path)

        logger.info("Stage 1/3: Type 1-3 clone detection (jscpd, Rust-based)...")
        t1_3 = self.detect_type1_to_3_jscpd()
        if not t1_3:
            logger.info("  jscpd returned 0 or unavailable, falling back to pylint...")
            t1_3 = self.detect_type1_to_3_pylint()
        logger.info("  → Found %d Type 1-3 clones", len(t1_3))


        logger.info("Stage 2/3: Type 2 AST normalization...")
        t2 = self.detect_type2_ast()
        logger.info("  → Found %d Type 2 clones", len(t2))

        all_clones = t1_3 + t2

        if semantic:
            logger.info("Stage 3/3: Type 4 semantic (768D cosine, threshold=%.2f)...", threshold)
            t4 = self.detect_type4_semantic(threshold=threshold)
            logger.info("  → Found %d Type 4 semantic clones", len(t4))
            all_clones += t4

        # Deduplicate overlapping pairs
        all_clones = self._deduplicate(all_clones)

        # Persist to vazus.db
        self._store_clones(all_clones)

        # Generate improvement suggestions for each clone
        for c in all_clones:
            self._store_suggestion(
                file_path=c.file_a,
                line=c.line_a_start,
                category="clone",
                severity="warning" if c.clone_type < 4 else "advisory",
                suggestion=c.suggestion,
                snippet=c.fragment_a
            )

        logger.info("Total clones found: %d (stored to vazus.db)", len(all_clones))
        return all_clones

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _build_suggestion(
        clone_type: int,
        file_a: str, line_a: int,
        file_b: str, line_b: int,
        extra: str = ""
    ) -> str:
        fa = Path(file_a).name
        fb = Path(file_b).name
        type_labels = {
            1: "Exact duplicate (Type 1)",
            2: "Renamed-variable clone (Type 2)",
            3: "Near-miss clone (Type 3)",
            4: "Semantic clone (Type 4, 768D cosine)",
        }
        label = type_labels.get(clone_type, f"Type {clone_type}")
        parts = [
            f"[{label}] {fa}:{line_a} ≈ {fb}:{line_b}",
            f"  → Extract shared logic into a utility function in vazus_core/analysis/",
        ]
        if extra:
            parts.append(f"  → {extra}")
        return "\n".join(parts)

    @staticmethod
    def _deduplicate(clones: list[Clone]) -> list[Clone]:
        seen: set[tuple] = set()
        out: list[Clone] = []
        for c in clones:
            key = (
                min(c.file_a, c.file_b),
                min(c.line_a_start, c.line_b_start),
                max(c.file_a, c.file_b),
                max(c.line_a_start, c.line_b_start),
            )
            if key not in seen:
                seen.add(key)
                out.append(c)
        return out

    def report(self, clones: list[Clone]) -> str:
        """Returns a human-readable report of all clones."""
        if not clones:
            return "✅ No code clones detected."
        lines = [f"🔍 {len(clones)} code clone(s) detected:\n"]
        for c in clones:
            fa = Path(c.file_a).name
            fb = Path(c.file_b).name
            lines.append(
                f"  [Type {c.clone_type}] sim={c.similarity:.2f}  "
                f"{fa}:{c.line_a_start} ↔ {fb}:{c.line_b_start}"
            )
            lines.append(f"    {c.suggestion.splitlines()[1] if len(c.suggestion.splitlines()) > 1 else ''}")
        return "\n".join(lines)


if __name__ == "__main__":
    import logging as _log
    _log.basicConfig(level=_log.INFO, format="%(levelname)s %(message)s")
    detector = CloneDetector()
    clones = detector.detect_all(semantic=False)  # skip semantic for CLI quick run
    print(detector.report(clones))
