import docx
import sys

sys.stdout.reconfigure(encoding='utf-8')

path = r"C:\Users\Vaz\Documents\mirea_study_os\01_Disciplines\14_Informatics\Титульный_лист.docx"
doc = docx.Document(path)

print(f"Num paragraphs: {len(doc.paragraphs)}")
for idx, p in enumerate(doc.paragraphs):
    print(f"P{idx}: '{p.text}' | align={p.alignment} | style={p.style.name}")
    for r in p.runs:
        print(f"   Run: '{r.text}' | font={r.font.name} | size={r.font.size} | bold={r.font.bold}")

print(f"Num tables: {len(doc.tables)}")
for tidx, t in enumerate(doc.tables):
    print(f"Table {tidx}: rows={len(t.rows)}, cols={len(t.columns)}")
    for ridx, r in enumerate(t.rows):
        for cidx, c in enumerate(r.cells):
            print(f"   Cell({ridx},{cidx}): '{c.text}'")
