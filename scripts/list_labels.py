import subprocess
import json
import sys

# Reconfigure stdout to use UTF-8
sys.stdout.reconfigure(encoding='utf-8')

args = [
    r"C:\vazus\pyenv\bin\codebase-memory-mcp.exe",
    "cli",
    "query_graph",
    json.dumps({
        "project": "C-dnts-pyenv-gomcp",
        "query": "MATCH (n) WHERE n.name = 'projectIndexTool' RETURN n.name, n.file_path, labels(n) LIMIT 5"
    })
]
proc = subprocess.run(args, capture_output=True, text=True, encoding='utf-8')
try:
    data = json.loads(proc.stdout)
    print("Columns:", data.get("columns"))
    print("Rows:", data.get("rows"))
except Exception as e:
    print("Error:", e)
