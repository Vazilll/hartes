#!/usr/bin/env python3
"""
vazus_core.mcp_client — Direct MCP Tool Executor for Subagents & Scripts.

Allows subagents or CLI scripts to invoke any Vazus OS MCP tool directly,
bypassing generic tool-call missing schema issues in subagents.
"""

import sys
import json
import os
from pathlib import Path

PROJECT_ROOT = Path("C:/vazus")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from vazus_core.memory.organic_memory_bridge import search_memory, record_insight
from vazus_core.memory.embeddings import get_embedding_manager
from vazus_core.verification.ast_pruner import ASTPruner
from vazus_core.verification.smt_z3_verifier import SMTZ3Verifier
from vazus_core.verification.concordia_jury import ConcordiaJury
from vazus_core.engine.unified_reasoning_pipeline import UnifiedReasoningPipeline


def call_mcp_direct(server_name: str, tool_name: str, args: dict) -> dict:
    """Directly dispatches tool call to underlying Vazus OS engine."""
    server_name = server_name.lower()
    tool_name = tool_name.lower()

    if server_name == "vazus-organic":
        if tool_name == "vazus_organic_recall":
            query = args.get("query", "")
            top_k = args.get("top_k", 5)
            mgr = get_embedding_manager()
            res = mgr.search_unified_vector_space(query, top_k=top_k)
            if not res:
                res = search_memory(query, limit=top_k)
            return {"status": "success", "result": res}

        elif tool_name == "vazus_record_insight":
            category = args.get("category", "general")
            insight = args.get("insight", "")
            res = record_insight(category, insight)
            return {"status": "success", "result": res}

        elif tool_name == "vazus_ast_prune":
            target = args.get("code_or_file", "")
            pruner = ASTPruner()
            if os.path.exists(target):
                res = pruner.prune_file(target)
            else:
                res = pruner.prune_code_string(target)
            return {"status": "success", "result": res}

        elif tool_name == "vazus_smt_z3_verify":
            code = args.get("code", "")
            depth = args.get("depth", 10)
            verifier = SMTZ3Verifier(depth=depth)
            res = verifier.verify_code_contracts(code)
            return {"status": "success", "result": res}

        elif tool_name == "vazus_index_repository":
            from vazus_core.integrations.repo_indexer import index_repository
            directory_path = args.get("directory_path", "")
            project_name = args.get("project_name", "vazus")
            max_files = args.get("max_files", 500)
            res = index_repository(directory_path=directory_path, project_name=project_name, max_files=max_files)
            return {"status": "success", "result": res}

    elif server_name == "vazus-reasoning":
        if tool_name == "vazus_unified_reasoning":
            pipeline = UnifiedReasoningPipeline(effort_level=args.get("effort_level", "high"))
            res = pipeline.execute_pipeline_sync(
                task_prompt=args.get("task_prompt", ""),
                code_proposal=args.get("code_proposal", ""),
                file_path=args.get("file_path", "proposal.py")
            )
            return {"status": "success", "result": res}

        elif tool_name == "vazus_smt_z3_verify_contract":
            verifier = SMTZ3Verifier(depth=10)
            res = verifier.verify_code_contracts(args.get("code_snippet", ""))
            return {"status": "success", "result": res}

        elif tool_name == "vazus_concordia_jury_vote":
            jury = ConcordiaJury(effort_level="high")
            res = jury.evaluate_code_proposal(
                file_path=args.get("file_path", ""),
                code_content=args.get("code_content", "")
            )
            return {"status": "success", "result": res}

    elif server_name == "ckb":
        import subprocess
        try:
            req = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": args}
            }
            proc = subprocess.Popen(
                ["ckb.cmd", "mcp"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            # init
            proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "subagent"}}}) + "\n")
            proc.stdin.flush()
            proc.stdout.readline() # init resp
            proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
            proc.stdin.flush()
            # call tool
            proc.stdin.write(json.dumps(req) + "\n")
            proc.stdin.flush()
            resp_line = proc.stdout.readline()
            proc.terminate()
            resp_data = json.loads(resp_line)
            return {"status": "success", "result": resp_data.get("result", {})}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    return {"status": "error", "error": f"Tool '{tool_name}' on server '{server_name}' not implemented direct."}


def main():
    if len(sys.argv) < 4:
        print(json.dumps({"error": "Usage: python mcp_client.py <server_name> <tool_name> '<json_args>'"}))
        return

    server_name = sys.argv[1]
    tool_name = sys.argv[2]
    try:
        args = json.loads(sys.argv[3])
    except Exception:
        args = {}

    res = call_mcp_direct(server_name, tool_name, args)
    print(json.dumps(res, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
