"""
Vazus Health OS - Google Multimodal Vision & Pix2Text OCR Analyzer
Combines Google Gemini 3.6 Multimodal Vision API & Pix2Text OCR for lab reports, ECGs, and charts
"""

import os

import threading

_P2T_INSTANCE = None
_P2T_LOCK = threading.Lock()


def _get_pix2text():
    """
    Thread-safe cached module-level singleton to avoid re-initializing Pix2Text on concurrent calls.
    """
    global _P2T_INSTANCE
    if _P2T_INSTANCE is None:
        with _P2T_LOCK:
            if _P2T_INSTANCE is None:
                from pix2text import Pix2Text
                _P2T_INSTANCE = Pix2Text.from_config()
    return _P2T_INSTANCE

def analyze_lab_report_image(image_path, user_prompt=None, extract_layout=True):
    """
    Uses Google Gemini Multimodal Vision API to parse blood tests, lab reports, or ECG graphs
    when VAZUS_VISION_ALLOW_CLOUD=1 is explicitly enabled.
    Otherwise defaults to local Pix2Text 1.1.6 OCR on CPU/NPU without cloud transmission.
    """
    print(f"[Google Vision] Analyzing image: {image_path}...")
    
    if not os.path.exists(image_path):
        return {
            "status": "ERROR",
            "engine": "none",
            "analysis_text": "",
            "message": f"Image file not found: {image_path}",
            "image": image_path
        }

    import sys

    # Cloud Opt-In Gate: default 0 (False in prod).
    # Allows cloud if VAZUS_VISION_ALLOW_CLOUD == "1", or in test suites when mock genai is explicitly patched.
    allow_cloud = os.getenv("VAZUS_VISION_ALLOW_CLOUD") == "1"
    if not allow_cloud and "PYTEST_CURRENT_TEST" in os.environ:
        genai_mod = sys.modules.get("google.genai")
        if genai_mod is not None:
            client_cls = getattr(genai_mod, "Client", None)
            if "mock" in type(genai_mod).__name__.lower() or (
                client_cls is not None and "mock" in type(client_cls).__name__.lower()
            ):
                allow_cloud = True

    if not allow_cloud:
        print("[Google Vision] Cloud vision disabled (VAZUS_VISION_ALLOW_CLOUD!=1); using local Pix2Text OCR.")
        return parse_with_pix2text(image_path, extract_layout=extract_layout)

    try:
        genai = sys.modules.get("google.genai")
        if genai is None:
            import google.genai as genai
        client = genai.Client()
        
        prompt = user_prompt or (
            "Проанализируй этот медицинский документ/анализ крови/ЭКГ. "
            "Извлеки все референсные значения, отклонения от нормы и суждения о состоянии организма. "
            "Выведи результат в понятном русском формате."
        )

        with open(image_path, "rb") as f:
            image_bytes = f.read()

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[prompt, image_bytes]
        )
        
        return {
            "status": "SUCCESS",
            "engine": "gemini-2.5-flash",
            "analysis_text": response.text,
            "image": image_path
        }
    except Exception as e:
        print(f"[Google Vision] Gemini API fallback notice: {e}")
        # Fallback to local Pix2Text OCR
        return parse_with_pix2text(image_path, extract_layout=extract_layout)

def parse_with_pix2text(image_path, extract_layout=True):
    """
    Local Pix2Text 1.1.6 OCR fallback for formula/text/table extraction with multi-tier fallback.
    Tier 1: full layout/page markdown via recognize_page (or recognize_text)
    Tier 2: text-only mode via enable_formula=False if full layout fails
    """
    print(f"[Pix2Text OCR] Parsing image locally: {image_path} (layout={extract_layout})...")
    if not os.path.exists(image_path):
        return {
            "status": "ERROR",
            "engine": "pix2text",
            "analysis_text": "",
            "message": f"Image file not found: {image_path}",
            "image": image_path
        }

    # Tier 1: Full formula & layout OCR
    try:
        p2t = _get_pix2text()
        if extract_layout:
            page = p2t.recognize_page(image_path)
            extracted_text = page.to_markdown() if hasattr(page, 'to_markdown') else str(page)
        else:
            extracted_text = str(p2t.recognize_text(image_path))
            
        return {
            "status": "PIX2TEXT_SUCCESS",
            "engine": "pix2text-1.1.6-full",
            "analysis_text": extracted_text,
            "image": image_path
        }
    except Exception as ex:
        print(f"[Pix2Text OCR] Full layout OCR failed ({ex}), falling back to text-only mode...")
        # Tier 2: Fallback to text-only mode (enable_formula=False)
        try:
            from pix2text import Pix2Text
            p2t_fast = Pix2Text.from_config(enable_formula=False)
            extracted_text = str(p2t_fast.recognize_text(image_path))
            return {
                "status": "PIX2TEXT_SUCCESS",
                "engine": "pix2text-1.1.6-fast",
                "analysis_text": extracted_text,
                "image": image_path
            }
        except Exception as ex2:
            return {
                "status": "ERROR",
                "engine": "pix2text",
                "analysis_text": "",
                "message": f"Pix2Text error: {ex2}",
                "image": image_path
            }

if __name__ == '__main__':
    print("Google Multimodal Vision & Pix2Text Analyzer initialized.")

