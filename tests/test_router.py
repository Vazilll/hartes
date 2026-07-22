import sys
sys.path.insert(0, "C:/vazus")
from vazus_core.workers import router

query = "What is LeANN and how is it configured in our codebase?"
print("=== Running Unified Router Test ===")
res = router.run(query=query)

print("\n--- Final Router Synthesis ---")
print(res.get("result", "Error: No result"))
print(f"\nElapsed: {res.get('elapsed_sec')}s")
