import sys
import sqlite3
import json
import os
import re

sys.stdout.reconfigure(encoding='utf-8')
conn = sqlite3.connect('C:/vazus/vazus.db')
rows = conn.execute("SELECT id, name, properties FROM kg_nodes WHERE domain='multimodal_av'").fetchall()
print(f'Total MediaScene nodes in vazus.db: {len(rows)}')
matched_msg_ids = []
for r in rows:
    p = json.loads(r[2]) if r[2] else {}
    sf = p.get('source_file', '')
    fn = os.path.basename(sf)
    m = re.search(r'(?:_msg|msg_|media_|video_msg|msg)(\d+)', fn, re.IGNORECASE)
    if m:
        matched_msg_ids.append((r[0], fn, int(m.group(1))))
print(f'MediaScenes with msg_id extracted: {len(matched_msg_ids)}')
print('Sample matched:', matched_msg_ids[:10])

# Also check physical files in C:/vazus/knowledge/telegram_courses
media_files = []
for root, dirs, files in os.walk('C:/vazus/knowledge/telegram_courses'):
    for f in files:
        if f.lower().endswith(('.mp4', '.m4a', '.mp3', '.oga', '.ogg', '.wav', '.mov', '.jpg', '.png', '.jpeg')):
            media_files.append((os.path.join(root, f), f))
print(f'Total physical media files in telegram_courses: {len(media_files)}')

media_matched = []
for full_path, fn in media_files:
    m = re.search(r'(?:_msg|msg_|media_|video_msg|msg)(\d+)', fn, re.IGNORECASE)
    if m:
        media_matched.append((fn, int(m.group(1)), full_path))
print(f'Physical media files with msg_id extracted: {len(media_matched)}')
print('Sample physical matched:', media_matched[:10])
conn.close()
