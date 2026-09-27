import json, sys
sys.stdout.reconfigure(encoding='utf-8')

with open(r'C:\vazus\hartes\scratch\debt_retake_summary.json', 'r', encoding='utf-8') as f:
    summary = json.load(f)

for num, items in summary.items():
    print(f"\n==========================================")
    print(f"=== ДОЛГ #{num} ({len(items)} записей в расписании) ===")
    if not items:
        print("  [!] Не найдено прямых записей в текущем файле (проверить СДО/деканат)")
        continue
    for idx, item in enumerate(items[:3], 1):
        ivbo_mark = "🎯 [ИВБО!]" if item['is_ivbo'] else "  [Общий поток]"
        print(f"{ivbo_mark} {item['discipline']}")
        print(f"   Кафедра: {item['sheet']} | Преподаватель: {item['teacher']} | Формат: {item['format']}")
        print(f"   Аудитория: {item['room']}")
        print(f"   Даты: {item['dates']}")
        print(f"   Время: {item['times']}")
        if item['groups']:
            print(f"   Группы: {item['groups'][:100]}...")
