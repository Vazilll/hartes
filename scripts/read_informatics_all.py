import os
import sys
import fitz

dir_path = r"C:\Users\Vaz\Documents\mirea_study_os\01_Disciplines\14_Informatics"
out_path = os.path.join(dir_path, "extracted_text.txt")

with open(out_path, "w", encoding="utf-8") as out:
    for fname in ["Практическая_работа_1.pdf", "Практическая_работа_5.pdf", "Практическая_работа_6.pdf"]:
        out.write(f"\n{'='*60}\nFILE: {fname}\n{'='*60}\n")
        path = os.path.join(dir_path, fname)
        doc = fitz.open(path)
        for i, p in enumerate(doc):
            out.write(f"\n--- {fname} PAGE {i+1} ---\n")
            out.write(p.get_text())

print("Successfully written utf-8 extracted_text.txt")
