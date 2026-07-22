#!/usr/bin/env python3
"""
unified_worker.py — Drop-in replacement for rlm_unified_worker.py
Called by gomcp/tools/unified_search.go via subprocess stdin/stdout JSON protocol.

Input (stdin): UnifiedSearchParams JSON
Output (stdout): UnifiedSearchResult JSON
"""
import sys
import json
import time
import traceback

sys.path.insert(0, "C:/vazus/pyenv")


def run():
    # Read input from stdin
    try:
        raw = sys.stdin.read()
        params = json.loads(raw) if raw.strip() else {}
    except Exception as e:
        out = {"query": "", "mode": "error", "web_count": 0, "file_count": 0,
               "code_count": 0, "context_length": 0, "errors": [str(e)],
               "web_results": [], "file_results": [], "code_results": []}
        print(json.dumps(out))
        return

    query = params.get("query", "")
    mode = params.get("mode", "full")
    code_results_n = params.get("codeResults", params.get("code_results", 5))
    file_results_n = params.get("fileResults", params.get("file_results", 10))

    errors = []
    code_results = []
    file_results = []
    web_results = []
    rlm_result = None

    t0 = time.time()

    # ── Code search via hybrid ────────────────────────────────────────────
    if params.get("search_code", True) or params.get("searchCode", True):
        try:
            from vazus_core.workers import hybrid
            results = hybrid.leann_search(query, top_k=code_results_n)
            code_results = [
                {"text": r.get("text", ""), "score": r.get("score", 0),
                 "source": r.get("source", "leann")}
                for r in results
            ]
        except Exception as e:
            errors.append(f"code_search: {e}")

    # ── File search via FTS ───────────────────────────────────────────────
    if params.get("search_files", True) or params.get("searchFiles", True):
        try:
            from vazus_core.workers import hybrid
            results = hybrid.sqlite_search(query, limit=file_results_n)
            file_results = [
                {"text": r.get("text", ""), "score": r.get("score", 0),
                 "source": r.get("source", "sqlite")}
                for r in results
            ]
        except Exception as e:
            errors.append(f"file_search: {e}")

    # ── RLM analysis (mode=full only) ─────────────────────────────────────
    if mode == "full":
        try:
            from vazus_core.workers.rlm import run_rlm_sync
            context = "\n".join([r["text"][:300] for r in (code_results + file_results)[:5]])
            rlm_out = run_rlm_sync(query, context=context, max_iterations=3, max_depth=1)
            rlm_result = {
                "success": True,
                "result": str(rlm_out.get("result", "")),
                "elapsed": time.time() - t0,
                "iterations": rlm_out.get("iterations", 0)
            }
        except Exception as e:
            errors.append(f"rlm: {e}")
            rlm_result = {"success": False, "error": str(e)}

    context_text = "\n".join(
        [r["text"] for r in (web_results + file_results + code_results)]
    )

    output = {
        "query": query,
        "mode": mode,
        "web_count": len(web_results),
        "file_count": len(file_results),
        "code_count": len(code_results),
        "context_length": len(context_text),
        "errors": errors if errors else None,
        "web_results": web_results,
        "file_results": file_results,
        "code_results": code_results,
        "rlm_result": rlm_result,
    }

    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    try:
        run()
    except Exception:
        err = traceback.format_exc()
        out = {"query": "", "mode": "error", "web_count": 0, "file_count": 0,
               "code_count": 0, "context_length": 0, "errors": [err],
               "web_results": [], "file_results": [], "code_results": []}
        print(json.dumps(out))
