import os
import sys
import json
import glob
import re

sys.stdout.reconfigure(encoding='utf-8')

messages_dir = r"C:\vazus\knowledge\telegram_messages"
jsonl_files = glob.glob(os.path.join(messages_dir, "*.jsonl"))

quotes = []
re_matches = []
brackets = []

for fpath in jsonl_files:
    fname = os.path.basename(fpath)
    with open(fpath, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except Exception:
                continue
            text = str(data.get("text", ""))
            if text.startswith(">"):
                quotes.append((fname, data.get("id"), text[:100]))
            if re.search(r'\b(?:Re|Ответ|ответ|reply|ID|msg)\b', text, re.IGNORECASE):
                re_matches.append((fname, data.get("id"), text[:100]))
            if "[" in text and "]" in text:
                brackets.append((fname, data.get("id"), text[:100]))

print(f"Quotes count starting with '>': {len(quotes)}")
print(f"Re/Ответ/reply/ID/msg keyword count: {len(re_matches)}")
print(f"Brackets '[' and ']' count: {len(brackets)}")

if quotes:
    print(f"Sample quotes: {quotes[:3]}")
if re_matches:
    print(f"Sample re_matches: {re_matches[:5]}")
