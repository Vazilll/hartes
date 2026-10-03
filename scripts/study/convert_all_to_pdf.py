import os
import sys
import win32com.client

sys.stdout.reconfigure(encoding='utf-8')

dir_path = r"C:\Users\Vaz\Documents\mirea_study_os\01_Disciplines\14_Informatics"

docx_files = [
    "Отчет_Практическая_01_Информатика_Жуков_ИВБО-22-25.docx",
    "Отчет_Практическая_05_Информатика_Жуков_ИВБО-22-25.docx",
    "Отчет_Практическая_06_Информатика_Жуков_ИВБО-22-25.docx"
]

print("Launching Word Application...")
word = win32com.client.Dispatch("Word.Application")
word.Visible = False

try:
    for docx_name in docx_files:
        src = os.path.join(dir_path, docx_name)
        pdf_name = docx_name.replace(".docx", ".pdf")
        dst = os.path.join(dir_path, pdf_name)
        
        print(f"Converting {docx_name} to {pdf_name}...")
        doc = word.Documents.Open(src)
        # 17 is wdExportFormatPDF
        doc.SaveAs2(dst, FileFormat=17)
        doc.Close()
        sz = os.path.getsize(dst)
        print(f"Successfully saved {pdf_name}: {sz} bytes")
finally:
    word.Quit()

print("All PDF conversions completed successfully!")
