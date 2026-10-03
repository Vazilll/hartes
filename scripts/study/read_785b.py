import os
import sys
import json

sys.stdout.reconfigure(encoding='utf-8')

tpath = r"C:\Users\Vaz\.gemini\antigravity\brain\785b010e-f668-41ec-b485-07a545d8234e\.system_generated\logs\transcript.jsonl"
with open(tpath, "r", encoding="utf-8") as f:
    for line in f:
        d = json.loads(line)
        if d.get("type") == "USER_INPUT":
            print(f"=== STEP {d.get('step_index')} ===")
            print(d.get("content"))
