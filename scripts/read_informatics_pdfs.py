import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

dir_path = r"C:\Users\Vaz\Documents\mirea_study_os\01_Disciplines\14_Informatics"

# Try different pdf extractors
pdf_text = {}
files = [
    "Практическая_работа_1.pdf",
    "Практическая_работа_5.pdf",
    "Практическая_работа_6.pdf"
]

has_pypdf = False
try:
    import pypdf
    has_pypdf = True
except ImportError:
    pass

has_fitz = False
try:
    import fitz
    has_fitz = True
except ImportError:
    pass

has_pdfminer = False
try:
    import pdfminer
    has_pdfminer = True
except ImportError:
    pass

print(f"Libraries available: pypdf={has_pypdf}, fitz={has_fitz}, pdfminer={has_pdfminer}")

for f in files:
    path = os.path.join(dir_path, f)
    print(f"\n=================== {f} ===================")
    if has_pypdf:
        reader = pypdf.PdfReader(path)
        print(f"Num pages: {len(reader.pages)}")
        for idx, page in enumerate(reader.pages):
            print(f"--- PAGE {idx+1} ---")
            print(page.extract_text()[:1500])
    elif has_fitz:
        doc = fitz.open(path)
        print(f"Num pages: {len(doc)}")
        for idx, page in enumerate(doc):
            print(f"--- PAGE {idx+1} ---")
            print(page.get_text()[:1500])
    else:
        print("No standard PDF library found. Let's check python environment.")
