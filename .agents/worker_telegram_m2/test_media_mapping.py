import sys
import os
import sqlite3
import json
import re
import glob

sys.stdout.reconfigure(encoding='utf-8')

# 1. Query MediaScene nodes from vazus.db
db_path = "C:/vazus/vazus.db"
conn = sqlite3.connect(db_path)
cur = conn.cursor()
nodes = cur.execute("SELECT id, name, properties FROM kg_nodes WHERE domain='multimodal_av'").fetchall()
conn.close()

print(f"Total MediaScene nodes in DB: {len(nodes)}")

# Build lookup: filename -> list of scene_ids, and msg_id -> list of scene_ids
scene_by_file = {}
scene_by_msg_id = {}

for nid, name, props_str in nodes:
    p = json.loads(props_str) if props_str else {}
    sf = p.get("source_file", "")
    fn = os.path.basename(sf)
    if fn:
        scene_by_file.setdefault(fn.lower(), []).append(nid)
    
    # Try regex on filename
    m = re.search(r'(?:_msg|msg_|media_|video_msg|msg)(\d+)', fn, re.IGNORECASE)
    if m:
        msg_id = int(m.group(1))
        scene_by_msg_id.setdefault(msg_id, []).append((nid, fn))

print(f"Unique MediaScene filenames: {len(scene_by_file)}")
print(f"Message IDs mapped in MediaScene filenames: {len(scene_by_msg_id)}")

# 2. Scan physical media files in telegram_courses
media_dir = "C:/vazus/knowledge/telegram_courses"
course_media_by_channel = {}

for root, dirs, files in os.walk(media_dir):
    rel_root = os.path.relpath(root, media_dir)
    channel_dir_name = os.path.basename(root) if rel_root != "." else ""
    for f in files:
        if f.lower().endswith(('.mp4', '.m4a', '.mp3', '.oga', '.ogg', '.wav', '.mov', '.jpg', '.jpeg', '.png')):
            full_p = os.path.join(root, f)
            m = re.search(r'(?:_msg|msg_|media_|video_msg|msg)(\d+)', f, re.IGNORECASE)
            msg_id = int(m.group(1)) if m else None
            course_media_by_channel.setdefault(channel_dir_name, []).append({
                "filename": f,
                "msg_id": msg_id,
                "full_path": full_p
            })

print("\nCourse media breakdown by channel folder:")
for ch, items in course_media_by_channel.items():
    with_msg_id = [i for i in items if i["msg_id"] is not None]
    print(f"  Channel folder '{ch}': {len(items)} files total, {len(with_msg_id)} with msg_id extracted.")

