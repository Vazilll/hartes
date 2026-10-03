import docx
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

path = r"C:\Users\Vaz\Documents\mirea_study_os\01_Disciplines\14_Informatics\Титульный_лист.docx"
if os.path.exists(path):
    doc = docx.Document(path)
    print("--- PARAGRAPHS ---")
    for p in doc.paragraphs:
        if p.text.strip():
            print(p.text)
    print("--- TABLES ---")
    for t in doc.tables:
        for r in t.rows:
            row_txt = [c.text.strip() for c in r.cells]
            print(" | ".join(row_txt))
