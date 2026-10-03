import fitz
import sys

sys.stdout.reconfigure(encoding='utf-8')

path = r"C:\Users\Vaz\Documents\mirea_study_os\01_Disciplines\05_Computer_Architecture\Отчет_Блок_01_Жуков_ИВБО-22-25.pdf"
doc = fitz.open(path)
print("Metadata:", doc.metadata)
