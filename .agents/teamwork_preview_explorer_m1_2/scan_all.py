import os
import sys
import json
import cv2
from PIL import Image

sys.stdout.reconfigure(encoding='utf-8')

knowledge_dir = r"C:\vazus\knowledge"

folders = {}
ext_summary = {}

for root, dirs, files in os.walk(knowledge_dir):
    rel_dir = os.path.relpath(root, knowledge_dir)
    if rel_dir == ".":
        rel_dir = "root"
    
    dir_info = {
        "count": len(files),
        "types": {}
    }
    
    for f in files:
        ext = os.path.splitext(f)[1].lower()
        ext_summary[ext] = ext_summary.get(ext, 0) + 1
        dir_info["types"][ext] = dir_info["types"].get(ext, 0) + 1
        
    folders[rel_dir] = dir_info

print("=== DIRECTORY STRUCTURE SUMMARY ===")
for folder, info in sorted(folders.items()):
    print(f"\nDirectory: {folder}")
    print(f"  Total files: {info['count']}")
    for ext, count in sorted(info['types'].items(), key=lambda x: x[1], reverse=True):
        print(f"    {ext or '[no ext]'}: {count}")

print("\n=== DETAILED VIDEO ANALYSIS ACROSS ALL COURSES ===")
all_videos = []
for root, dirs, files in os.walk(knowledge_dir):
    for f in files:
        ext = os.path.splitext(f)[1].lower()
        if ext in [".mp4", ".mov", ".webm", ".mkv", ".avi"]:
            full_path = os.path.join(root, f)
            rel_path = os.path.relpath(full_path, knowledge_dir)
            all_videos.append((rel_path, full_path, ext))

print(f"Total video files: {len(all_videos)}")

cv2_open_ok = 0
cv2_open_fail = 0
resolutions = {}
durations = []

for rel_path, full_path, ext in all_videos:
    cap = cv2.VideoCapture(full_path)
    if cap.isOpened():
        cv2_open_ok += 1
        fps = cap.get(cv2.CAP_PROP_FPS)
        frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        dur = frames / fps if fps > 0 else 0
        durations.append(dur)
        res_key = f"{w}x{h}"
        resolutions[res_key] = resolutions.get(res_key, 0) + 1
    else:
        cv2_open_fail += 1
        print(f"FAIL to open: {rel_path}")
    cap.release()

print(f"CV2 Open Success: {cv2_open_ok}/{len(all_videos)}")
print(f"CV2 Open Fail: {cv2_open_fail}/{len(all_videos)}")

print("\nVideo Resolutions breakdown:")
for res, count in sorted(resolutions.items(), key=lambda x: x[1], reverse=True):
    print(f"  {res}: {count} videos")

if durations:
    avg_dur = sum(durations) / len(durations)
    max_dur = max(durations)
    min_dur = min(durations)
    print(f"\nVideo Durations: Min={min_dur:.1f}s, Max={max_dur:.1f}s ({max_dur/60:.1f}m), Avg={avg_dur:.1f}s ({avg_dur/60:.1f}m)")

print("\n=== AUDIO FILES ANALYSIS (.mp3, .oga, .m4a, .ogg) ===")
all_audio = []
for root, dirs, files in os.walk(knowledge_dir):
    for f in files:
        ext = os.path.splitext(f)[1].lower()
        if ext in [".mp3", ".oga", ".m4a", ".ogg", ".wav", ".flac", ".opus", ".aac"]:
            full_path = os.path.join(root, f)
            rel_path = os.path.relpath(full_path, knowledge_dir)
            all_audio.append((rel_path, full_path, ext))

print(f"Total audio files: {len(all_audio)}")
audio_exts = {}
for rel_path, full_path, ext in all_audio:
    audio_exts[ext] = audio_exts.get(ext, 0) + 1

for ext, count in audio_exts.items():
    print(f"  {ext}: {count} audio files")

