import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, "C:/vazus/pyenv")
from dnts_core.workers import router

query = "Deeply analyze your own architecture: Unified Grounding Router, Reciprocal Rank Fusion, LeANN local vector search, Google GenAI web grounding, and RLM synthesis. As the core agent, what capabilities do you currently lack? What are you dissatisfied with in your own design? List specific technical limitations."

print("=== Running Introspection Task ===")
res = router.run(query=query)

print("\n--- Introspection Results ---")
print(res.get("result", "Error: No result"))
