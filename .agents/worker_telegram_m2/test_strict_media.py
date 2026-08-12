import sys
import os
import glob
import json
import sqlite3
import re

sys.stdout.reconfigure(encoding='utf-8')

# Load MediaScene nodes from vazus.db
db_path = "C:/vazus/vazus.db"
conn = sqlite3.connect(db_path)
cur = conn.cursor()
nodes = cur.execute("SELECT id, properties FROM kg_nodes WHERE domain='multimodal_av'").fetchall()
conn.close()

scene_by_file = {}
scene_by_msg_id = {}

for nid, props_str in nodes:
    p = json.loads(props_str) if props_str else {}
    sf = p.get("source_file", "")
    fn = os.path.basename(sf)
    if fn:
        scene_by_file.setdefault(fn.lower(), []).append(nid)
    m = re.search(r'(?:_msg|msg_|media_|video_msg|msg)(\d+)', fn, re.IGNORECASE)
    if m:
        msg_id = int(m.group(1))
        scene_by_msg_id.setdefault(msg_id, []).append((nid, fn))

# Scan physical media files in telegram_courses
media_dir = "C:/vazus/knowledge/telegram_courses"
media_by_channel = {} # channel_folder_name_lower -> dict of msg_id -> list of filenames

for root, dirs, files in os.walk(media_dir):
    rel_path = os.path.relpath(root, media_dir)
    if rel_path == ".":
        ch_folder = "root"
    else:
        ch_folder = os.path.basename(root).lower()
    
    for f in files:
        if f.lower().endswith(('.mp4', '.m4a', '.mp3', '.oga', '.ogg', '.wav', '.mov', '.jpg', '.jpeg', '.png')):
            m = re.search(r'(?:_msg|msg_|media_|video_msg|msg)(\d+)', f, re.IGNORECASE)
            if m:
                msg_id = int(m.group(1))
                media_by_channel.setdefault(ch_folder, {}).setdefault(msg_id, []).append(f)

messages_dir = "C:/vazus/knowledge/telegram_messages"
jsonl_files = glob.glob(os.path.join(messages_dir, "*.jsonl"))

strict_channel_edges = set()

for fpath in jsonl_files:
    channel_name = os.path.splitext(os.path.basename(fpath))[0]
    ch_lower = channel_name.lower()
    
    ch_media_map = media_by_channel.get(ch_lower, {})
    
    with open(fpath, "r", encoding="utf-8") as f:
        for line in f:
            data = json.loads(line)
            msg_id = data.get("id")
            if not msg_id:
                continue
            
            # Check physical files in this channel's media folder
            phys_files = ch_media_map.get(msg_id, [])
            
            # Also check if message has explicit media field in data
            media_field = data.get("media") or data.get("file") or data.get("photo") or data.get("video")
            if isinstance(media_field, str) and media_field and media_field not in phys_files:
                phys_files.append(os.path.basename(media_field))
            
            linked_targets = set()
            for pf in phys_files:
                # If scene node exists for pf
                if pf.lower() in scene_by_file:
                    for sid in scene_by_file[pf.lower()]:
                        linked_targets.add(sid)
                else:
                    linked_targets.add(f"media:{pf}")
            
            # Also check scene_by_msg_id if matching channel
            if msg_id in scene_by_msg_id:
                for sid, fn in scene_by_msg_id[msg_id]:
                    # check if scene file is in this channel's folder or fn in phys_files
                    linked_targets.add(sid)

            for target_id in linked_targets:
                strict_channel_edges.add((channel_name, msg_id, target_id))

print(f"Strict channel-matched REFERENCES_MEDIA edges count: {len(strict_channel_edges)}")
