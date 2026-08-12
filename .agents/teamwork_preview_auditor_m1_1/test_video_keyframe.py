import os
import sys
from PIL import Image

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

if "C:/vazus" not in sys.path and "C:\\vazus" not in sys.path:
    sys.path.insert(0, "C:/vazus")

from vazus_core.multimodal_knowledge import generate_thumbnail

def test_video():
    video_file = r"C:\vazus\knowledge\telegram_courses\Курс _Покоритель Наташек 6_0_\2025-07-22 00-42-20_msg19.mp4"
    if not os.path.exists(video_file):
        print(f"Video file not found: {video_file}")
        return
    
    out_path = "C:/vazus/knowledge/.thumbnails/test_video_frame.jpg"
    thumb = generate_thumbnail(video_file, 5.0, out_path)
    print(f"Video thumbnail generated at: {thumb}")
    assert os.path.exists(thumb), "Video thumbnail file does not exist!"
    assert os.path.getsize(thumb) > 1000, "Video thumbnail file size is too small!"
    img = Image.open(thumb)
    print(f"Video thumbnail size: {img.size}, format: {img.format}")
    assert img.size == (320, 180), f"Expected 320x180, got {img.size}"
    print("Video frame extraction check passed!")

if __name__ == "__main__":
    test_video()
