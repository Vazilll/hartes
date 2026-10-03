#!/usr/bin/env python3
"""
migrate_bobusy_3semesters.py — Restructures G:\\My Drive\\бобусы into 3 Semesters.
Preserves all existing cohort files (Жуков, Артём, Вадим), merges debts from Semester 1 and 2,
and populates all remaining 3rd semester subjects.
"""

import os
import sys
import shutil
import logging
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("migrate_3semesters")

DRIVE_BOBUSY = Path(r"G:\My Drive\бобусы")
DRIVE_DEBTS_1 = Path(r"G:\My Drive\МИРЭА_Задолженности_1_семестр")
LOCAL_DOCS = Path(r"C:\Users\Vaz\Documents")
LOCAL_KNOWLEDGE = Path(r"C:\vazus\knowledge\mirea")
LOCAL_STUDY_OS = Path(r"C:\Users\Vaz\Documents\mirea_study_os")

def safe_copy_tree(src: Path, dst: Path, overwrite: bool = False):
    if not src.exists():
        logger.warning(f"Source does not exist: {src}")
        return 0
    copied = 0
    excl = {".git", "__pycache__", ".obsidian", ".pytest_cache"}
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d not in excl and not d.startswith(".tmp")]
        rel = Path(root).relative_to(src)
        target_dir = dst / rel
        target_dir.mkdir(parents=True, exist_ok=True)
        for f in files:
            if f == "desktop.ini" or f.endswith(".pyc") or f.startswith("~$"):
                continue
            sf = Path(root) / f
            df = target_dir / f
            if not df.exists() or overwrite:
                try:
                    shutil.copy2(sf, df)
                    copied += 1
                except Exception as e:
                    logger.warning(f"Error copying {sf} -> {df}: {e}")
    return copied

def safe_move_dir(src: Path, dst: Path):
    if not src.exists():
        logger.warning(f"Source dir does not exist: {src}")
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        logger.info(f"Merging {src} into existing {dst}")
        safe_copy_tree(src, dst, overwrite=True)
        try:
            shutil.rmtree(src)
            logger.info(f"Removed source dir after merge: {src}")
        except Exception as e:
            logger.warning(f"Could not remove {src} after merge: {e}")
    else:
        try:
            shutil.move(str(src), str(dst))
            logger.info(f"Moved {src} -> {dst}")
        except Exception as e:
            logger.warning(f"Move failed, trying copy + remove: {e}")
            safe_copy_tree(src, dst, overwrite=True)
            shutil.rmtree(src, ignore_errors=True)

