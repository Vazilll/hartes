#!/usr/bin/env python3
"""Quick health check for all new MCP servers."""
import sys, json, traceback
sys.path.insert(0, "C:/vazus")

PASS = "\u2705"
FAIL = "\u274c"
WARN = "\u26a0\ufe0f"

results = []

def test(name, fn):
    try:
        r = fn()
        results.append((PASS, name, str(r)[:120]))
    except Exception as e:
        results.append((FAIL, name, str(e)[:120]))

# ── leann-mcp ────────────────────────────────────────────────────────────
print("Testing leann-mcp...")
try:
    exec(open("C:/vazus/scripts/leann-mcp.py", encoding="utf-8").read().split("if __name__")[0])
    test("leann_list()", lambda: f"{len(json.loads(leann_list()))} indexes")
    test("leann_search(daemon)", lambda: json.loads(leann_search("worker search architecture", top_k=2))["source"])
except Exception as e:
    results.append((FAIL, "leann-mcp import", str(e)))

# ── dnts-hybrid-search ───────────────────────────────────────────────────
print("Testing dnts-hybrid-search...")
try:
    from vazus_core.workers import hybrid
    test("fts_search()", lambda: hybrid.sqlite_search("worker", 3))
    test("leann_search(via hybrid)", lambda: hybrid.leann_search("search architecture", 2))
    test("hybrid.run()", lambda: hybrid.run("code search worker", limit=3)["result_count"])
except Exception as e:
    results.append((FAIL, "hybrid import", str(e)))

# ── dnts-rlm ─────────────────────────────────────────────────────────────
print("Testing dnts-rlm...")
try:
    from vazus_core import database
    tasks = database.list_tasks(limit=5)
    results.append((PASS, "dnts-rlm database", f"{len(tasks)} tasks in DB"))
    from vazus_core.workers.rlm import load_compiled_tools
    tools = load_compiled_tools()
    results.append((PASS, "rlm compiled tools", f"{len(tools)} tools loaded"))
except Exception as e:
    results.append((FAIL, "dnts-rlm", str(e)))

# ── dnts-ldr ─────────────────────────────────────────────────────────────
print("Testing dnts-ldr...")
try:
    from vazus_core.workers import ldr
    results.append((PASS, "dnts-ldr import", "OK"))
except Exception as e:
    results.append((FAIL, "dnts-ldr", str(e)))

# ── dnts-evolution ───────────────────────────────────────────────────────
print("Testing dnts-evolution...")
try:
    exec(open("C:/vazus/scripts/evolution_mcp.py", encoding="utf-8").read().split("if __name__")[0])
    test("find_code_duplicates(vazus_core)", lambda: find_code_duplicates("C:/vazus/vazus_core")[:60])
    test("find_callers(load_adapter_key)", lambda: find_callers("load_adapter_key", "C:/vazus/vazus_core")[:60])
except Exception as e:
    results.append((FAIL, "dnts-evolution import", str(e)))

# ── leann daemon ─────────────────────────────────────────────────────────
print("Testing leann daemon HTTP...")
try:
    import urllib.request
    req = urllib.request.Request("http://127.0.0.1:5010/health")
    with urllib.request.urlopen(req, timeout=3) as resp:
        data = json.loads(resp.read())
    results.append((PASS if data.get("ok") else WARN, "leann daemon :5010", str(data)))
except Exception as e:
    results.append((WARN, "leann daemon :5010", f"Not ready yet: {e}"))

# ── dnts-orchestrator-v2 ─────────────────────────────────────────────────
print("Testing dnts-orchestrator-v2...")
try:
    from vazus_core.mcp_server import list_tasks
    r = list_tasks()
    results.append((PASS, "orchestrator list_tasks", f"{len(json.loads(r))} tasks"))
except Exception as e:
    results.append((FAIL, "dnts-orchestrator-v2", str(e)))

# ── Print report ─────────────────────────────────────────────────────────
print("\n" + "="*60)
print("DNTS MCP HEALTH REPORT")
print("="*60)
for icon, name, detail in results:
    print(f"{icon}  {name:<35} {detail}")

passed = sum(1 for i,_,_ in results if i == PASS)
failed = sum(1 for i,_,_ in results if i == FAIL)
warned = sum(1 for i,_,_ in results if i == WARN)
print(f"\n{'='*60}")
print(f"PASS={passed}  WARN={warned}  FAIL={failed}  TOTAL={len(results)}")
