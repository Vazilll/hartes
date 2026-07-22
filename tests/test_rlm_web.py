import sys
sys.path.insert(0, "C:/vazus")
from vazus_core.workers import rlm

query = "Что мы можем улучшить в нашей системе NEXUS (multi-agent, FTS5+LeANN hybrid search, RLM reasoning) на основе свежих данных и архитектур от Google Research? Используй инструмент web_search."
print("=== Running RLM Web Grounding ===")
res = rlm.run(task_id="web_test_1", prompt=query, max_iterations=4, max_depth=2)

print("\n--- Final Synthesis ---")
print(res.get("result", "Error: No result"))
print(f"\nElapsed: {res.get('elapsed_sec')}s")
