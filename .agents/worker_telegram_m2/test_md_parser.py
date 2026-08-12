import sys
import os
import glob
import re

sys.stdout.reconfigure(encoding='utf-8')

messages_dir = "C:/vazus/knowledge/telegram_messages"
md_files = glob.glob(os.path.join(messages_dir, "*.md"))

print(f"Found {len(md_files)} md files.")

for fpath in md_files:
    fname = os.path.basename(fpath)
    reply_refs = []
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()
        # look for reply patterns in header or body
        matches = re.findall(r'(\[ID:\s*(\d+)\]|\(в ответ на #?(\d+)\)|Re:\s*#?(\d+)|>.*?\n)', content, re.IGNORECASE)
        for m in matches[:5]:
            reply_refs.append(m[0].strip())
    print(f"{fname}: found {len(re.findall(r'### ', content))} msgs, {len(matches)} reply pattern matches.")
    if reply_refs:
        print("  Sample matches:", reply_refs)
