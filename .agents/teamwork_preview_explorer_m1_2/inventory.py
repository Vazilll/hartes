import os
import sys
import shutil

print("=== PYTHON ENVIRONMENT ===")
print("Python Executable:", sys.executable)
print("Python Version:", sys.version)

mods = ["cv2", "PIL", "ffmpeg", "moviepy", "openvino", "whisper", "torch"]
for mod in mods:
    try:
        m = __import__(mod)
        ver = getattr(m, "__version__", "installed")
        print(f"Module {mod}: AVAILABLE ({ver})")
    except ImportError as e:
        print(f"Module {mod}: NOT AVAILABLE ({e})")

# Check binary tools in PATH
ffmpeg_bin = shutil.which("ffmpeg")
ffprobe_bin = shutil.which("ffprobe")
print(f"FFmpeg binary: {ffmpeg_bin}")
print(f"FFprobe binary: {ffprobe_bin}")

print("\n=== KNOWLEDGE MEDIA INVENTORY ===")
knowledge_dir = r"C:\vazus\knowledge"

file_list = []
ext_counts = {}
media_categories = {"video": 0, "audio": 0, "image": 0, "text_data": 0, "other": 0}

video_exts = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".flv"}
audio_exts = {".mp3", ".oga", ".m4a", ".wav", ".ogg", ".aac", ".flac", ".opus"}
image_exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
text_exts = {".json", ".jsonl", ".txt", ".md"}

for root, dirs, files in os.walk(knowledge_dir):
    for f in files:
        full_path = os.path.join(root, f)
        rel_path = os.path.relpath(full_path, knowledge_dir)
        ext = os.path.splitext(f)[1].lower()
        size_bytes = os.path.getsize(full_path)
        ext_counts[ext] = ext_counts.get(ext, 0) + 1
        
        cat = "other"
        if ext in video_exts:
            cat = "video"
        elif ext in audio_exts:
            cat = "audio"
        elif ext in image_exts:
            cat = "image"
        elif ext in text_exts:
            cat = "text_data"
            
        media_categories[cat] += 1
        file_list.append({
            "rel_path": rel_path,
            "ext": ext,
            "size": size_bytes,
            "cat": cat
        })

print(f"Total files in {knowledge_dir}: {len(file_list)}")
print("\nExtension breakdown:")
for ext, count in sorted(ext_counts.items(), key=lambda x: x[1], reverse=True):
    print(f"  {ext or '[no ext]'}: {count} files")

print("\nCategory breakdown:")
for cat, count in media_categories.items():
    print(f"  {cat}: {count} files")
