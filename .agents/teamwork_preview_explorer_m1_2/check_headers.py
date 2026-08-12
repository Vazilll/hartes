import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

knowledge_dir = r"C:\vazus\knowledge"
failed_files = [
    r"telegram_courses\Курс _Покоритель Наташек 6_0_\2025-09-28 16-26-43.mp4",
    r"telegram_courses\Курс _Покоритель Наташек 6_0_\2025-09-28 16-26-43_msg162.mp4",
    r"telegram_courses\Курс _Покоритель Наташек 6_0_\2025-10-02 19-42-41.mp4",
    r"telegram_courses\Курс _Покоритель Наташек 6_0_\2025-10-02 19-42-41_msg164.mp4",
    r"telegram_courses\Мышцы 20_80 _ BIOMACHINE _ 2 поток\03 1 Питание 1_(СЖАТЫЙ)_msg75.mp4",
]

print("=== CHECKING FILE HEADERS ===")
for rel in failed_files:
    full = os.path.join(knowledge_dir, rel)
    if os.path.exists(full):
        with open(full, "rb") as f:
            header = f.read(64)
            print(f"File: {rel}\n  Header hex: {header.hex()[:64]}\n  Header repr: {header[:32]}")
