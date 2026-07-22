#!/usr/bin/env python3
"""leann-mcp — LEANN vector search MCP server for DNTS.

Search routes (in priority order):
  1. HTTP daemon :5010  — warm, <2s, for the active pyenv-project index
  2. leann_search_direct — cold start via sentence-transformers, for any index
  3. Text scan fallback  — keyword search on .passages.jsonl (always works)

Tools:
  leann_search  — Semantic search (auto-routes to daemon or direct)
  leann_list    — List available indexes
  leann_index   — Build a new index via build_leann_index.py
  leann_delete  — Delete an index
"""
import sys
import os
import json
import subprocess
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from fastmcp import FastMCP

MCP = FastMCP("leann-mcp")

# ── Config ────────────────────────────────────────────────────────────────
LEANN_DIR = Path(os.environ.get("LEANN_DIR", "C:/vazus/pyenv/leann-indexes"))
LEANN_DIR.mkdir(parents=True, exist_ok=True)

SCRIPTS_DIR = Path("C:/vazus/pyenv/scripts")
PYTHON_EXE = "C:/vazus/pyenv/.venv/Scripts/python.exe"
DAEMON_URL = "http://127.0.0.1:5010/search"

# The index that the HTTP daemon keeps warm in RAM
DAEMON_INDEX = "pyenv-project"


def _json(data) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)


# ── Search routing ────────────────────────────────────────────────────────

def _search_via_daemon(query: str, top_k: int) -> list[dict] | None:
    """Try the HTTP leann_daemon (warm, <2s). Returns None on failure."""
    try:
        payload = json.dumps({"query": query, "top_k": top_k}).encode()
        req = urllib.request.Request(
            DAEMON_URL, data=payload,
            headers={"Content-Type": "application/json"}, method="POST"
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        return data.get("results", [])
    except Exception:
        return None


def _search_via_direct(index_path: str, query: str, top_k: int) -> list[dict] | None:
    """Import leann_search_direct and run semantic search on any index."""
    try:
        scripts = str(SCRIPTS_DIR)
        if scripts not in sys.path:
            sys.path.insert(0, scripts)
        import importlib
        mod = importlib.import_module("leann_search_direct")
        # reload if already cached with different index
        results = mod.search(query, top_k=top_k, index_path=index_path)
        return results
    except Exception:
        return None


def _search_text_scan(index_path: str, query: str, top_k: int) -> list[dict]:
    """Keyword scan on .passages.jsonl — always works, no ML needed."""
    passages_file = Path(index_path + ".passages.jsonl")
    if not passages_file.exists():
        return []
    q_lower = query.lower()
    results = []
    with passages_file.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                p = json.loads(line)
                text = p.get("text", "")
                if q_lower in text.lower():
                    results.append({"text": text, "score": 0.5, "source": "text_scan"})
                    if len(results) >= top_k:
                        break
            except json.JSONDecodeError:
                continue
    return results


# ══════════════════════════════════════════════════════════════════════════
# MCP TOOLS
# ══════════════════════════════════════════════════════════════════════════

@MCP.tool(description="List all available LEANN indexes in the indexes directory")
def leann_list() -> str:
    indexes = []
    for f in sorted(LEANN_DIR.glob("*.leann")):
        passages = Path(str(f) + ".passages.jsonl")
        line_count = 0
        if passages.exists():
            with passages.open(encoding="utf-8", errors="replace") as pf:
                line_count = sum(1 for l in pf if l.strip())
        indexes.append({
            "name": f.stem,
            "path": str(f),
            "size_bytes": f.stat().st_size,
            "passages": line_count,
            "daemon_active": f.stem == DAEMON_INDEX,
        })
    return _json(indexes)


@MCP.tool(description=(
    "Semantic search over a LEANN index. "
    "Uses HTTP daemon (:5010) for the active 'pyenv-project' index (<2s), "
    "or direct sentence-transformers for any other index."
))
def leann_search(query: str, name: str = "pyenv-project", top_k: int = 5) -> str:
    index_path = str(LEANN_DIR / f"{name}.leann")

    # 1. Try HTTP daemon (only for the warm index)
    if name == DAEMON_INDEX:
        results = _search_via_daemon(query, top_k)
        if results is not None:
            return _json({"query": query, "index": name, "source": "daemon", "results": results})

    # 2. Try direct sentence-transformers
    results = _search_via_direct(index_path, query, top_k)
    if results is not None:
        return _json({"query": query, "index": name, "source": "direct", "results": results})

    # 3. Text scan fallback
    results = _search_text_scan(index_path, query, top_k)
    return _json({"query": query, "index": name, "source": "text_scan", "results": results})


@MCP.tool(description=(
    "Build a new LEANN index from a JSON array of text strings. "
    "Runs build_leann_index.py as a subprocess (handles all ML deps internally)."
))
def leann_index(name: str, documents_json: str) -> str:
    try:
        docs = json.loads(documents_json)
        if not isinstance(docs, list):
            docs = [str(docs)]
    except json.JSONDecodeError as e:
        return _json({"error": f"Invalid JSON: {e}"})

    build_script = str(SCRIPTS_DIR / "build_leann_index.py")
    if not Path(build_script).exists():
        return _json({"error": f"build_leann_index.py not found at {build_script}"})

    # Write docs to a temp file and pass to the builder
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False,
                                     encoding="utf-8") as tmp:
        json.dump(docs, tmp)
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            [PYTHON_EXE, build_script, "--name", name, "--docs", tmp_path],
            capture_output=True, text=True, timeout=300,
            cwd=str(SCRIPTS_DIR.parent)
        )
        Path(tmp_path).unlink(missing_ok=True)
        if result.returncode != 0:
            return _json({"error": result.stderr.strip() or "Build failed"})
        return _json({
            "status": "created",
            "name": name,
            "path": str(LEANN_DIR / f"{name}.leann"),
            "documents": len(docs),
            "output": result.stdout.strip()
        })
    except subprocess.TimeoutExpired:
        return _json({"error": "Index build timed out (>5 min)"})
    except Exception as e:
        return _json({"error": str(e)})


@MCP.tool(description="Delete a LEANN index and its associated passages file")
def leann_delete(name: str) -> str:
    deleted = []
    errors = []
    for suffix in [".leann", ".leann.passages.jsonl"]:
        path = LEANN_DIR / f"{name}{suffix}"
        if path.exists():
            try:
                path.unlink()
                deleted.append(str(path))
            except Exception as e:
                errors.append(str(e))

    if not deleted and not errors:
        return _json({"error": f"Index '{name}' not found in {LEANN_DIR}"})
    return _json({"status": "deleted", "name": name, "deleted": deleted, "errors": errors})


if __name__ == "__main__":
    MCP.run()
