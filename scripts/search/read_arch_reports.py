import docx
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

for f in ["Отчет_Блок_01_Жуков_ИВБО-22-25.docx", "Отчет_Блок_02_Жуков_ИВБО-22-25.docx"]:
    path = os.path.join(r"C:\Users\Vaz\Documents\mirea_study_os\01_Disciplines\05_Computer_Architecture", f)
    if os.path.exists(path):
        print(f"\n{'='*50}\n{f}\n{'='*50}")
        doc = docx.Document(path)
        for p in doc.paragraphs[:25]:
            if p.text.strip():
                print(p.text)
