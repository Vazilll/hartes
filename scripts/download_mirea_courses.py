#!/usr/bin/env python3
"""
scripts/download_mirea_courses.py — Automated Interactive RTU MIREA Moodle Course Exporter (2FA Yandex & MAX Bypass).

Features:
1. 🔐 Interactive & Saved Login to online-edu.mirea.ru with 2FA Yandex Email IMAP integration.
2. 🛑 Automatic MAX Registration Bypass (Declines MAX prompt).
3. 📚 Scrapes all enrolled subjects/courses via Moodle 4.x WS Service API + /my/ fallback.
4. 🎯 Multi-course selection ('1, 3, 5' or '0' for ALL subjects).
5. 📂 Exports PDFs, slides, and Markdown lecture notes to C:/vazus/services/memory/knowledge/mirea_courses.
6. ⚡ Auto-ingestible by vazus SuperGraph OS & NotebookLM Studio.

vazus SuperGraph OS Ecosystem
"""

import sys
import os
import time
import argparse
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from vazus_core.integrations.mirea_exporter import MoodleSessionManager, MireaCourseExporter, load_env_credentials


def parse_selection(choice_str: str, max_count: int) -> list[int]:
    """Parses selection syntax like '1, 3, 5-8' or '0'."""
    choice_str = choice_str.strip()
    if choice_str == "0" or not choice_str:
        return list(range(max_count))

    selected_indices = set()
    parts = choice_str.replace(";", ",").split(",")

    for part in parts:
        part = part.strip()
        if "-" in part:
            try:
                start, end = map(int, part.split("-"))
                for idx in range(start, end + 1):
                    if 1 <= idx <= max_count:
                        selected_indices.add(idx - 1)
            except ValueError:
                pass
        else:
            try:
                idx = int(part)
                if 1 <= idx <= max_count:
                    selected_indices.add(idx - 1)
            except ValueError:
                pass

    return sorted(list(selected_indices)) if selected_indices else list(range(max_count))


def main():
    print("=" * 75)
    print("🎓 РАЙТСИСТЕМ / ВЫГРУЗЧИК ДИСЦИПЛИН РТУ МИРЭА (2FA YANDEX IMAP + MAX BYPASS)")
    print("=" * 75)

    parser = argparse.ArgumentParser(description="RTU MIREA Moodle Course Exporter")
    parser.add_argument("--all", action="store_true", help="Automatically download ALL enrolled subjects")
    parser.add_argument("--username", type=str, default="", help="MIREA Moodle username")
    parser.add_argument("--password", type=str, default="", help="MIREA Moodle password")
    parser.add_argument("--yandex-email", type=str, default="", help="Yandex Mail for 2FA auto-reading")
    parser.add_argument("--yandex-password", type=str, default="", help="Yandex App Password for IMAP")
    args = parser.parse_args()

    manager = MoodleSessionManager()

    # Attempt Login
    if not manager.load_session_cookies() or not manager.is_authenticated():
        creds = load_env_credentials()
        username = args.username or creds["username"]
        password = args.password or creds["password"]
        yandex_email = args.yandex_email or creds["yandex_email"]
        yandex_password = args.yandex_password or creds["yandex_password"]

        if not username or not password:
            if not sys.stdin.isatty():
                print("\n❌ Учетные данные не заданы. В неинтерактивном режиме необходимо указать MIREA_USERNAME и MIREA_PASSWORD в C:\\vazus\\.env или передать через аргументы CLI.")
                sys.exit(1)

            print("\n🔐 Введите данные учетной записи РТУ МИРЭА (online-edu.mirea.ru):")
            try:
                username = input("Логин (учетка МИРЭА): ").strip()
                import getpass
                password = getpass.getpass("Пароль МИРЭА: ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\n❌ Ввод отменен.")
                sys.exit(1)

        if not yandex_email and sys.stdin.isatty():
            print("\n📩 Для автоматического перехвата 2FA-кодов из письма Yandex:")
            try:
                yandex_email = input("Email Yandex (или Enter для ручного ввода 2FA): ").strip()
                if yandex_email and not yandex_password:
                    import getpass
                    yandex_password = getpass.getpass("Пароль приложения Yandex (IMAP): ").strip()
            except (KeyboardInterrupt, EOFError):
                pass

        if not manager.login(username, password, yandex_email, yandex_password):
            print("❌ Авторизация не удалась. Проверьте правильность логина и пароля.")
            sys.exit(1)
    else:
        print("✅ Авторизация подтверждена по сохраненному токену сессии!")

    exporter = MireaCourseExporter(manager)
    courses = exporter.get_enrolled_courses()

    if not courses:
        print("⚠️ Учебные дисциплины не найдены.")
        sys.exit(0)

    if args.all or not sys.stdin.isatty():
        selected_courses = courses
    else:
        print("\n💡 Можно выбрать несколько предметов через запятую или тире (например: '1, 3' или '0' для ВСЕХ):")
        try:
            choice = input("Выберите номера дисциплин (или 0 для всех): ").strip()
        except (KeyboardInterrupt, EOFError):
            choice = "0"
        selected_indices = parse_selection(choice, len(courses))
        selected_courses = [courses[i] for i in selected_indices]

    print(f"\n🎯 Выбрано дисциплин для выгрузки: {len(selected_courses)}")

    total_downloaded = 0
    t_start = time.time()

    for c in selected_courses:
        res = exporter.export_course(c["course_id"], c["title"])
        total_downloaded += res["downloaded_files"]

    t_total = time.time() - t_start
    print("\n" + "=" * 75)
    print("🎉 ВЫГРУЗКА ДИСЦИПЛИН РТУ МИРЭА ЗАВЕРШЕНА!")
    print(f"Всего скачано файлов: {total_downloaded}")
    print(f"Время работы: {t_total:.1f} сек")
    print(f"Каталог сохранения: {exporter.export_dir}")
    print("=" * 75)


if __name__ == "__main__":
    main()
