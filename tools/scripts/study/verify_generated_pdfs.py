import os
import sys
import fitz

sys.stdout.reconfigure(encoding='utf-8')

dir_path = r"C:\Users\Vaz\Documents\mirea_study_os\01_Disciplines\14_Informatics"

for fname in [
    "Отчет_Практическая_01_Информатика_Жуков_ИВБО-22-25.pdf",
    "Отчет_Практическая_05_Информатика_Жуков_ИВБО-22-25.pdf",
    "Отчет_Практическая_06_Информатика_Жуков_ИВБО-22-25.pdf"
]:
    p = os.path.join(dir_path, fname)
    doc = fitz.open(p)
    print(f"{fname}: {len(doc)} pages, size: {os.path.getsize(p)} bytes")
