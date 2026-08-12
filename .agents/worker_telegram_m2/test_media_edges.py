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

# Build map: (channel_folder_lower, msg_id) -> list of scene_ids
# and (filename_lower) -> list of scene_ids
# and msg_id -> list of scene_ids
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
media_by_channel_msg = {} # (channel_lower, msg_id) -> list of filenames

for root, dirs, files in os.walk(media_dir):
    ch_folder = os.path.basename(root).lower()
    for f in files:
        if f.lower().endswith(('.mp4', '.m4a', '.mp3', '.oga', '.ogg', '.wav', '.mov', '.jpg', '.jpeg', '.png')):
            m = re.search(r'(?:_msg|msg_|media_|video_msg|msg)(\d+)', f, re.IGNORECASE)
            if m:
                msg_id = int(m.group(1))
                media_by_channel_msg.setdefault((ch_folder, msg_id), []).append(f)
                media_by_channel_msg.setdefault(msg_id, []).append(f)

# Load messages from jsonl files
messages_dir = "C:/vazus/knowledge/telegram_messages"
jsonl_files = glob.glob(os.path.join(messages_dir, "*.jsonl"))

total_media_edges = 0
unique_edges = set()

for fpath in jsonl_files:
    channel_name = os.path.splitext(os.path.basename(fpath))[0]
    ch_lower = channel_name.lower()
    
    with open(fpath, "r", encoding="utf-8") as f:
        for line in f:
            data = json.loads(line)
            msg_id = data.get("id")
            if not msg_id:
                continue
            
            # Find matching MediaScene nodes
            linked_scenes = set()
            # 1. Check if scene filename matches physical files for this channel + msg_id
            phys_files = media_by_channel_msg.get((ch_lower, msg_id), []) or media_by_channel_msg.get(msg_id, [])
            for pf in phys_files:
                if pf.lower() in scene_by_file:
                    for sid in scene_by_file[pf.lower()]:
                        linked_scenes.add((sid, pf))
            
            # 2. Check scene_by_msg_id if any scene has this msg_id in filename
            if msg_id in scene_by_msg_id:
                for sid, fn in scene_by_msg_id[msg_id]:
                    linked_scenes.add((sid, fn))
            
            if linked_scenes:
                for sid, fn in linked_scenes:
                    unique_edges.add((channel_name, msg_id, sid, fn))
            else:
                # Fallback to physical media node media:<filename> if physical files exist
                for pf in phys_files:
                    unique_edges.add((channel_name, msg_id, f"media:{pf}", pf))

print(f"Total REFERENCES_MEDIA edges generated: {len(unique_edges)}")
print("Sample REFERENCES_MEDIA edges:")
for item in list(unique_edges)[:10]:
    print(" ", item)
