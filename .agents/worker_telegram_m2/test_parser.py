import sys
import os
import glob
import json
import re

sys.stdout.reconfigure(encoding='utf-8')

messages_dir = "C:/vazus/knowledge/telegram_messages"
jsonl_files = glob.glob(os.path.join(messages_dir, "*.jsonl"))

print(f"Found {len(jsonl_files)} jsonl files.")

total_msgs = 0
for fpath in jsonl_files:
    fname = os.path.basename(fpath)
    count = 0
    reply_cnt = 0
    regex_reply_cnt = 0
    senders = set()
    with open(fpath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            count += 1
            text = str(data.get("text") or data.get("caption") or "")
            sender = data.get("sender") or data.get("from") or data.get("author") or ""
            if isinstance(sender, dict):
                sender = sender.get("name") or sender.get("first_name") or str(sender)
            senders.add(str(sender))
            
            # Check reply_to_msg_id
            reply_id = data.get("reply_to_msg_id") or data.get("reply_to")
            if isinstance(reply_id, dict):
                reply_id = reply_id.get("reply_to_msg_id") or reply_id.get("message_id")
            if reply_id:
                reply_cnt += 1
            else:
                # Check regex
                m = re.search(r'\[(?:ID|msg):\s*(\d+)\]', text, re.IGNORECASE)
                if not m:
                    m = re.search(r'^(?:Re|Ответ на|в ответ на)\s*#?(\d+)', text, re.IGNORECASE)
                if m:
                    regex_reply_cnt += 1
    total_msgs += count
    print(f"{fname}: {count} msgs, {len(senders)} senders, explicit replies: {reply_cnt}, regex replies: {regex_reply_cnt}")

print(f"Total messages across jsonl files: {total_msgs}")
