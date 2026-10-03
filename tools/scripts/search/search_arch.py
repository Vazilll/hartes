import os
import sys
import json

sys.stdout.reconfigure(encoding='utf-8')

brain_dir = r"C:\Users\Vaz\.gemini\antigravity\brain"

for cdir in os.listdir(brain_dir):
    tpath = os.path.join(brain_dir, cdir, ".system_generated", "logs", "transcript.jsonl")
    if os.path.exists(tpath):
        try:
            with open(tpath, "r", encoding="utf-8") as f:
                for line in f:
                    if "05_Computer_Architecture" in line:
                        d = json.loads(line)
                        if d.get("type") == "USER_INPUT":
                            print(f"[{cdir[:8]}] USER: {d.get('content', '')[:300].strip()}")
                            break
        except Exception:
            pass
