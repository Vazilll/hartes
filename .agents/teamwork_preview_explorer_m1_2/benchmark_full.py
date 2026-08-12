import os
import sys
import time
import hashlib
import cv2
from PIL import Image, ImageDraw

sys.stdout.reconfigure(encoding='utf-8')

knowledge_dir = r"C:\vazus\knowledge"
thumbnails_dir = r"C:\vazus\knowledge\.thumbnails"

os.makedirs(thumbnails_dir, exist_ok=True)

def generate_scene_thumbnail(media_path: str, start_sec: float, end_sec: float, target_w: int = 320, target_h: int = 180, quality: int = 85) -> str:
    rel_path = os.path.relpath(media_path, knowledge_dir)
    ext = os.path.splitext(media_path)[1].lower()
    
    # Calculate midpoint timestamp for representative scene preview
    mid_sec = start_sec + (end_sec - start_sec) / 2.0
    
    hash_key = hashlib.sha256(f"{rel_path}:{start_sec:.2f}:{end_sec:.2f}".encode('utf-8')).hexdigest()[:12]
    
    # Check if media is video
    if ext in [".mp4", ".mov", ".webm", ".mkv", ".avi"]:
        cap = cv2.VideoCapture(media_path)
        if cap.isOpened():
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if fps > 0 and frame_count > 0:
                target_frame = int(mid_sec * fps)
                target_frame = max(0, min(target_frame, frame_count - 1))
                cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
                ret, frame = cap.read()
                cap.release()
                
                if ret and frame is not None:
                    # Convert BGR to RGB
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(frame_rgb)
                    
                    # Aspect ratio resize & letterbox
                    img_w, img_h = img.size
                    scale = min(target_w / img_w, target_h / img_h)
                    new_w = max(1, int(img_w * scale))
                    new_h = max(1, int(img_h * scale))
                    
                    img_resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                    canvas = Image.new("RGB", (target_w, target_h), (18, 18, 24))
                    canvas.paste(img_resized, ((target_w - new_w) // 2, (target_h - new_h) // 2))
                    
                    out_path = os.path.join(thumbnails_dir, f"thumb_v_{hash_key}.jpg")
                    canvas.save(out_path, "JPEG", quality=quality)
                    return out_path
        cap.release()
        
        # Fallback for unreadable video
        canvas = Image.new("RGB", (target_w, target_h), (36, 24, 24))
        draw = ImageDraw.Draw(canvas)
        draw.rectangle([(10, 10), (120, 30)], fill=(220, 38, 38))
        draw.text((15, 12), "VIDEO UNREADABLE", fill=(255, 255, 255))
        out_path = os.path.join(thumbnails_dir, f"thumb_v_err_{hash_key}.jpg")
        canvas.save(out_path, "JPEG", quality=quality)
        return out_path

    # Audio or other media format fallback
    canvas = Image.new("RGB", (target_w, target_h), (24, 28, 36))
    draw = ImageDraw.Draw(canvas)
    center_y = target_h // 2
    bars = 28
    spacing = 7
    start_x = (target_w - (bars * spacing)) // 2
    h_val = int(hashlib.md5(rel_path.encode('utf-8')).hexdigest(), 16)
    
    for i in range(bars):
        amp = ((h_val >> (i % 24)) & 0x1F) + 12
        x = start_x + (i * spacing)
        draw.line([(x, center_y - amp), (x, center_y + amp)], fill=(99, 102, 241), width=4)
        
    draw.rectangle([(10, 10), (70, 30)], fill=(79, 70, 229))
    draw.text((15, 12), "AUDIO", fill=(255, 255, 255))
    out_path = os.path.join(thumbnails_dir, f"thumb_a_{hash_key}.jpg")
    canvas.save(out_path, "JPEG", quality=quality)
    return out_path

print("=== BENCHMARKING THUMBNAIL GENERATION ON ALL KNOWLEDGE MEDIA (FIRST 50 FILES) ===")

all_media_files = []
for root, dirs, files in os.walk(knowledge_dir):
    for f in files:
        ext = os.path.splitext(f)[1].lower()
        if ext in [".mp4", ".mov", ".webm", ".mp3", ".oga", ".m4a", ".ogg"]:
            all_media_files.append(os.path.join(root, f))

print(f"Total video/audio files found: {len(all_media_files)}")

sample_batch = all_media_files[:50]
t0 = time.time()
results = {"video_ok": 0, "video_err": 0, "audio": 0}

for idx, mpath in enumerate(sample_batch):
    # Simulate a 1-3 min scene (0 to 120 sec)
    out_file = generate_scene_thumbnail(mpath, start_sec=0.0, end_sec=120.0)
    if "thumb_v_err_" in out_file:
        results["video_err"] += 1
    elif "thumb_v_" in out_file:
        results["video_ok"] += 1
    else:
        results["audio"] += 1

t1 = time.time()
print(f"Processed 50 media files in {t1-t0:.3f} seconds ({ (t1-t0)/50:.3f}s per media file)")
print(f"Results summary: {results}")

