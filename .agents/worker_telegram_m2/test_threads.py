import sys
import os
import glob
import json
import re

sys.stdout.reconfigure(encoding='utf-8')

messages_dir = "C:/vazus/knowledge/telegram_messages"
jsonl_files = glob.glob(os.path.join(messages_dir, "*.jsonl"))

total_msgs = 0
total_replies_linked = 0

for fpath in jsonl_files:
    channel_name = os.path.splitext(os.path.basename(fpath))[0]
    
    # 1. Load messages and sort ascending by id
    raw_msgs = []
    with open(fpath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                data = json.loads(line)
                raw_msgs.append(data)
                
    raw_msgs.sort(key=lambda x: int(x.get("id", 0)))
    
    msgs_by_id = {}
    parsed_msgs = []
    
    for item in raw_msgs:
        msg_id = int(item["id"])
        text = str(item.get("text") or item.get("caption") or "")
        sender = item.get("sender") or item.get("from") or item.get("author") or "Пользователь"
        if isinstance(sender, dict):
            sender = sender.get("name") or sender.get("first_name") or "Пользователь"
        date = str(item.get("date", ""))
        
        # Explicit reply_to_msg_id
        parent_id = item.get("reply_to_msg_id") or item.get("reply_to")
        if isinstance(parent_id, dict):
            parent_id = parent_id.get("reply_to_msg_id") or parent_id.get("message_id")
        if parent_id is not None:
            try:
                parent_id = int(parent_id)
            except (ValueError, TypeError):
                parent_id = None
                
        # Regex fallback if parent_id not set
        if parent_id is None and text:
            m = re.search(r'\[(?:ID|msg):\s*(\d+)\]', text, re.IGNORECASE)
            if not m:
                m = re.search(r'^(?:Re|Ответ на|в ответ на)\s*#?(\d+)', text, re.IGNORECASE)
            if m:
                try:
                    parent_id = int(m.group(1))
                except (ValueError, TypeError):
                    parent_id = None
                    
        # Quoting fallback if text starts with >
        if parent_id is None and text.startswith(">"):
            # try fuzzy match against recent preceding messages within 50 msgs window
            quote_line = text.split("\n")[0].lstrip("> ").strip().lower()
            if len(quote_line) > 10:
                recent = parsed_msgs[-50:]
                for prev in reversed(recent):
                    if quote_line[:30] in prev["text"].lower():
                        parent_id = prev["msg_id"]
                        break
                        
        msg_record = {
            "msg_id": msg_id,
            "sender": sender,
            "date": date,
            "text": text,
            "parent_id": parent_id,
            "root_msg_id": msg_id,
            "reply_depth": 0,
            "is_thread_root": True,
            "child_ids": []
        }
        
        # Resolve parent if parent_id exists in msgs_by_id
        if parent_id is not None and parent_id in msgs_by_id:
            parent_node = msgs_by_id[parent_id]
            msg_record["is_thread_root"] = False
            msg_record["root_msg_id"] = parent_node["root_msg_id"]
            msg_record["reply_depth"] = parent_node["reply_depth"] + 1
            parent_node["child_ids"].append(msg_id)
            total_replies_linked += 1
            
        msgs_by_id[msg_id] = msg_record
        parsed_msgs.append(msg_record)
        
    total_msgs += len(parsed_msgs)
    print(f"Channel '{channel_name}': {len(parsed_msgs)} msgs, replies linked: {sum(1 for m in parsed_msgs if not m['is_thread_root'])}")

print(f"Total msgs: {total_msgs}, total replies linked: {total_replies_linked}")
