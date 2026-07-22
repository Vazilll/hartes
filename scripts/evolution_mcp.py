#!/usr/bin/env python3
"""dnts-evolution MCP — Bio-inspired Code Evolution server.

Tools for code crossover, Hebbian tool compilation, prompt evolution,
duplicate detection, and AST call-graph tracing.
"""
import sys
import json
import ast
from pathlib import Path
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
sys.path.insert(0, "C:/vazus/pyenv")

from fastmcp import FastMCP

MCP = FastMCP("dnts-evolution")

WORKSPACE = Path("C:/vazus/pyenv")
SKIP_DIRS = {".venv", "__pycache__", ".git", "node_modules", ".agents", ".claude",
             "hermes-home", "Bonsai-demo"}


@MCP.tool(description=(
    "Run prompt self-evolution: iteratively refine a prompt using textual gradients. "
    "Uses the local LLM adapter at :5001."
))
def run_prompt_evolution(prompt_id: str, iterations: int = 3) -> str:
    try:
        from vazus_core.evolution.prompt_optimizer import run as _run
        result = _run(prompt_id=prompt_id, iterations=iterations)
        if isinstance(result, dict):
            return json.dumps(result, ensure_ascii=False, indent=2, default=str)
        return str(result)
    except Exception as e:
        return f"Error: {e}"


@MCP.tool(description=(
    "Compile a Hebbian tool: distill code snippets + description into a reusable "
    "optimized function and register it in the rlm_tools manifest."
))
def compile_hebbian_tool(name: str, description: str, code_snippets: str) -> str:
    try:
        from vazus_core.evolution.hebbian_compiler import compile_tool
        result = compile_tool(name=name, description=description,
                              code_snippets=code_snippets)
        return json.dumps(result, ensure_ascii=False, indent=2, default=str)
    except Exception as e:
        return f"Error: {e}"


@MCP.tool(description=(
    "Find duplicate function/class definitions across Python files in root directory. "
    "Uses AST parsing — much more accurate than text search."
))
def find_code_duplicates(root: str = "C:/vazus/pyenv", extensions: str = ".py") -> str:
    root_path = Path(root)
    if not root_path.exists():
        return f"Root path not found: {root}"

    ext_list = [e.strip() for e in extensions.split(",")]
    definitions: dict[str, list[str]] = defaultdict(list)

    for fpath in root_path.rglob("*"):
        if not fpath.is_file():
            continue
        if any(part in SKIP_DIRS for part in fpath.parts):
            continue
        if fpath.suffix not in ext_list:
            continue
        try:
            source = fpath.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source)
            rel = str(fpath.relative_to(root_path)).replace("\\", "/")
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    definitions[node.name].append(f"{rel}:{node.lineno}")
        except (SyntaxError, OSError):
            continue

    duplicates = {name: locs for name, locs in definitions.items()
                  if len(locs) > 1 and name not in ("__init__", "run", "main")}
    if not duplicates:
        return f"✅ No meaningful duplicates found in {root}"

    lines = [f"## Duplicates in `{root}`\n", f"Found **{len(duplicates)}** names:\n"]
    for name, locs in sorted(duplicates.items(), key=lambda x: -len(x[1]))[:50]:
        lines.append(f"\n### `{name}` ({len(locs)} defs)")
        for loc in locs:
            lines.append(f"  - `{loc}`")
    return "\n".join(lines)


@MCP.tool(description=(
    "Find all call sites of a function by name across the workspace. "
    "Uses AST — returns file:line for each call."
))
def find_callers(function_name: str, root: str = "C:/vazus/pyenv") -> str:
    root_path = Path(root)
    callers: list[str] = []

    for fpath in root_path.rglob("*.py"):
        if any(part in SKIP_DIRS for part in fpath.parts):
            continue
        try:
            source = fpath.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source)
            rel = str(fpath.relative_to(root_path)).replace("\\", "/")
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    name = None
                    if isinstance(node.func, ast.Name):
                        name = node.func.id
                    elif isinstance(node.func, ast.Attribute):
                        name = node.func.attr
                    if name == function_name:
                        callers.append(f"`{rel}:{node.lineno}`")
        except (SyntaxError, OSError):
            continue

    if not callers:
        return f"No callers of `{function_name}` found in `{root}`"
    return (f"## Callers of `{function_name}` ({len(callers)} sites)\n\n"
            + "\n".join(f"- {c}" for c in sorted(callers)))


if __name__ == "__main__":
    MCP.run()
