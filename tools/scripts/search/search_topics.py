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
                    if any(w in line for w in ["счислен", "СДНФ", "СКНФ", "СЛАУ", "МДНФ", "Карно", "логическ"]):
                        if "USER_INPUT" in line:
                            d = json.loads(line)
                            content = d.get("content", "")
                            print(f"[{cdir[:8]}] USER: {content[:200].strip()}")
        except Exception as e:
            pass
