import os
import sys
from PIL import Image, ImageDraw

sys.stdout.reconfigure(encoding='utf-8')

img_dir = r"C:\Users\Vaz\Documents\mirea_study_os\01_Disciplines\14_Informatics\images"
os.makedirs(img_dir, exist_ok=True)

# 1. Ч/б домик 640x480 (24-bit BMP)
img1 = Image.new("RGB", (640, 480), "white")
d1 = ImageDraw.Draw(img1)
# Стены
d1.rectangle([220, 220, 420, 420], outline="black", width=3)
# Крыша
d1.polygon([(200, 220), (320, 100), (440, 220)], outline="black", fill="white")
# Окно
d1.rectangle([280, 260, 360, 340], outline="black", width=2)
d1.line([(320, 260), (320, 340)], fill="black", width=2)
d1.line([(280, 300), (360, 300)], fill="black", width=2)
# Дверь
d1.rectangle([230, 320, 270, 420], outline="black", width=2)

p_domik_bmp = os.path.join(img_dir, "Домик.bmp")
p_domik_jpg = os.path.join(img_dir, "Домик.jpg")
img1.save(p_domik_bmp, format="BMP")
img1.save(p_domik_jpg, format="JPEG", quality=85)

# 2. Цветной домик Домик2.bmp 640x480 (24-bit BMP)
img2 = Image.new("RGB", (640, 480), "#87CEEB") # Небо
d2 = ImageDraw.Draw(img2)
# Земля / трава
d2.rectangle([0, 380, 640, 480], fill="#228B22")
# Солнце
d2.ellipse([500, 40, 600, 140], fill="#FFD700", outline="#FFA500", width=2)
# Стены дома
d2.rectangle([220, 220, 420, 420], fill="#D2691E", outline="#8B4513", width=3)
# Крыша
d2.polygon([(200, 220), (320, 100), (440, 220)], fill="#B22222", outline="#800000")
# Окно
d2.rectangle([280, 260, 360, 340], fill="#E0FFFF", outline="#4682B4", width=2)
d2.line([(320, 260), (320, 340)], fill="#4682B4", width=2)
d2.line([(280, 300), (360, 300)], fill="#4682B4", width=2)
# Дверь
d2.rectangle([230, 320, 270, 420], fill="#8B4513", outline="#5C2E0B", width=2)
# Забор
for x in range(50, 200, 25):
    d2.rectangle([x, 340, x+15, 420], fill="#DEB887", outline="#8B5A2B", width=1)
for x in range(440, 600, 25):
    d2.rectangle([x, 340, x+15, 420], fill="#DEB887", outline="#8B5A2B", width=1)

p_domik2_bmp = os.path.join(img_dir, "Домик2.bmp")
p_domik2_jpg = os.path.join(img_dir, "Домик2.jpg")
img2.save(p_domik2_bmp, format="BMP")
img2.save(p_domik2_jpg, format="JPEG", quality=85)

# 3. Домик3.bmp 16-цветный (4-битная палитра)
img3 = img2.quantize(colors=16)
p_domik3_bmp = os.path.join(img_dir, "Домик3.bmp")
img3.save(p_domik3_bmp, format="BMP")

# 4. Домик 4 (Домик2, уменьшенный до 320x240)
img4 = img2.resize((320, 240), Image.Resampling.LANCZOS)
p_domik4_bmp = os.path.join(img_dir, "Домик4.bmp")
p_domik4_jpg = os.path.join(img_dir, "Домик4.jpg")
img4.save(p_domik4_bmp, format="BMP")
img4.save(p_domik4_jpg, format="JPEG", quality=85)

results = {}
for p in [p_domik_bmp, p_domik_jpg, p_domik2_bmp, p_domik2_jpg, p_domik3_bmp, p_domik4_bmp, p_domik4_jpg]:
    name = os.path.basename(p)
    sz = os.path.getsize(p)
    results[name] = sz
    print(f"{name}: {sz} bytes ({sz / 1024:.2f} KB)")
