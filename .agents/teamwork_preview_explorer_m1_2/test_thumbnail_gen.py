import os
import sys
import time
import hashlib
import cv2
from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding='utf-8')

knowledge_dir = r"C:\vazus\knowledge"
thumbnails_dir = r"C:\vazus\knowledge\.thumbnails"

os.makedirs(thumbnails_dir, exist_ok=True)
print(f"Thumbnails directory created/verified: {thumbnails_dir}")

def generate_video_thumbnail_cv2(video_path: str, timestamp_sec: float, target_w: int = 320, target_h: int = 180, quality: int = 85) -> str:
    """Extract a thumbnail from video using OpenCV at timestamp_sec, resized & padded to target_w x target_h."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None
    
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        cap.release()
        return None
    
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    target_frame = int(timestamp_sec * fps)
    target_frame = max(0, min(target_frame, frame_count - 1))
    
    # Try setting frame index
    cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
    ret, frame = cap.read()
    cap.release()
    
    if not ret or frame is None:
        return None
    
    # Convert BGR (OpenCV) to RGB (PIL)
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    img = Image.fromarray(frame_rgb)
    
    # Resize preserving aspect ratio with letterboxing or crop
    img_w, img_h = img.size
    scale = min(target_w / img_w, target_h / img_h)
    new_w = max(1, int(img_w * scale))
    new_h = max(1, int(img_h * scale))
    
    img_resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    
    # Create dark background canvas
    canvas = Image.new("RGB", (target_w, target_h), (18, 18, 24))
    paste_x = (target_w - new_w) // 2
    paste_y = (target_h - new_h) // 2
    canvas.paste(img_resized, (paste_x, paste_y))
    
    # Determine unique thumbnail filename using hash of relative path + timestamp
    rel_path = os.path.relpath(video_path, knowledge_dir)
    hash_key = hashlib.sha256(f"{rel_path}:{timestamp_sec:.2f}".encode('utf-8')).hexdigest()[:12]
    filename = f"thumb_{hash_key}.jpg"
    out_path = os.path.join(thumbnails_dir, filename)
    
    canvas.save(out_path, "JPEG", quality=quality)
    return out_path

def generate_audio_thumbnail(audio_path: str, title: str = "Audio Scene", target_w: int = 320, target_h: int = 180) -> str:
    """Generate a clean dark-mode waveform placeholder for audio files using PIL."""
    canvas = Image.new("RGB", (target_w, target_h), (24, 28, 36))
    draw = ImageDraw.Draw(canvas)
    
    # Draw simple decorative audio waveform lines
    center_y = target_h // 2
    bars = 32
    bar_width = 4
    spacing = 6
    start_x = (target_w - (bars * spacing)) // 2
    
    rel_path = os.path.relpath(audio_path, knowledge_dir)
    h_val = int(hashlib.md5(rel_path.encode('utf-8')).hexdigest(), 16)
    
    for i in range(bars):
        # Semi-random amplitude based on hash
        amp = ((h_val >> (i % 24)) & 0x1F) + 10
        x = start_x + (i * spacing)
        draw.line([(x, center_y - amp), (x, center_y + amp)], fill=(99, 102, 241), width=bar_width)
    
    # Draw audio icon / badge text
    draw.rectangle([(10, 10), (70, 30)], fill=(79, 70, 229))
    draw.text((15, 12), "AUDIO", fill=(255, 255, 255))
    
    hash_key = hashlib.sha256(rel_path.encode('utf-8')).hexdigest()[:12]
    filename = f"thumb_audio_{hash_key}.jpg"
    out_path = os.path.join(thumbnails_dir, filename)
    canvas.save(out_path, "JPEG", quality=85)
    return out_path

print("\n=== TESTING THUMBNAIL GENERATION ON SAMPLE VIDEOS ===")
sample_videos = [
    r"telegram_courses\Курс _Покоритель Наташек 6_0_\2025-07-22 00-42-20_msg19.mp4",
    r"telegram_courses\Курс _Покоритель Наташек 6_0_\2025-07-23 03-31-37_msg20.mp4",
    r"telegram_courses\Общий чат _Покоритель Наташек 6_0_\IMG_5200_msg190813.MOV",
    r"telegram_courses\Мышцы 20_80 _ BIOMACHINE _ 2 поток\sticker_msg90.webm",
]

t0 = time.time()
generated_count = 0

for vrel in sample_videos:
    vfull = os.path.join(knowledge_dir, vrel)
    if os.path.exists(vfull):
        # Extract at 10 seconds, 60 seconds, 120 seconds
        for ts in [10.0, 60.0, 120.0]:
            out = generate_video_thumbnail_cv2(vfull, ts, target_w=320, target_h=180, quality=85)
            if out:
                generated_count += 1
                size = os.path.getsize(out)
                print(f"Generated video thumb: {os.path.basename(out)} | timestamp={ts}s | size={size} bytes")

t1 = time.time()
print(f"Video thumbnail test complete. Generated {generated_count} thumbnails in {t1-t0:.3f} seconds ({ (t1-t0)/max(1, generated_count):.3f}s per thumb)")

print("\n=== TESTING AUDIO THUMBNAIL GENERATION ===")
sample_audio = [
    r"telegram_courses\Курс _Покоритель Наташек 6_0_\20250902-222352_msg140.mp3",
    r"telegram_courses\Курс _Покоритель Наташек 6_0_\media_174.oga",
    r"telegram_courses\Курс _Покоритель Наташек 6_0_\URecorder_21092025_194536_msg154.m4a"
]

for arel in sample_audio:
    afull = os.path.join(knowledge_dir, arel)
    if os.path.exists(afull):
        out = generate_audio_thumbnail(afull, target_w=320, target_h=180)
        size = os.path.getsize(out)
        print(f"Generated audio thumb: {os.path.basename(out)} | size={size} bytes")