def main():
    if not DRIVE_BOBUSY.exists():
        logger.error(f"{DRIVE_BOBUSY} is not mounted!")
        return 1

    sem1 = DRIVE_BOBUSY / "01_Семестр_1"
    sem2 = DRIVE_BOBUSY / "02_Семестр_2"
    sem3 = DRIVE_BOBUSY / "03_Семестр_3"

    for d in (sem1, sem2, sem3):
        d.mkdir(parents=True, exist_ok=True)

    logger.info("=== 1. Restructuring Semester 3 Disciplines ===")
    sem3_mappings = [
        ("Системы искусственного интеллекта и большие данные", "01_Системы_искусственного_интеллекта_и_большие_данные"),
        ("Информационно-технологическая инфраструктура", "02_Информационно_технологическая_инфраструктура"),
        ("Программирование на языке Java (ООП)", "03_Программирование_на_языке_Java_ООП"),
        ("Электротехника", "04_Электротехника"),
        ("Теория вычислительных процессов", "05_Теория_вычислительных_процессов"),
        ("Архитектура вычислительных машин и систем", "06_Архитектура_вычислительных_машин_и_систем"),
    ]

    for old_name, new_name in sem3_mappings:
        src = DRIVE_BOBUSY / old_name
        dst = sem3 / new_name
        if src.exists():
            safe_move_dir(src, dst)
        else:
            logger.info(f"Checking if {dst} already in place: {dst.exists()}")

    # Additional 3rd semester subjects
    additional_sem3 = [
        (LOCAL_DOCS / "Математический анализ 3", sem3 / "07_Математический_анализ_3" / "Основы"),
        (LOCAL_DOCS / "Социальная психология и педагогика", sem3 / "08_Социальная_психология_и_педагогика" / "Основы"),
        (LOCAL_DOCS / "Философия", sem3 / "09_Философия" / "Основы"),
        (LOCAL_DOCS / "Иностранный язык (английский)", sem3 / "11_Иностранный_язык_IT_3" / "Основы"),
    ]
    for src, dst in additional_sem3:
        if src.exists():
            logger.info(f"Copying {src.name} to {dst}")
            safe_copy_tree(src, dst)

    # 10. Аналитическая практика (отчет Жукова и общие методички)
    analyt_dir = sem3 / "10_Аналитическая_практика"
    analyt_dir.mkdir(parents=True, exist_ok=True)
    (analyt_dir / "Жуков").mkdir(parents=True, exist_ok=True)
    report_src = LOCAL_KNOWLEDGE / "Отчет_Аналитическая_практика_Жуков_М_Д.docx"
    if report_src.exists():
        shutil.copy2(report_src, analyt_dir / "Жуков" / "Отчет_Аналитическая_практика_Жуков_М_Д.docx")

    # Ensure student subdirs exist in 3rd semester subjects
    students = ["Жуков", "Артём", "Вадим"]
    for subj in sem3.iterdir():
        if subj.is_dir():
            for s in students:
                (subj / s).mkdir(parents=True, exist_ok=True)

    logger.info("=== 2. Migrating Semester 1 Disciplines and Debts ===")
    sem1_mappings = [
        ("01_Математический_анализ", "01_Математический_анализ_1"),
        ("02_Линейная_алгебра", "02_Линейная_алгебра_1"),
        ("03_Математическая_логика", "03_Математическая_логика"),
        ("04_Английский_язык_IT", "04_Иностранный_язык_IT_1"),
    ]

    for old_name, new_name in sem1_mappings:
        dst = sem1 / new_name
        dst.mkdir(parents=True, exist_ok=True)
        (dst / "Основы").mkdir(parents=True, exist_ok=True)
        for s in students:
            (dst / s).mkdir(parents=True, exist_ok=True)

        if DRIVE_DEBTS_1.exists() and (DRIVE_DEBTS_1 / old_name).exists():
            logger.info(f"Moving debt folder {old_name} into {dst / 'Основы'}")
            safe_copy_tree(DRIVE_DEBTS_1 / old_name, dst / "Основы", overwrite=True)
        elif (LOCAL_KNOWLEDGE / old_name).exists():
            safe_copy_tree(LOCAL_KNOWLEDGE / old_name, dst / "Основы", overwrite=True)

    # 05. Русский язык и культура речи
    rus_dir = sem1 / "05_Русский_язык_и_культура_речи"
    (rus_dir / "Основы").mkdir(parents=True, exist_ok=True)
    (rus_dir / "Жуков").mkdir(parents=True, exist_ok=True)
    if (LOCAL_DOCS / "Русский язык и культура речи").exists():
        safe_copy_tree(LOCAL_DOCS / "Русский язык и культура речи", rus_dir / "Основы")

    # 06. Основы конструирования
    konstr_dir = sem1 / "06_Основы_конструирования"
    (konstr_dir / "Основы").mkdir(parents=True, exist_ok=True)
    (konstr_dir / "Жуков").mkdir(parents=True, exist_ok=True)
    (konstr_dir / "Основы" / "README.md").write_text(
        "# Основы конструирования (Семестр 1)\n"
        "> **Тип контроля:** Зачет (1/1, № 86971) | Дедлайн: 15.10.2026\n\n"
        "## Задачи:\n"
        "1. Ознакомление с ЕСКД, чертежами и САПР (Компас-3D / AutoCAD).\n"
        "2. Оформление пояснительной записки и сдача отчета по практическим работам.\n",
        encoding="utf-8"
    )

    # 07. Ознакомительная практика
    oznakom_dir = sem1 / "07_Ознакомительная_практика"
    (oznakom_dir / "Основы").mkdir(parents=True, exist_ok=True)
    (oznakom_dir / "Жуков").mkdir(parents=True, exist_ok=True)
    (oznakom_dir / "Основы" / "README.md").write_text(
        "# Ознакомительная практика (Семестр 1)\n"
        "> **Тип контроля:** Дифференцированный зачет (1/1, № 6082) | Дедлайн: 15.10.2026\n\n"
        "## Требования:\n"
        "1. Заполнение дневника практики и индивидуального задания.\n"
        "2. Оформление титульного листа и отчета по профилю кафедры КИТПиПИ.\n",
        encoding="utf-8"
    )

    # 08. Основы российской государственности
    gos_dir = sem1 / "08_Основы_российской_государственности"
    (gos_dir / "Основы").mkdir(parents=True, exist_ok=True)
    (gos_dir / "Жуков").mkdir(parents=True, exist_ok=True)
    (gos_dir / "Основы" / "README.md").write_text(
        "# Основы российской государственности (Семестр 1)\n"
        "> **Тип контроля:** Зачет (1/1, № 82576) | Дедлайн: 15.10.2026\n\n"
        "## Задачи:\n"
        "1. Прохождение тестов в СДО Moodle.\n"
        "2. Подготовка итогового эссе.\n",
        encoding="utf-8"
    )

    # 09. Физическая культура и спорт 1
    fk1_dir = sem1 / "09_Физическая_культура_и_спорт_1"
    (fk1_dir / "Основы").mkdir(parents=True, exist_ok=True)
    (fk1_dir / "Жуков").mkdir(parents=True, exist_ok=True)
    if (LOCAL_DOCS / "Физическая культура и спорт").exists():
        safe_copy_tree(LOCAL_DOCS / "Физическая культура и спорт", fk1_dir / "Основы")

    logger.info("=== 3. Setting Up Semester 2 Disciplines and Debts ===")
    sem2_disciplines = [
        ("01_Математический_анализ_2", "Экзамен (2/3, № 81917)", "Интегральное исчисление функций одной и нескольких переменных, ряды, дифференциальные уравнения. Расчетно-графические работы."),
        ("02_Линейная_алгебра_2", "Экзамен (2/2, № 66804)", "Линейные пространства, линейные операторы, квадратичные формы, евклидовы пространства."),
        ("03_Физика", "Зачет + Экзамен (2/2, № 78208)", "Механика, молекулярная физика, термодинамика, электромагнетизм, волновая и квантовая оптика. Лабораторный практикум."),
        ("04_Информатика_и_Архитектура_ЭВМ", "Экзамен (2/2, № 85415)", "Основы алгоритмизации на Python/C++, базовые принципы архитектуры ЭВМ фон Неймана, память, регистры, машинные команды."),
        ("05_Объектно_ориентированное_программирование", "Курсовая работа + Экзамен (1/1, № 86959)", "Принципы ООП (инкапсуляция, наследование, полиморфизм, абстракция), паттерны GoF, разработка курсового проекта."),
        ("06_Иностранный_язык_IT_2", "Зачет (2/3, № 86146)", "Профессиональный перевод англоязычной научно-технической литературы по вычислительной технике, терминологический минимум."),
        ("07_История_России", "Экзамен (2/2, № 82054)", "Хронология, ключевые исторические этапы, реформы, государственное управление и культура России."),
        ("08_Физическая_культура_и_спорт_2", "Зачет (2/3, № 72287)", "Нормативы, рефераты по оздоровительной физической культуре."),
    ]

    for d_name, d_type, d_desc in sem2_disciplines:
        d_path = sem2 / d_name
        (d_path / "Основы").mkdir(parents=True, exist_ok=True)
        for s in students:
            (d_path / s).mkdir(parents=True, exist_ok=True)
        readme_file = d_path / "Основы" / "README.md"
        if not readme_file.exists():
            readme_file.write_text(
                f"# {d_name.replace('_', ' ')}\n"
                f"> **Контроль:** {d_type} | Дедлайн 1 этапа: **15.10.2026**\n\n"
                f"## Описание и программа:\n{d_desc}\n\n"
                f"## Структура раздела:\n"
                f"- `Основы/`: Программа курса, вопросы к экзамену/зачету, литература.\n"
                f"- `Жуков/`: Индивидуальный вариант (Вар. 6), выполненные РГР и билеты.\n"
                f"- `Артём/`: Вариант 10.\n"
                f"- `Вадим/`: Вариант 4.\n",
                encoding="utf-8"
            )

    logger.info("=== 4. Updating Master README and Navigation Hub ===")
    from sync_bobusy_drive import write_master_readme, write_notebooklm_catalog
    write_master_readme(DRIVE_BOBUSY / "00_README_И_НАВИГАЦИЯ.md")

    nlm_dir = DRIVE_BOBUSY / "Материалы для изучения (NotebookLM)"
    nlm_dir.mkdir(parents=True, exist_ok=True)
    write_notebooklm_catalog(nlm_dir / "NOTEBOOKLM_CATALOG.md")

    logger.info("=== 5. Cleaning up temporary debt folder on Drive ===")
    if DRIVE_DEBTS_1.exists():
        try:
            shutil.rmtree(DRIVE_DEBTS_1)
            logger.info(f"Successfully archived/removed {DRIVE_DEBTS_1}")
        except Exception as e:
            logger.warning(f"Note: Could not remove {DRIVE_DEBTS_1}: {e}")

    logger.info("✅ Migration to 3-semester taxonomy completed successfully!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
