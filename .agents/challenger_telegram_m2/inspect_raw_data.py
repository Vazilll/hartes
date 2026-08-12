import os
import sys
import json
import glob
import re

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

messages_dir = r"C:\vazus\knowledge\telegram_messages"
jsonl_files = glob.glob(os.path.join(messages_dir, "*.jsonl"))
md_files = glob.glob(os.path.join(messages_dir, "*.md"))

print(f"Found {len(jsonl_files)} jsonl files, {len(md_files)} md files.")

all_keys = set()
reply_related_keys = set()
sample_replies = []

for fpath in jsonl_files:
    fname = os.path.basename(fpath)
    count = 0
    reply_count = 0
    with open(fpath, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except Exception:
                continue
            count += 1
            all_keys.update(data.keys())
            for k in data.keys():
                if "reply" in k.lower():
                    reply_related_keys.add(k)
                    reply_count += 1
                    if len(sample_replies) < 5:
                        sample_replies.append((fname, k, data[k], data))
    print(f"JSONL {fname}: {count} messages, reply_count={reply_count}")

print(f"\nAll JSON keys across jsonl files: {sorted(list(all_keys))}")
print(f"Reply related keys: {reply_related_keys}")
print(f"Sample reply fields: {sample_replies}")

# Check MD files
md_reply_count = 0
for fpath in md_files:
    fname = os.path.basename(fpath)
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()
    matches = re.findall(r'\(в ответ на #?(\d+)\)', content, re.IGNORECASE)
    md_reply_count += len(matches)
    print(f"MD {fname}: {len(matches)} reply matches found with pattern '(в ответ на #ID)'")

print(f"Total MD reply matches across all md files: {md_reply_count}")
