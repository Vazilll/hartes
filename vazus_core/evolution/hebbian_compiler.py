"""
vazus_core.evolution.hebbian_compiler
Hebbian Tool Compiler: Distills frequently co-occurring tool call chains into optimized composite functions.
"""

import os
import json
import time
from typing import Dict, Any
from vazus_core.memory.organic_memory_bridge import record_insight

MANIFEST_PATH = r"C:\vazus\services\memory\hebbian_tools_manifest.json"

import ast
from vazus_core.verification.ast_pruner import ASTPruner

def compile_tool(name: str, description: str, code_snippets: str) -> Dict[str, Any]:
    """Compiles a new composite tool from frequently used code patterns with AST verification and bytecode compilation."""
    os.makedirs(os.path.dirname(MANIFEST_PATH), exist_ok=True)

    is_valid_ast = False
    total_nodes = 0
    signatures: Dict[str, Any] = {}
    bytecode_compiled = False

    try:
        tree = ast.parse(code_snippets)
        is_valid_ast = True
        total_nodes = len(list(ast.walk(tree)))
        signatures = ASTPruner.extract_signatures(code_snippets)
        compile(code_snippets, filename=name, mode="exec")
        bytecode_compiled = True
    except Exception as e:
        signatures = {"error": str(e)}

    tools = {}
    if os.path.exists(MANIFEST_PATH):
        try:
            with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
                tools = json.load(f)
        except Exception:
            tools = {}

    prev_count = tools.get(name, {}).get("usage_count", 0)

    tool_entry = {
        "name": name,
        "description": description,
        "code_snippets": code_snippets,
        "is_valid_ast": is_valid_ast,
        "total_nodes": total_nodes,
        "bytecode_compiled": bytecode_compiled,
        "signatures": signatures,
        "compiled_at": time.time(),
        "usage_count": prev_count + 1
    }
    tools[name] = tool_entry

    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(tools, f, ensure_ascii=False, indent=2)

    # Record in organic memory
    record_insight(
        "hebbian_tool",
        f"Compiled Hebbian Tool [{name}]: {description} (ASTValid={is_valid_ast}, Bytecode={bytecode_compiled})"
    )

    return {
        "status": "COMPILED" if bytecode_compiled else "COMPILE_FAILED",
        "tool_name": name,
        "manifest_path": MANIFEST_PATH,
        "entry": tool_entry
    }

if __name__ == "__main__":
    res = compile_tool("ast_vector_search_composite", "Composite tool combining AST callgraph trace and 768D vector search", "def composite(): pass")
    print("[+] Hebbian Tool Result:", json.dumps(res, indent=2))
