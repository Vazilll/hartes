import os
import sys
import sqlite3
import json

sys.stdout.reconfigure(encoding='utf-8')

tc_dir = r"C:\vazus\knowledge\telegram_courses"
tb_dir = r"C:\vazus\knowledge\.thumbnails"

tc_files = []
if os.path.exists(tc_dir):
    for root, dirs, files in os.walk(tc_dir):
        for f in files:
            full_path = os.path.join(root, f)
            tc_files.append((full_path, os.path.getsize(full_path)))

print(f"telegram_courses total files: {len(tc_files)}")
for path, size in tc_files[:15]:
    print(f"  {os.path.relpath(path, tc_dir)} ({size} bytes)")
if len(tc_files) > 15:
    print(f"  ... and {len(tc_files)-15} more files")

tb_files = []
if os.path.exists(tb_dir):
    for root, dirs, files in os.walk(tb_dir):
        for f in files:
            full_path = os.path.join(root, f)
            tb_files.append((full_path, os.path.getsize(full_path)))

print(f"\n.thumbnails total files: {len(tb_files)}")
for path, size in tb_files[:15]:
    print(f"  {os.path.relpath(path, tb_dir)} ({size} bytes)")
if len(tb_files) > 15:
    print(f"  ... and {len(tb_files)-15} more files")

conn = sqlite3.connect(r"C:\vazus\vazus.db")
cur = conn.cursor()
nodes = cur.execute("SELECT id, properties FROM kg_nodes WHERE node_type = 'MediaScene'").fetchall()
print(f"\nMediaScene nodes count in DB: {len(nodes)}")

found_thumbnails = 0
missing_thumbnails = 0
found_videos = 0
missing_videos = 0

sample_sources = set()
sample_thumbs = set()

for node_id, props_str in nodes:
    if not props_str:
        continue
    props = json.loads(props_str)
    src_file = props.get("source_file")
    thumb_path = props.get("thumbnail_path")
    if src_file:
        sample_sources.add(src_file)
        if os.path.exists(src_file):
            found_videos += 1
        else:
            missing_videos += 1
    if thumb_path:
        sample_thumbs.add(thumb_path)
        if os.path.exists(thumb_path):
            found_thumbnails += 1
        else:
            missing_thumbnails += 1

print(f"MediaScene video verification: {found_videos} found, {missing_videos} missing (unique source files referenced: {len(sample_sources)})")
print(f"MediaScene thumbnail verification: {found_thumbnails} found, {missing_thumbnails} missing (unique thumbs referenced: {len(sample_thumbs)})")

print("\nSample source files referenced in DB:")
for s in list(sample_sources)[:5]:
    print(f"  {s} (exists: {os.path.exists(s)})")

print("\nSample thumbnail paths referenced in DB:")
for t in list(sample_thumbs)[:5]:
    print(f"  {t} (exists: {os.path.exists(t)})")
