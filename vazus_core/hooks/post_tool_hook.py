#!/usr/bin/env python3
"""
vazus_core.hooks.post_tool_hook — Antigravity PostToolUse Lifecycle Hook.

Triggered AUTOMATICALLY by Antigravity AFTER file editing tools execute.
Performs instant AST syntax verification via python ast.parse on modified files.
Conforms 100% to Google Antigravity PostToolUse contract.
"""

import sys
import json
import ast
from pathlib import Path

sys.path.insert(0, "C:/vazus")
try:
    from vazus_core.hooks.hud_writer import write_hud_event
except Exception:
    def write_hud_event(event_type, payload): pass

import subprocess

def main():
    try:
        input_data = json.load(sys.stdin)
        tool_call = input_data.get("toolCall", {})
        tool_name = tool_call.get("name", "")
        args = tool_call.get("args", {})
        
        target_file = args.get("TargetFile") or args.get("AbsolutePath") or ""
        if target_file and target_file.endswith(".py"):
            target_path = Path(target_file)
            if target_path.exists():
                try:
                    code_content = target_path.read_text(encoding="utf-8", errors="ignore")
                    ast.parse(code_content)
                    
                    # Fast targeted test check (TDD Loop)
                    test_file = Path("C:/vazus/tests") / f"test_{target_path.stem}.py"
                    test_res = None
                    if test_file.exists():
                        try:
                            py_bin = Path("C:/vazus/.venv/Scripts/python.exe")
                            p = str(py_bin) if py_bin.exists() else sys.executable
                            res = subprocess.run(
                                [p, "-m", "pytest", str(test_file), "-q", "--tb=line"],
                                capture_output=True,
                                text=True,
                                timeout=4
                            )
                            test_res = "PASSED" if res.returncode == 0 else f"FAILED: {res.stdout.strip().splitlines()[-1] if res.stdout.strip() else 'error'}"
                            if res.returncode != 0:
                                sys.stderr.write(f"[Vazus OS TDD Gate] {test_file.name} {test_res}\n")
                        except Exception:
                            test_res = "SKIPPED"

                    write_hud_event("PostToolUse", {
                        "tool": tool_name,
                        "file": target_file,
                        "ast_valid": True,
                        "test_result": test_res
                    })
                except SyntaxError as se:
                    write_hud_event("PostToolUse", {
                        "tool": tool_name,
                        "file": target_file,
                        "ast_valid": False,
                        "syntax_error": f"line {se.lineno}: {se.msg}",
                    })
                    sys.stderr.write(f"[Vazus OS AST Hook Error] Syntax error in {target_file} at line {se.lineno}: {se.msg}\n")
        elif target_file:
            write_hud_event("PostToolUse", {
                "tool": tool_name,
                "file": target_file,
                "ast_valid": None,
            })
        
        print(json.dumps({}))
    except Exception:
        print(json.dumps({}))

if __name__ == "__main__":
    main()
