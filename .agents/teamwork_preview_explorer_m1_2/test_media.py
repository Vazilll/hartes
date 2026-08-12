import os
import sys
import shutil
import glob
import subprocess

sys.stdout.reconfigure(encoding='utf-8')

print("=== CHECKING POTENTIAL FFMPEG PATHS AND MODULES ===")
# Check imageio ffmpeg path if imageio is installed
import imageio
print("Imageio version:", imageio.__version__)
try:
    import imageio_ffmpeg
    print("imageio_ffmpeg path:", imageio_ffmpeg.get_ffmpeg_exe())
except Exception as e:
    print("imageio_ffmpeg error:", e)

print("\n=== TESTING OPENCV ON VARIOUS VIDEO FORMATS (.mp4, .mov, .webm) ===")
import cv2

knowledge_dir = r"C:\vazus\knowledge"
video_files_by_ext = {}
for root, dirs, files in os.walk(knowledge_dir):
    for f in files:
        ext = os.path.splitext(f)[1].lower()
        if ext in [".mp4", ".mov", ".webm", ".mkv", ".avi"]:
            if ext not in video_files_by_ext:
                video_files_by_ext[ext] = []
            video_files_by_ext[ext].append(os.path.join(root, f))

for ext, file_list in video_files_by_ext.items():
    print(f"\nTesting {ext} (total {len(file_list)} files):")
    sample_files = file_list[:5]
    success_count = 0
    for vpath in sample_files:
        rel = os.path.relpath(vpath, knowledge_dir)
        cap = cv2.VideoCapture(vpath)
        if not cap.isOpened():
            print(f"  [FAIL] CV2 cannot open: {rel}")
            continue
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration_sec = frame_count / fps if fps > 0 else 0
        
        # Try reading frame at midpoint
        mid_frame_idx = frame_count // 2
        cap.set(cv2.CAP_PROP_POS_FRAMES, mid_frame_idx)
        ret, frame = cap.read()
        cap.release()
        
        if ret and frame is not None:
            success_count += 1
            print(f"  [OK] {rel} | {width}x{height} | {fps:.1f} fps | {duration_sec:.1f}s | shape={frame.shape}")
        else:
            print(f"  [FAIL_FRAME] {rel} | {width}x{height} | {fps:.1f} fps | frames={frame_count}")
    print(f"Ext {ext} sample success: {success_count}/{len(sample_files)}")
