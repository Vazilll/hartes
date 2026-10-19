import sys
import os
import json

# Setup PYTHONPATH to ensure vazus_core is available
sys.path.insert(0, "C:/vazus")
from vazus_core.workers import router

query = "Проанализируй собственную архитектуру (файлы vazus_core). На основе современных open source систем от Google и MIT, предложи ОДНО ключевое архитектурное улучшение, которое мы еще не внедрили. Детально опиши, почему оно важно и как оно улучшит стабильность."

print(f"Running self-audit with query: {query}")
result = router.run(query, task_id="self_audit_001")

print("\n\n" + "="*50)
print("FINAL AUDIT RESULT:")
print("="*50)
print(result["result"])

# Also print global memory to verify GameMaster logged it
print("\n[GameMaster Log]")
try:
    with open("C:/vazus/data/logs/global_memory.json", "r") as f:
        print(f.read())
except Exception as e:
    print("Could not read global memory:", e)
