#!/usr/bin/env python3
import time
import sys
import os
import json
from pathlib import Path

# Setup paths
WORKSPACE = Path("C:/vazus/pyenv")
sys.path.insert(0, str(WORKSPACE))

from vazus_core import engine
from vazus_core import database as db

def wait_for_task(task_id: str, timeout_sec: int = 1800) -> dict:
    start_time = time.time()
    while time.time() - start_time < timeout_sec:
        task = db.get_task(task_id)
        if task and task["status"] in ("DONE", "ERROR"):
            return task
        time.sleep(2)
    raise TimeoutError(f"Task {task_id} timed out")

def extract_result_data(task: dict) -> str:
    if task["status"] == "ERROR":
        return f"ERROR: {task.get('error_text', 'Unknown error')}"
    
    result = task.get("result", {})
    if not result:
        return "No result data"
        
    data = result.get("data", result)
    if isinstance(data, dict):
        if "report" in data:
            return data["report"]
        if "result" in data:
            return data["result"]
        if "final_answer" in data:
            return data["final_answer"]
    return str(data)

def run_nexus(query: str):
    print(f"=== NEXUS Pipeline Starting ===")
    print(f"Query: {query}")
    
    # Phase 1: Parallel Search
    print("\n[Phase 1] Launching parallel Web and Local searches...")
    ldr_id = engine.submit_task("ldr", {"topic": query, "max_depth": 2})
    search_id = engine.submit_task("search", {"query": query, "limit": 15})
    
    print(f"  - LDR task: {ldr_id}")
    print(f"  - Search task: {search_id}")
    
    ldr_task = wait_for_task(ldr_id)
    print(f"  [OK] LDR finished with status: {ldr_task['status']}")
    
    search_task = wait_for_task(search_id)
    print(f"  [OK] Local Search finished with status: {search_task['status']}")
    
    print("\n[Phase 1] Parallel Search Completed.")
    
    # Phase 2: RLM Synthesis
    print("\n[Phase 2] Synthesizing results with RLM...")
    
    ldr_text = extract_result_data(ldr_task)
    search_text = extract_result_data(search_task)
    
    context = f"=== WEB RESEARCH (Google Search Grounding) ===\n{ldr_text}\n\n"
    context += f"=== LOCAL CODEBASE SEARCH (FTS5+CBM+LeANN) ===\n{search_text}\n"
    
    rlm_prompt = f"""
You are the NEXUS RLM synthesizer. Analyze the web research and local codebase search results below.
Query: {query}

Your tasks:
1. Synthesize the findings into a cohesive report.
2. Compare what's available online (Web) vs what's already implemented locally (Codebase).
3. Identify gaps in our current local implementation.
4. Provide a numbered list of concrete Action Items for improvement.
"""
    
    rlm_id = engine.submit_task("rlm", {
        "prompt": rlm_prompt,
        "context": context,
        "max_iterations": 3
    })
    print(f"  - RLM task: {rlm_id}")
    rlm_task = wait_for_task(rlm_id)
    print(f"  [OK] RLM finished with status: {rlm_task['status']}")
    
    # Phase 3: Output Generation
    print("\n[Phase 3] Generating Output & Report...")
    safe_query = "".join(c if c.isalnum() else "_" for c in query)[:30]
    report_path = WORKSPACE / f"nexus_report_{safe_query}.md"
    
    report_content = f"# NEXUS Research Report\n**Query:** {query}\n\n"
    report_content += extract_result_data(rlm_task)
        
    report_path.write_text(report_content, encoding="utf-8")
    print(f"  [OK] Report written to {report_path}")
    print(f"\n[Done] Pipeline execution completed successfully.")

if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "How to improve Python agentic workflows using Google Gemini and LangGraph?"
    run_nexus(q)
