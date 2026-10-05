"""
vazus_core.analysis.code_twin_finder
====================================
"Don't repeat yourself" guard: before writing a function, ask whether the codebase already has one
with the same meaning. Query is a code snippet or a plain-language (RU/EN) description.

Function vectors come from the multilingual 768D embedder and are cached in sqlite keyed by the
sha256 of the source, so only changed functions are re-embedded.

    python -m vazus_core.analysis.code_twin_finder "функция, которая считает косинусную близость"
    python -m vazus_core.analysis.code_twin_finder --file new_code.py
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List

import numpy as np

from vazus_core.paths import VAZUS_ROOT, CACHE_DIR

ROOT = VAZUS_ROOT / "vazus_core"
CACHE = CACHE_DIR / "code_twins.sqlite"
TWIN = 0.85     # near-identical meaning: show only the diff
RELATED = 0.50  # worth a look


@dataclass
class Twin:
    score: float
    file: str
    line: int
    name: str
    source: str
    diff: str = ""


def _functions(root: Path):
    import ast
    for fp in root.rglob("*.py"):
        if "__pycache__" in fp.parts:
            continue
        try:
            text = fp.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(text)
        except Exception:
            continue
        lines = text.splitlines()
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and (n.end_lineno or 0) - n.lineno >= 2:
                yield str(fp), n.lineno, n.name, "\n".join(lines[n.lineno - 1:n.end_lineno])


def _idents(text: str) -> set:
    """Lowercased identifier words (snake_case/camelCase split), keywords and 1-2 letter names dropped."""
    import keyword, re
    words = re.sub(r"([a-z])([A-Z])", r"\1_\2", text).lower()
    return {w for w in re.findall(r"[a-zа-я]{3,}", words.replace("_", " ")) if not keyword.iskeyword(w)} - {"self", "return", "import"}


def _meaning_text(src: str) -> str:
    """'cosine_similarity(a, b): <docstring>' -> 'cosine similarity. <docstring> (a, b)'. Non-code text passes through."""
    import ast, textwrap
    try:
        fn = next(n for n in ast.parse(textwrap.dedent(src)).body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)))
    except Exception:
        return src[:600]
    args = ", ".join(a.arg for a in fn.args.args if a.arg not in ("self", "cls"))
    doc = (ast.get_docstring(fn) or "").strip().splitlines()
    calls = []
    for c in ast.walk(fn):
        if isinstance(c, ast.Call):
            f = c.func
            nm = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
            if nm and nm not in calls:
                calls.append(nm.replace("_", " "))
    return f"{fn.name.replace('_', ' ').strip()}. {' '.join(doc[:2])} ({args}) uses: {', '.join(calls[:12])}"[:500]


def _index(root: Path, mgr, cached_only: bool = False) -> List[tuple]:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(CACHE)
    db.execute("CREATE TABLE IF NOT EXISTS v (h TEXT PRIMARY KEY, vec BLOB)")
    items = []
    for fp, line, name, src in _functions(root):
        h = "v3:" + hashlib.sha256(src.encode()).hexdigest()
        row = db.execute("SELECT vec FROM v WHERE h=?", (h,)).fetchone()
        if row:
            vec = np.frombuffer(row[0], dtype=np.float32)
        elif cached_only:
            continue
        else:
            vec = np.asarray(mgr.get_embedding(_meaning_text(src)), dtype=np.float32)
            db.execute("INSERT OR REPLACE INTO v VALUES (?,?)", (h, vec.tobytes()))
        items.append((fp, line, name, src, vec))
    db.commit()
    db.close()
    return items


def find_twins(query: str, root: Path | str = ROOT, top_k: int = 5, min_score: float = RELATED,
               cached_only: bool = False) -> List[Twin]:
    """Existing functions closest in meaning to `query`; near-twins carry a unified diff of the differences."""
    from vazus_core.memory.embeddings import get_embedding_manager
    mgr = get_embedding_manager()
    items = _index(Path(root), mgr, cached_only)
    if not items:
        return []
    q = np.asarray(mgr.get_embedding(_meaning_text(query)), dtype=np.float32)
    sims = np.array([float(v @ q) / ((np.linalg.norm(v) * np.linalg.norm(q)) or 1.0) for *_, v in items])
    if _meaning_text(query) != query[:600]:  # query is code: blend in identifier overlap
        qi = _idents(query)
        lex = np.array([len(qi & i) / (len(qi | i) or 1) for i in (_idents(it[3]) for it in items)])
        sims = np.minimum(1.0, sims + 0.5 * lex)  # bonus, never a penalty
    out = []
    for k in np.argsort(-sims)[:top_k]:
        if sims[k] < min_score:
            break
        fp, line, name, src, _ = items[k]
        diff = ""
        if sims[k] >= TWIN and _meaning_text(query) != query[:600]:
            diff = "\n".join(l for l in difflib.unified_diff(src.splitlines(), query.splitlines(), "existing", "new", n=0, lineterm="")
                             if not l.startswith(("---", "+++", "@@")))
        out.append(Twin(round(float(sims[k]), 3), fp, line, name, src, diff))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("query", nargs="?", default="")
    ap.add_argument("--file")
    ap.add_argument("--top", type=int, default=5)
    a = ap.parse_args(argv)
    q = Path(a.file).read_text(encoding="utf-8-sig") if a.file else a.query
    if not q.strip():
        ap.error("query or --file required")
    sys.stdout.reconfigure(encoding="utf-8")
    twins = find_twins(q, top_k=a.top)
    if not twins:
        print("No similar code found - safe to write.")
    for t in twins:
        tag = "TWIN" if t.score >= TWIN else "related"
        print(f"[{tag} {t.score:.2f}] {t.name}  {t.file}:{t.line}")
        if t.diff:
            print(t.diff)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())




