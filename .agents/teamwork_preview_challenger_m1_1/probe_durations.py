import os
import sys
import cv2

sys.stdout.reconfigure(encoding='utf-8')
root_dir = r"C:\vazus\knowledge\telegram_courses"

files_to_probe = []
for root, dirs, files in os.walk(root_dir):
    for f in files:
        ext = os.path.splitext(f)[1].lower()
        if ext in ('.mp4', '.oga', '.mp3'):
            files_to_probe.append(os.path.join(root, f))

print(f"Total media files: {len(files_to_probe)}")

# Find video duration using cv2
for p in files_to_probe:
    ext = os.path.splitext(p)[1].lower()
    if ext == '.mp4':
        cap = cv2.VideoCapture(p)
        if cap.isOpened():
            fps = cap.get(cv2.CAP_PROP_FPS)
            frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            dur = frames / fps if fps > 0 else 0
            size_mb = os.path.getsize(p) / (1024 * 1024)
            if 30 <= dur <= 600: # 30s to 10 min
                print(f"Video: {os.path.basename(p)} | Size: {size_mb:.1f} MB | FPS: {fps:.1f} | Duration: {dur:.1f}s | Path: {p}")
        cap.release()
