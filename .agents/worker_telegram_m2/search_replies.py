import sys
import os
import glob
import json
import re

sys.stdout.reconfigure(encoding='utf-8')

messages_dir = "C:/vazus/knowledge/telegram_messages"
jsonl_files = glob.glob(os.path.join(messages_dir, "*.jsonl"))

for fpath in jsonl_files:
    fname = os.path.basename(fpath)
    matched = []
    with open(fpath, "r", encoding="utf-8") as f:
        for line in f:
            data = json.loads(line)
            msg_id = data.get("id")
            text = str(data.get("text") or "")

            # Check various reply patterns
            m1 = re.search(r'\[(?:ID|msg):\s*(\d+)\]', text, re.IGNORECASE)
            m2 = re.search(r'(?:Re|Ответ|в ответ|reply|отвечая|на post|на пост)\s*(?:на)?\s*#?(\d+)', text, re.IGNORECASE)
            m3 = re.search(r'#(\d{2,6})\b', text)
            m4 = re.search(r'(?:t\.me|telegram\.me)/[a-zA-Z0-9_]+/\s*(\d+)', text)
            
            pats = []
            if m1: pats.append(('m1', m1.group(1)))
            if m2: pats.append(('m2', m2.group(1)))
            if m3: pats.append(('m3', m3.group(1)))
            if m4: pats.append(('m4', m4.group(1)))
            
            if pats:
                matched.append((msg_id, pats, text[:60]))
    print(f"{fname}: found {len(matched)} messages with potential reply patterns.")
    if matched:
        print("  Sample:", matched[:5])
