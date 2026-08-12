import glob
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

tg_msg_dir = r"C:\vazus\knowledge\telegram_messages"
tg_crs_dir = r"C:\vazus\knowledge\telegram_courses"

jsonl_files = glob.glob(os.path.join(tg_msg_dir, "*.jsonl"))

print("=== 1. JSON KEYS AUDIT ===")
all_keys = set()
for f in jsonl_files:
    with open(f, 'r', encoding='utf-8') as jf:
        for line in jf:
            if line.strip():
                data = json.loads(line)
                all_keys.update(data.keys())
print("All JSON keys found across all files:", sorted(list(all_keys)))

print("\n=== 2. MEDIA FILES AUDIT ===")
media_files = []
for root, dirs, files in os.walk(tg_crs_dir):
    for file in files:
        rel_path = os.path.relpath(os.path.join(root, file), tg_crs_dir)
        media_files.append((file, rel_path, os.path.join(root, file)))

print(f"Total media files in telegram_courses: {len(media_files)}")
for file, rel, abs_p in media_files[:20]:
    print(f"  - {file} (rel: {rel})")

print("\n=== 3. MEDIA FILENAME MSG ID PARSING ===")
# Patterns to extract message ID from media filenames
# e.g. 2025-07-22 00-42-20_msg19.mp4 -> 19
# e.g. msg_104_record.mp4 -> 104
# e.g. media_174.oga -> 174
msg_id_from_media = {}
for file, rel, abs_p in media_files:
    m = re.search(r'msg_?(\d+)', file, re.IGNORECASE)
    if not m:
        m = re.search(r'media_(\d+)', file, re.IGNORECASE)
    if m:
        msg_id = int(m.group(1))
        msg_id_from_media[msg_id] = (file, rel)

print(f"Extracted msg_ids from media filenames: {len(msg_id_from_media)} files mapped.")
for msg_id, (file, rel) in list(msg_id_from_media.items())[:10]:
    print(f"  Msg ID {msg_id} -> {file}")

print("\n=== 4. MATCHING MEDIA MSG IDS WITH TELEGRAM MESSAGES ===")
all_msgs = {}
for f in jsonl_files:
    ch_name = os.path.basename(f).replace('.jsonl', '')
    with open(f, 'r', encoding='utf-8') as jf:
        for line in jf:
            if line.strip():
                d = json.loads(line)
                all_msgs[d['id']] = (ch_name, d)

print(f"Total unique telegram message IDs: {len(all_msgs)}")
matched_media_count = 0
for msg_id, (file, rel) in msg_id_from_media.items():
    if msg_id in all_msgs:
        matched_media_count += 1
        ch, msg = all_msgs[msg_id]
        print(f"MATCH! Media Msg ID {msg_id} ({file}) matches msg in channel '{ch}': text snippet '{msg['text'][:60]}...'")
    else:
        print(f"NO DIRECT MSG MATCH for Media Msg ID {msg_id} ({file})")

print(f"Total matched media files to messages: {matched_media_count} / {len(msg_id_from_media)}")
