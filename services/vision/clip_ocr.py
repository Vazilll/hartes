import sys
import numpy as np
from PIL import ImageGrab
from rapidocr import RapidOCR

sys.stdout.reconfigure(encoding='utf-8')

def read_clipboard_ocr():
    img = ImageGrab.grabclipboard()
    if img is None:
        print("NO_IMAGE_IN_CLIPBOARD")
        return
    img_np = np.array(img.convert('RGB'))
    engine = RapidOCR()
    out = engine(img_np)
    if hasattr(out, 'txts') and out.txts:
        print("\n".join(out.txts))
    else:
        print("NO_TEXT_FOUND")

if __name__ == "__main__":
    read_clipboard_ocr()
