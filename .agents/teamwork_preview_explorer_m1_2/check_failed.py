import os
import sys
import cv2

sys.stdout.reconfigure(encoding='utf-8')

knowledge_dir = r"C:\vazus\knowledge"
failed_files = [
    r"telegram_courses\Курс _Покоритель Наташек 6_0_\2025-09-28 16-26-43.mp4",
    r"telegram_courses\Курс _Покоритель Наташек 6_0_\2025-10-02 19-42-41.mp4",
    r"telegram_courses\Курс _Покоритель Наташек 6_0_\2025-12-04 01-58-17.mp4",
    r"telegram_courses\Курс _Покоритель Наташек 6_0_\2025-12-10 01-51-00.mp4",
    r"telegram_courses\Курс _Покоритель Наташек 6_0_\IMG_4823.MP4",
    r"telegram_courses\Курс _Покоритель Наташек 6_0_\record.mp4",
    r"telegram_courses\МЫШЦЫ 20_80\IMG_2364_msg7.MP4",
    r"telegram_courses\МЫШЦЫ 20_80\IMG_9779_msg26.MP4",
    r"telegram_courses\Мышцы 20_80 _ BIOMACHINE _ 2 поток\03 1 Питание 1_(СЖАТЫЙ)_msg75.mp4",
    r"telegram_courses\Мышцы 20_80 _ BIOMACHINE _ 2 поток\03 2 Питание 1_(СЖАТЫЙ)_msg76.mp4",
    r"telegram_courses\Мышцы 20_80 _ BIOMACHINE _ 2 поток\03 3 Питание_(СЖАТЫЙ)_msg77.mp4",
    r"telegram_courses\Мышцы 20_80 _ BIOMACHINE _ 2 поток\04 Питание_(СЖАТЫЙ)_msg78.mp4",
    r"telegram_courses\Мышцы 20_80 _ BIOMACHINE _ 2 поток\04_1 Питание_(СЖАТЫЙ)_msg79.mp4",
    r"telegram_courses\ФУНКЦИОНАЛЬНАЯ МАШИНА _ Канал курса\02 ИНТ_ПРАКТИКА_compressed_msg38.mp4",
    r"telegram_courses\ФУНКЦИОНАЛЬНАЯ МАШИНА _ Канал курса\03 ИНТ_ТЕОРИЯ_compressed_msg39.mp4",
    r"telegram_courses\ФУНКЦИОНАЛЬНАЯ МАШИНА _ Канал курса\Live Тренировка Main_(СЖАТЫЙ)_msg48.mp4"
]

print("=== INSPECTING FAILED VIDEO FILES ===")
for rel_path in failed_files:
    full_path = os.path.join(knowledge_dir, rel_path)
    exists = os.path.exists(full_path)
    if exists:
        size = os.path.getsize(full_path)
        print(f"File: {rel_path} | Size: {size} bytes ({size / 1024 / 1024:.2f} MB)")
    else:
        print(f"File NOT FOUND: {rel_path}")
