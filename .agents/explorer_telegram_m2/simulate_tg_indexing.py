import glob
import json
import os
import re
import sqlite3
import sys
from typing import Dict, List, Any

sys.stdout.reconfigure(encoding='utf-8')

tg_msg_dir = r"C:\vazus\knowledge\telegram_messages"
tg_crs_dir = r"C:\vazus\knowledge\telegram_courses"
db_path = r"C:\vazus\services\memory\vazus.db"

# 1. Load existing MediaScene nodes from vazus.db
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT id, name, properties FROM kg_nodes WHERE domain='multimodal_av' AND node_type='MediaScene'")
media_scenes = cursor.fetchall()
conn.close()

media_scene_map = {} # msg_id -> list of scene_ids
for sid, sname, props_str in media_scenes:
    try:
        props = json.loads(props_str)
        src = props.get("source_file", "")
        # Extract msg_id from source_file
        m = re.search(r'msg_?(\d+)', src, re.IGNORECASE)
        if not m:
            m = re.search(r'media_(\d+)', src, re.IGNORECASE)
        if m:
            mid = int(m.group(1))
            if mid not in media_scene_map:
                media_scene_map[mid] = []
            media_scene_map[mid].append(sid)
    except Exception:
        pass

print(f"Loaded {len(media_scenes)} MediaScene nodes from vazus.db.")
print(f"Mapped {len(media_scene_map)} unique msg_ids to MediaScenes.")

# 2. Parse all Telegram messages across files
jsonl_files = glob.glob(os.path.join(tg_msg_dir, "*.jsonl"))

total_msgs = 0
total_replies = 0
total_media_links = 0

for f in jsonl_files:
    fname = os.path.basename(f)
    ch_slug = re.sub(r'[^a-zA-Z0-9_]', '_', fname.replace('.jsonl', '')).lower()
    
    with open(f, 'r', encoding='utf-8') as jf:
        msgs = [json.loads(line) for line in jf if line.strip()]
        
    msg_dict = {m['id']: m for m in msgs}
    
    ch_replies = 0
    ch_media = 0
    
    for m in msgs:
        mid = m['id']
        txt = m.get('text', '')
        reply_to_id = m.get('reply_to_msg_id') or m.get('reply_to')
        
        # Fallback text regex for reply if not in json field
        if not reply_to_id:
            match = re.search(r'\[(?:ID|msg):\s*(\d+)\]', txt, re.IGNORECASE)
            if not match:
                match = re.search(r'^(?:Re|Ответ на msg|Ответ на|>>)\s*#?(\d+)', txt, re.IGNORECASE)
            if match:
                reply_to_id = int(match.group(1))
                
        if reply_to_id:
            ch_replies += 1
            
        # Check media link
        if mid in media_scene_map:
            ch_media += len(media_scene_map[mid])

    print(f"Channel '{fname}': msgs={len(msgs)}, replies={ch_replies}, media_scene_links={ch_media}")
    total_msgs += len(msgs)
    total_replies += ch_replies
    total_media_links += ch_media

print(f"\nTOTAL SUMMARY:")
print(f"  Files: {len(jsonl_files)}")
print(f"  Messages: {total_msgs}")
print(f"  Replies linked: {total_replies}")
print(f"  Media links created: {total_media_links}")
