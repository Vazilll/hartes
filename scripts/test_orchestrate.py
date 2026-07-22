import sys
sys.path.insert(0, 'C:/vazus/pyenv')
import io
sys.stderr = io.StringIO()  # suppress startup logs

from dnts_core.mcp_server import orchestrate_task, run_leann_async, spawn_workers
print("orchestrate_task: imported OK")

import json
r = orchestrate_task("search", '{"query": "test hybrid"}')
d = json.loads(r)
print("dispatched task_id:", d.get("task_id", "?")[:30])
print("status:", d.get("status"))

# Test unknown type
r2 = orchestrate_task("unknown_type")
d2 = json.loads(r2)
print("unknown type error:", d2.get("error", "?")[:50])
print("supported:", d2.get("supported"))
