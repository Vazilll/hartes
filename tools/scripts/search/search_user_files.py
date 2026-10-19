import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

search_dirs = [
    r"C:\Users\Vaz\Documents",
    r"C:\Users\Vaz\Downloads",
    r"/home/tarhes/Проекты/vazus"
]

keywords = ["Кодировка", "Системы", "Домик", "Домик2", "4C3B", "D35E", "9B7D", "Практическая работа"]

for base in search_dirs:
    for root, dirs, files in os.walk(base):
        # Skip noisy dirs
        if any(x in root for x in [".git", ".venv", "node_modules", ".cache", "cache", "AppData"]):
            continue
        for f in files:
            if f.endswith(('.txt', '.md', '.docx', '.py', '.xlsx', '.pdf')):
                fpath = os.path.join(root, f)
                try:
                    # check filename
                    if any(k.lower() in f.lower() for k in ["домик", "кодировк", "информатик"]):
                        print(f"MATCH FILE: {fpath}")
                except Exception:
                    pass
print("Done searching filenames.")
