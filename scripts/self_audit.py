#!/usr/bin/env python3
"""Self-audit: analyze myself for vulnerabilities using unified_search."""
import sys, json, time
sys.path.insert(0, "C:/vazus/pyenv/scripts")
from rlm_unified_worker import unified_search

queries = [
    {
        "id": "creds",
        "query": "API key token secret password credential",
        "search_web": False,
        "search_files": True,
        "search_code": False,
        "file_results": 50,
    },
    {
        "id": "security_config",
        "query": "security vulnerability exploit injection command",
        "search_web": False,
        "search_files": True,
        "search_code": False,
        "file_results": 30,
    },
    {
        "id": "config_issues",
        "query": "config.yaml hermes settings misconfiguration",
        "search_web": False,
        "search_files": True,
        "search_code": False,
        "file_results": 30,
    },
    {
        "id": "go_vulns",
        "query": "TODO FIXME HACK XXX BUG SECURITY",
        "search_web": False,
        "search_files": True,
        "search_code": False,
        "file_results": 30,
    },
    {
        "id": "dependency",
        "query": "CVE vulnerability package dependency npm pip go",
        "search_web": True,
        "search_files": True,
        "search_code": False,
        "web_results": 5,
        "file_results": 20,
    },
]

all_results = {}
for q in queries:
    t0 = time.time()
    print(f"\n--- [{q['id']}] {q['query'][:50]}...", flush=True)
    result = unified_search(q)
    elapsed = time.time() - t0
    print(f"    done in {elapsed:.1f}s: web={result['web_count']} files={result['file_count']} code={result['code_count']}", flush=True)
    all_results[q['id']] = result

# Save full results
with open("C:/vazus/pyenv/hermes-home/cache/self_audit_results.json", "w") as f:
    json.dump(all_results, f, ensure_ascii=False, default=str, indent=2)

print("\n\n=== SELF-AUDIT COMPLETE ===")
print(f"Results saved to cache/self_audit_results.json")

# Summary
for rid, r in all_results.items():
    files = [f.get('file','') for f in r.get('file_results',[])]
    print(f"\n[{rid}] Files found: {len(files)}")
    for f in files[:10]:
        print(f"  - {f}")
