import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
root_dir = r"C:\vazus\knowledge\telegram_courses"

audio_files = []
video_files = []

for root, dirs, files in os.walk(root_dir):
    for f in files:
        ext = os.path.splitext(f)[1].lower()
        full_path = os.path.join(root, f)
        size = os.path.getsize(full_path)
        if ext in ('.oga', '.mp3', '.wav', '.m4a', '.flac'):
            audio_files.append((full_path, size))
        elif ext in ('.mp4', '.mkv', '.avi', '.mov', '.webm'):
            video_files.append((full_path, size))

print(f"Total audio files found: {len(audio_files)}")
print(f"Total video files found: {len(video_files)}")

print("\nSample Audio Files:")
for path, size in audio_files[:5]:
    print(f"  {path} ({size} bytes)")

print("\nSample Video Files:")
for path, size in video_files[:5]:
    print(f"  {path} ({size} bytes)")
