import sys
import os
import json

sys.path.insert(0, r"C:\vazus")
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from vazus_core.integrations.mirea_exporter import MoodleSessionManager, MireaCourseExporter, load_env_credentials

print("=" * 70)
print("🎓 РТУ МИРЭА — АВТОМАТИЧЕСКИЙ СКАНИРОВАТЕЛЬ КУРСОВ И ДИСЦИПЛИН (Moodle API)")
print("=" * 70)

manager = MoodleSessionManager()
creds = load_env_credentials()

# Attempt login if session not saved
if not manager.load_session_cookies() or not manager.is_authenticated():
    print("🔑 Запуск полной Keycloak 2FA-авторизации для получения MoodleSession...")
    success = manager.login(
        username=creds['username'],
        password=creds['password'],
        yandex_email=creds.get('yandex_email'),
        yandex_password=creds.get('yandex_password')
    )
    if not success:
        print("❌ Не удалось авторизоваться в СДО МИРЭА.")
        sys.exit(1)

exporter = MireaCourseExporter(manager=manager)
courses = exporter.get_enrolled_courses()

print(f"\n📚 ВСЕГО НАЙДЕНО КУРСОВ/ДИСЦИПЛИН В СДО МИРЭА: {len(courses)}")
print("=" * 70)

for idx, c in enumerate(courses, 1):
    c_id = c.get("id")
    c_fullname = c.get("fullname", "Без названия")
    c_shortname = c.get("shortname", "")
    c_category = c.get("coursecategory", "")
    c_progress = c.get("progress", 0)
    print(f"{idx:2d}. [ID: {c_id}] {c_fullname}")
    if c_progress is not None:
        print(f"    Прогресс: {c_progress}% | Категория: {c_category}")
    print("-" * 70)

# Save found catalog to JSON
out_path = r"C:\vazus\services\memory\knowledge\mirea_courses_catalog.json"
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(courses, f, ensure_ascii=False, indent=2)

print(f"\n💾 Каталог дисциплин сохранён в: {out_path}")
