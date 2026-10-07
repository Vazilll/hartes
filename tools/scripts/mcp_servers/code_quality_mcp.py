#!/usr/bin/env python3
"""
code_quality_mcp.py — Unified Code Quality MCP Server для Vazus OS.

Объединяет все "сиротские" инструменты в один MCP сервер:
  • ast-grep (sg)         — AST pattern search + rewrite (158 языков)
  • grit                  — GritQL декларативные рефакторинги
  • radon                 — Цикломатическая сложность (CC) + Maintainability Index
  • wily                  — Тренд метрик качества (сложность, halstead, MI)
  • pyinstrument          — Runtime hotspot profiling
  • candidate_harvester   — Dead code / рефакторинг кандидаты из vazus.db

Регистрация: ~/.gemini/config/mcp_config.json → "code-quality"
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

def _resolve_sg_binary() -> str:
    resolved = shutil.which("ast-grep") or shutil.which("sg")
    if resolved:
        return resolved
    for candidate in [
        Path.home() / ".local" / "bin" / "ast-grep",
        Path.home() / ".cargo" / "bin" / "ast-grep",
        Path("/usr/local/bin/ast-grep"),
        Path("/usr/bin/ast-grep"),
        Path(r"C:\Users\Vaz\AppData\Roaming\npm\ast-grep.cmd"),
        Path(r"C:\Users\Vaz\AppData\Roaming\npm\sg.cmd"),
    ]:
        if candidate.exists():
            return str(candidate)
    return "ast-grep"

# ── FastMCP ──────────────────────────────────────────────────────────────────
try:
    from fastmcp import FastMCP
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "fastmcp", "-q"])
    from fastmcp import FastMCP

mcp = FastMCP("code-quality")

_vazus_base = Path(__file__).resolve().parents[3]
VAZUS_ROOT = Path(os.getenv("VAZUS_WORKSPACE_DIR", str(_vazus_base)))
VENV_BIN   = VAZUS_ROOT / ".venv" / ("Scripts" if sys.platform == "win32" else "bin")
PY         = str(VENV_BIN / ("python.exe" if sys.platform == "win32" else "python"))


def _safe_run(cmd, timeout=60, **kwargs):
    kwargs.setdefault("capture_output", True)
    kwargs.setdefault("text", True)
    kwargs.setdefault("stdin", subprocess.DEVNULL)
    kwargs.setdefault("encoding", "utf-8")
    kwargs.setdefault("errors", "replace")
    return subprocess.run(cmd, timeout=timeout, **kwargs)

# ─────────────────────────────────────────────────────────────────────────────
# TOOL 1: ast-grep pattern search
# ─────────────────────────────────────────────────────────────────────────────
@mcp.tool()
def ast_grep_search(
    pattern: str,
    language: str = "python",
    path: str = str(VAZUS_ROOT),
    max_results: int = 50
) -> str:
    """
    Search for AST structural patterns in source code using ast-grep (sg).

    Args:
        pattern: AST pattern to search, e.g. "def $FUNC($$$ARGS): ..." or "assert True"
        language: Language code: python, javascript, typescript, rust, go, java, ...
        path: Root directory or file to search (default: C:/vazus)
        max_results: Max number of results to return

    Returns:
        JSON list of matches with file, line, text.
    """
    sg = _resolve_sg_binary()
    try:
        result = _safe_run(
            [sg, "run", "--pattern", pattern, "--lang", language,
             "--json", path],
            timeout=30
        )
        if result.returncode not in (0, 1):
            return json.dumps({"error": result.stderr[:500], "matches": []})
        try:
            data = json.loads(result.stdout) if result.stdout.strip() else []
            if isinstance(data, list):
                matches = [
                    {"file": m.get("file", "?"),
                     "line": m.get("range", {}).get("start", {}).get("line", 0),
                     "text": m.get("text", "")[:200]}
                    for m in data[:max_results]
                ]
                return json.dumps({"matches": matches, "total": len(data)})
        except json.JSONDecodeError:
            pass
        lines = result.stdout.splitlines()[:max_results]
        return json.dumps({"matches": lines, "total": len(lines)})
    except FileNotFoundError:
        return json.dumps({"error": "ast-grep (sg) not found. Install: npm install -g @ast-grep/cli"})
    except subprocess.TimeoutExpired:
        return json.dumps({"error": "ast-grep timed out after 30s"})


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 2: ast-grep rewrite (L3 codemod)
# ─────────────────────────────────────────────────────────────────────────────
@mcp.tool()
def ast_grep_rewrite(
    pattern: str,
    replacement: str,
    language: str = "python",
    path: str = str(VAZUS_ROOT),
    dry_run: bool = True
) -> str:
    """
    Rewrite AST structural patterns in source code using ast-grep (sg).
    ALWAYS runs in dry-run mode by default — set dry_run=False to apply changes.

    Args:
        pattern: Pattern to find, e.g. "print($MSG)"
        replacement: Replacement, e.g. "logger.info($MSG)"
        language: Language code
        path: Root directory or file
        dry_run: If True (default), only show what would change — do NOT modify files
    """
    sg = _resolve_sg_binary()
    cmd = [sg, "run", "--pattern", pattern, "--rewrite", replacement,
           "--lang", language, "--json"]
    if not dry_run:
        cmd.append("--update-all")
    cmd.append(path)
    try:
        result = _safe_run(cmd, timeout=60)
        mode = "DRY RUN" if dry_run else "APPLIED"
        lines = result.stdout.splitlines()[:30]
        return json.dumps({
            "mode": mode,
            "returncode": result.returncode,
            "preview": lines,
            "stderr": result.stderr[:200] if result.stderr else ""
        })
    except FileNotFoundError:
        return json.dumps({"error": "ast-grep not found"})
    except subprocess.TimeoutExpired:
        return json.dumps({"error": "ast-grep rewrite timed out"})


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 3: grit apply (GritQL pattern)
# ─────────────────────────────────────────────────────────────────────────────
@mcp.tool()
def grit_apply(
    pattern_or_preset: str,
    path: str = str(VAZUS_ROOT),
    dry_run: bool = True
) -> str:
    """
    Apply a GritQL pattern or preset to the codebase using the grit CLI.
    Examples of preset: "python/print_to_logging", "remove_unused_imports"

    Args:
        pattern_or_preset: GritQL pattern string or named preset
        path: Directory to apply to
        dry_run: If True (default), only show what would change (--dry-run)
    """
    cmd = ["grit", "apply", pattern_or_preset]
    if dry_run:
        cmd.append("--dry-run")
    cmd.append(path)
    try:
        result = _safe_run(cmd, timeout=60)
        return json.dumps({
            "mode": "DRY RUN" if dry_run else "APPLIED",
            "returncode": result.returncode,
            "output": (result.stdout + result.stderr)[:2000]
        })
    except FileNotFoundError:
        return json.dumps({"error": "grit not found. Install: npm install -g @getgrit/cli"})
    except subprocess.TimeoutExpired:
        return json.dumps({"error": "grit timed out"})


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 4: radon complexity
# ─────────────────────────────────────────────────────────────────────────────
@mcp.tool()
def radon_complexity(
    path: str = str(VAZUS_ROOT / "vazus_core"),
    min_rank: str = "C",
    show_complexity: bool = True
) -> str:
    """
    Compute cyclomatic complexity for Python code using radon.
    Returns functions/methods sorted by complexity.

    Args:
        path: File or directory to analyze
        min_rank: Minimum rank to show: A(1-5), B(6-10), C(11-15), D(16-20), E(21-25), F(26+)
        show_complexity: Include raw CC numbers in output
    """
    cmd = [PY, "-m", "radon", "cc", path, "--min", min_rank, "--json"]
    if show_complexity:
        cmd.append("--show-complexity")
    try:
        result = _safe_run(cmd, timeout=60)
        try:
            data = json.loads(result.stdout) if result.stdout.strip() else {}
            # Flatten and sort by complexity
            items = []
            for fname, funcs in data.items():
                for f in funcs:
                    items.append({
                        "file": fname,
                        "name": f.get("name"),
                        "complexity": f.get("complexity"),
                        "rank": f.get("rank"),
                        "lineno": f.get("lineno")
                    })
            items.sort(key=lambda x: x.get("complexity", 0), reverse=True)
            return json.dumps({"results": items[:50], "total_functions": len(items)})
        except json.JSONDecodeError:
            return json.dumps({"raw": result.stdout[:3000]})
    except FileNotFoundError:
        return json.dumps({"error": "radon not installed. Run: pip install radon"})
    except subprocess.TimeoutExpired:
        return json.dumps({"error": "radon timed out"})


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 5: radon maintainability index
# ─────────────────────────────────────────────────────────────────────────────
@mcp.tool()
def radon_maintainability(
    path: str = str(VAZUS_ROOT / "vazus_core"),
    min_rank: str = "B"
) -> str:
    """
    Compute Maintainability Index (MI) for Python files.
    MI > 20 = maintainable, MI 10-20 = moderate, MI < 10 = hard to maintain.

    Args:
        path: Directory to analyze
        min_rank: Minimum rank filter: A(MI>20), B(10<MI≤20), C(MI≤10)
    """
    cmd = [PY, "-m", "radon", "mi", path, "--min", min_rank, "--json"]
    try:
        result = _safe_run(cmd, timeout=60)
        try:
            data = json.loads(result.stdout) if result.stdout.strip() else {}
            items = [
                {"file": f, "mi": v.get("mi"), "rank": v.get("rank")}
                for f, v in data.items()
            ]
            items.sort(key=lambda x: x.get("mi", 100))
            return json.dumps({"results": items[:50], "total_files": len(items)})
        except json.JSONDecodeError:
            return json.dumps({"raw": result.stdout[:2000]})
    except FileNotFoundError:
        return json.dumps({"error": "radon not installed"})
    except subprocess.TimeoutExpired:
        return json.dumps({"error": "radon mi timed out"})


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 6: wily report (complexity trend)
# ─────────────────────────────────────────────────────────────────────────────
@mcp.tool()
def wily_report(
    path: str = str(VAZUS_ROOT / "vazus_core"),
    metric: str = "cyclomatic_complexity",
    n_revisions: int = 10
) -> str:
    """
    Show the historical trend of a code quality metric using wily.
    Tracks how complexity changes across git commits.

    Args:
        path: Directory or file to report on
        metric: Metric name: cyclomatic_complexity, maintainability_index, loc, sloc, ...
        n_revisions: Number of git revisions to include
    """
    try:
        # First build the wily index if needed
        _safe_run(
            [PY, "-m", "wily", "build", path, "-n", str(n_revisions)],
            timeout=120, cwd=str(VAZUS_ROOT)
        )
        # Then get the report
        report_result = _safe_run(
            [PY, "-m", "wily", "report", path, metric, "--format", "JSON"],
            timeout=30, cwd=str(VAZUS_ROOT)
        )
        output = report_result.stdout or report_result.stderr
        try:
            return json.dumps({"report": json.loads(output)})
        except json.JSONDecodeError:
            return json.dumps({"raw": output[:3000]})
    except FileNotFoundError:
        return json.dumps({"error": "wily not installed. Run: pip install wily"})
    except subprocess.TimeoutExpired:
        return json.dumps({"error": "wily timed out (building git history)"})


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 7: pyinstrument hotspot profiler
# ─────────────────────────────────────────────────────────────────────────────
@mcp.tool()
def pyinstrument_profile(
    script: str,
    args: list[str] = [],
    timeout: int = 30
) -> str:
    """
    Profile a Python script or module and return the top hotspots.
    Use this to find slow functions in vazus_core.

    Args:
        script: Path to Python script OR "-m module.name" to profile a module
        args: Additional args to pass to the script
        timeout: Max seconds to run (default 30)
    """
    cmd = [PY, "-m", "pyinstrument", "--renderer", "json"]
    if script.startswith("-m "):
        cmd += script.split()
    else:
        cmd.append(script)
    cmd.extend(args)
    try:
        result = _safe_run(cmd, timeout=timeout, cwd=str(VAZUS_ROOT))
        try:
            data = json.loads(result.stdout)
            # Extract top hotspots from pyinstrument JSON
            def extract_hotspots(frame, depth=0, out=None):
                if out is None:
                    out = []
                if depth > 5:
                    return out
                if frame and frame.get("time", 0) > 0.01:
                    out.append({
                        "function": frame.get("function", "?"),
                        "file": frame.get("file_path_short", "?"),
                        "line": frame.get("line_no", 0),
                        "time_s": round(frame.get("time", 0), 4)
                    })
                for child in (frame.get("children") or []):
                    extract_hotspots(child, depth + 1, out)
                return out
            hotspots = sorted(
                extract_hotspots(data.get("root_frame", {})),
                key=lambda x: x["time_s"], reverse=True
            )[:20]
            return json.dumps({"hotspots": hotspots, "duration_s": data.get("duration")})
        except (json.JSONDecodeError, AttributeError):
            return json.dumps({"raw": result.stdout[:3000] or result.stderr[:500]})
    except FileNotFoundError:
        return json.dumps({"error": "pyinstrument not installed"})
    except subprocess.TimeoutExpired:
        return json.dumps({"error": f"profiling timed out after {timeout}s"})


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 8: candidate_harvester — dead code + refactoring candidates
# ─────────────────────────────────────────────────────────────────────────────
@mcp.tool()
def harvest_refactoring_candidates(
    path: str = str(VAZUS_ROOT / "vazus_core"),
    min_confidence: int = 70,
    max_results: int = 40
) -> str:
    """
    Find dead code and refactoring candidates using vazus_core candidate_harvester.
    Combines vulture dead-code detection with the protected whitelist.

    Args:
        path: Directory to scan
        min_confidence: Minimum vulture confidence (0-100, default 70)
        max_results: Max candidates to return
    """
    try:
        sys.path.insert(0, str(VAZUS_ROOT))
        from vazus_core.verification.candidate_harvester import CandidateHarvester
        harvester = CandidateHarvester(workspace_root=str(VAZUS_ROOT))
        rel_sub = str(Path(path).relative_to(VAZUS_ROOT)) if Path(path).is_relative_to(VAZUS_ROOT) else None
        candidates = harvester.harvest_dead_function_candidates(target_subdir=rel_sub)
        results = [
            {
                "name": c["function_name"],
                "type": "function",
                "file": c["file"],
                "safety_level": c.get("safety_level", "MEDIUM"),
                "confidence": 90 if c.get("is_private") else 75
            }
            for c in candidates
        ][:max_results]
        return json.dumps({"candidates": results, "total": len(candidates)})
    except Exception as e:
        # Fallback: direct vulture call
        try:
            result = _safe_run(
                [PY, "-m", "vulture", path, "--min-confidence", str(min_confidence), "--json"],
                timeout=60
            )
            try:
                data = json.loads(result.stdout)
                return json.dumps({"candidates": data[:max_results], "total": len(data), "via": "vulture_direct"})
            except json.JSONDecodeError:
                lines = result.stdout.splitlines()[:max_results]
                return json.dumps({"candidates": lines, "via": "vulture_text"})
        except Exception as e2:
            return json.dumps({"error": f"harvester failed: {e}; vulture fallback: {e2}"})


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 9: pydeps — module dependency graph
# ─────────────────────────────────────────────────────────────────────────────
@mcp.tool()
def pydeps_graph(
    module: str = "vazus_core",
    max_bacon: int = 2,
    output_path: Optional[str] = None
) -> str:
    """
    Generate a dependency graph for a Python module using pydeps.
    Shows which modules depend on which.

    Args:
        module: Module name to analyze (must be importable from VAZUS_ROOT)
        max_bacon: Max dependency depth (bacon number). 2 = direct + indirect deps
        output_path: Path to save SVG (optional, defaults to temp dir)
    """
    if output_path is None:
        output_path = str(VAZUS_ROOT / "docs" / f"pydeps_{module.replace('.','_')}.svg")

    try:
        result = _safe_run(
            [PY, "-m", "pydeps", module,
             "--max-bacon", str(max_bacon),
             "--output", output_path,
             "--no-show",
             "--rankdir", "LR"],
            timeout=60, cwd=str(VAZUS_ROOT)
        )
        if Path(output_path).exists():
            size = Path(output_path).stat().st_size
            return json.dumps({
                "status": "generated",
                "output": output_path,
                "size_bytes": size,
                "stderr": result.stderr[:300] if result.stderr else ""
            })
        return json.dumps({
            "status": "failed",
            "returncode": result.returncode,
            "stderr": result.stderr[:500]
        })
    except FileNotFoundError:
        return json.dumps({"error": "pydeps not installed. Run: pip install pydeps"})
    except subprocess.TimeoutExpired:
        return json.dumps({"error": "pydeps timed out"})


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 10: detect_clones — 4-level code clone detection
# ─────────────────────────────────────────────────────────────────────────────
@mcp.tool()
def detect_clones(
    path: str = str(VAZUS_ROOT / "vazus_core"),
    clone_types: str = "1,2",
    semantic: bool = False,
    threshold: float = 0.92
) -> str:
    """
    Detect code clones at 4 levels of sophistication.

    Type 1: Exact token copies (different whitespace/comments) — pylint R0801
    Type 2: Renamed identifiers, same AST structure — normalization + SHA256
    Type 3: Near-miss (added/deleted statements) — pylint
    Type 4: Semantic clones (same logic, different impl) — 768D cosine embeddings

    Args:
        path: Directory to scan (default: vazus_core)
        clone_types: Comma-separated types to detect: "1,2" or "1,2,3,4"
        semantic: Whether to include Type-4 semantic scan (slower, needs embeddings)
        threshold: Cosine similarity threshold for Type 4 (default 0.92)

    Returns:
        JSON with clone list and suggestions.
    """
    try:
        sys.path.insert(0, str(VAZUS_ROOT))
        from vazus_core.analysis.clone_detector import CloneDetector
        detector = CloneDetector(root=Path(path))
        clones = detector.detect_all(semantic=semantic, threshold=threshold)
        return json.dumps({
            "total_clones": len(clones),
            "clones": [
                {
                    "type": c.clone_type,
                    "similarity": c.similarity,
                    "file_a": c.file_a,
                    "line_a": c.line_a_start,
                    "file_b": c.file_b,
                    "line_b": c.line_b_start,
                    "suggestion": c.suggestion
                }
                for c in clones[:30]
            ],
            "report": detector.report(clones)
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 11: get_improvement_suggestions — reads proactive DB suggestions
# ─────────────────────────────────────────────────────────────────────────────
@mcp.tool()
def get_improvement_suggestions(
    file_path: str = "",
    category: str = "",
    severity: str = "",
    limit: int = 20,
    run_fresh_scan: bool = False
) -> str:
    """
    Get proactive code improvement suggestions from vazus.db.
    These are auto-generated by ProactiveSuggestionEngine during commits and background scans.

    Optionally run a fresh scan on a specific file before returning results.

    Args:
        file_path: Filter by file path (optional, partial match)
        category: Filter by category: complexity|clone|print|md5|dead_code|security
        severity: Filter by severity: error|warning|advisory
        limit: Max suggestions to return (default 20)
        run_fresh_scan: If True, runs a fresh scan on file_path before returning results

    Returns:
        JSON with suggestions list and improvement report.
    """
    try:
        sys.path.insert(0, str(VAZUS_ROOT))
        from vazus_core.analysis.proactive_suggestion_engine import ProactiveSuggestionEngine
        from pathlib import Path as _Path
        import sqlite3 as _sql

        engine = ProactiveSuggestionEngine()

        if run_fresh_scan and file_path:
            fp = _Path(file_path)
            if fp.exists():
                engine.scan_file(fp)
            
        db = engine.db_path
        query = "SELECT file_path, line, category, severity, suggestion, context_snippet, radon_cc, created_at FROM improvement_suggestions WHERE status='pending'"
        params: list = []
        if file_path:
            query += " AND file_path LIKE ?"
            params.append(f"%{file_path}%")
        if category:
            query += " AND category=?"
            params.append(category)
        if severity:
            query += " AND severity=?"
            params.append(severity)
        query += " ORDER BY CASE severity WHEN 'error' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END, created_at DESC LIMIT ?"
        params.append(limit)

        with _sql.connect(db, timeout=5) as conn:
            rows = conn.execute(query, params).fetchall()

        suggestions = []
        for fp_r, line, cat, sev, sugg, snippet, cc, ts in rows:
            suggestions.append({
                "file": _Path(fp_r).name,
                "line": line,
                "category": cat,
                "severity": sev,
                "suggestion": sugg[:300],
                "snippet": snippet[:100] if snippet else "",
                "radon_cc": cc,
                "detected_at": ts
            })

        # Build human-readable report
        by_sev = {"error": [], "warning": [], "advisory": []}
        for s in suggestions:
            by_sev.setdefault(s["severity"], []).append(s)

        report_lines = [f"📋 {len(suggestions)} pending improvement(s):"]
        for sev in ("error", "warning", "advisory"):
            group = by_sev.get(sev, [])
            if group:
                report_lines.append(f"\n[{sev.upper()}] ({len(group)})")
                for s in group[:8]:
                    report_lines.append(f"  [{s['category']}] {s['file']}:{s['line']} — {s['suggestion'][:120]}")

        return json.dumps({
            "total": len(suggestions),
            "suggestions": suggestions,
            "report": "\n".join(report_lines)
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


if __name__ == "__main__":
    mcp.run(transport="stdio")
