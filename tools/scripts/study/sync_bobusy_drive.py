#!/usr/bin/env python3
"""
sync_bobusy_drive.py — Comprehensive Synchronization and Educational Hub Manager for 'G:\\My Drive\\бобусы'.

Hierarchically organizes the academic workspace across 3 Semesters:
- 01_Семестр_1: Core disciplines & 1st semester debts
- 02_Семестр_2: Disciplines & 2nd semester debts
- 03_Семестр_3: Active 2026 courses (AI, IT Infra, Java OOP, EE, Computer Architecture, etc.)
- Hubs: NotebookLM study guides, Textbooks, GOST templates, Master README navigation.
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
logger = logging.getLogger("sync_bobusy")

DRIVE_BOBUSY_ROOT = Path(r"G:\My Drive\бобусы")
LOCAL_DOCUMENTS = Path(r"C:\Users\Vaz\Documents")
LOCAL_STUDY_OS = Path(r"C:\Users\Vaz\Documents\mirea_study_os")
LOCAL_KNOWLEDGE_MIREA = Path(r"C:\vazus\knowledge\mirea")
LOCAL_NOTEBOOKLM_READY = Path(r"C:\vazus\data\notebooklm_ready")

STUDENTS = ["Жуков", "Артём", "Вадим"]

NOTEBOOKLM_LINKS = [
    {
        "subject": "Информационно-технологическая инфраструктура (ИТИ)",
        "id": "cfcf68ab-70a5-4c74-a205-574e81777e16",
        "title": "RTU MIREIT Term Project Assignment: IT Infrastructure Design",
        "url": "https://notebooklm.google.com/notebook/cfcf68ab-70a5-4c74-a205-574e81777e16",
        "desc": "Методички курсовой работы, практические задания 1-4, требования к расчету серверных стоек и сетей."
    },
    {
        "subject": "Системы искусственного интеллекта и большие данные (СИИБД)",
        "id": "a40ce267-445f-441a-9467-b4e6544c4447",
        "title": "Workbook 8: Methods of Clustering and Data Analysis",
        "url": "https://notebooklm.google.com/notebook/a40ce267-445f-441a-9467-b4e6544c4447",
        "desc": "Все 8 рабочих тетрадей, алгоритмы кластеризации (K-Means, DBSCAN), регрессия и нейросетевые пайплайны."
    },
    {
        "subject": "Архитектура ООП на Java (Car System Design)",
        "id": "57187a67-61d5-4684-8298-f3410b0de2de",
        "title": "Architectural Blueprint for the Car Class Registration System",
        "url": "https://notebooklm.google.com/notebook/57187a67-61d5-4684-8298-f3410b0de2de",
        "desc": "Объектно-ориентированная архитектура, разбор классов, наследования и полиморфизма на примере Car/Main."
    },
    {
        "subject": "Математический анализ (1 семестр)",
        "id": "b61efe0f-9b7f-4438-8792-79aa13671a79",
        "title": "МИРЭА: Математический анализ (1 семестр)",
        "url": "https://notebooklm.google.com/notebook/b61efe0f-9b7f-4438-8792-79aa13671a79",
        "desc": "Полный курс из 16 лекций, теория пределов, дифференциальное исчисление, шпаргалки для пересдачи."
    },
    {
        "subject": "Линейная алгебра и аналитическая геометрия",
        "id": "94b713d9-2a5b-4d7e-a4a1-8804bfd2031e",
        "title": "Cross and Mixed Products of Vectors",
        "url": "https://notebooklm.google.com/notebook/94b713d9-2a5b-4d7e-a4a1-8804bfd2031e",
        "desc": "13 лекций, векторные произведения, методы Крамера, Гаусса, матрицы, определители и СЛАУ."
    },
    {
        "subject": "Математическая логика и теория алгоритмов",
        "id": "6236ddcb-f6af-432a-bc5f-6144eea9d94b",
        "title": "Normal Forms of Boolean Functions",
        "url": "https://notebooklm.google.com/notebook/6236ddcb-f6af-432a-bc5f-6144eea9d94b",
        "desc": "16 лекций, минимизация булевых функций (СДНФ/СКНФ), карты Карно, исчисление высказываний и предикатов."
    },
    {
        "subject": "Иностранный язык в сфере IT (English IT)",
        "id": "a5cb58c1-d990-4d25-9fc0-fd3981437f70",
        "title": "IT English Mastery: Exam Preparation Guide",
        "url": "https://notebooklm.google.com/notebook/a5cb58c1-d990-4d25-9fc0-fd3981437f70",
        "desc": "Пособие для инженеров МИРЭА, профессиональный глоссарий, тексты для экзаменационного перевода."
    },
    {
        "subject": "Аналитическая практика (2026)",
        "id": "b2bb34fd-c4e1-4806-8900-a78b51adb0eb",
        "title": "МИРЭА: Аналитическая практика 2026",
        "url": "https://notebooklm.google.com/notebook/b2bb34fd-c4e1-4806-8900-a78b51adb0eb",
        "desc": "Материалы для сдачи практики, структура отчета, пример готовой исследовательской работы."
    }
]


def copy_file_safe(src: Path, dst: Path, overwrite: bool = True) -> bool:
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists() and not overwrite:
            return False
        shutil.copy2(src, dst)
        return True
    except Exception as exc:
        logger.warning("Failed copying %s to %s: %s", src.name, dst, exc)
        return False


def copy_tree_safe(src_dir: Path, dst_dir: Path, excludes=None, overwrite: bool = True) -> int:
    if not src_dir.exists():
        return 0
    copied = 0
    excl = set(excludes or [".git", "__pycache__", ".obsidian", ".pytest_cache"])
    
    for root, dirs, files in os.walk(src_dir):
        dirs[:] = [d for d in dirs if d not in excl and not d.startswith(".tmp")]
        rel = Path(root).relative_to(src_dir)
        target_sub = dst_dir / rel
        
        for f in files:
            if f == "desktop.ini" or f.endswith(".pyc") or f.startswith("~$"):
                continue
            src_f = Path(root) / f
            dst_f = target_sub / f
            if not dst_f.exists() or overwrite:
                if copy_file_safe(src_f, dst_f, overwrite=overwrite):
                    copied += 1
    return copied


def ensure_student_dirs(subject_dir: Path):
    (subject_dir / "Основы").mkdir(parents=True, exist_ok=True)
    for s in STUDENTS:
        (subject_dir / s).mkdir(parents=True, exist_ok=True)


def run_full_sync():
    if not DRIVE_BOBUSY_ROOT.exists():
        logger.error("Path 'G:\\My Drive\\бобусы' is not mounted!")
        return

    logger.info("Syncing comprehensive 3-Semester study hub to 'G:\\My Drive\\бобусы'...")

    sem1 = DRIVE_BOBUSY_ROOT / "01_Семестр_1"
    sem2 = DRIVE_BOBUSY_ROOT / "02_Семестр_2"
    sem3 = DRIVE_BOBUSY_ROOT / "03_Семестр_3"

    for d in (sem1, sem2, sem3):
        d.mkdir(parents=True, exist_ok=True)

    # ═════════════════════════════════════════════════════════════════════════
    # 01. СЕМЕСТР 1 (Базовые дисциплины и академические задолженности 1 курса)
    # ═════════════════════════════════════════════════════════════════════════
    sem1_subjects = [
        ("01_Математический_анализ_1", LOCAL_KNOWLEDGE_MIREA / "01_math_analysis"),
        ("02_Линейная_алгебра_1", LOCAL_KNOWLEDGE_MIREA / "02_linear_algebra"),
        ("03_Математическая_логика", LOCAL_KNOWLEDGE_MIREA / "03_math_logic"),
        ("04_Иностранный_язык_IT_1", LOCAL_KNOWLEDGE_MIREA / "04_english_it"),
    ]
    for s_name, s_src in sem1_subjects:
        s_dir = sem1 / s_name
        ensure_student_dirs(s_dir)
        if s_src.exists():
            copy_tree_safe(s_src, s_dir / "Основы")

    # Русский язык и культура речи
    rus_dir = sem1 / "05_Русский_язык_и_культура_речи"
    ensure_student_dirs(rus_dir)
    if (LOCAL_DOCUMENTS / "Русский язык и культура речи").exists():
        copy_tree_safe(LOCAL_DOCUMENTS / "Русский язык и культура речи", rus_dir / "Основы")

    # Физкультура 1
    fk1_dir = sem1 / "09_Физическая_культура_и_спорт_1"
    ensure_student_dirs(fk1_dir)
    if (LOCAL_DOCUMENTS / "Физическая культура и спорт").exists():
        copy_tree_safe(LOCAL_DOCUMENTS / "Физическая культура и спорт", fk1_dir / "Основы")

    # ═════════════════════════════════════════════════════════════════════════
    # 02. СЕМЕСТР 2 (Дисциплины и задолженности 2 семестра)
    # ═════════════════════════════════════════════════════════════════════════
    sem2_list = [
        "01_Математический_анализ_2",
        "02_Линейная_алгебра_2",
        "03_Физика",
        "04_Информатика_и_Архитектура_ЭВМ",
        "05_Объектно_ориентированное_программирование",
        "06_Иностранный_язык_IT_2",
        "07_История_России",
        "08_Физическая_культура_и_спорт_2"
    ]
    for s_name in sem2_list:
        s_dir = sem2 / s_name
        ensure_student_dirs(s_dir)

    # ═════════════════════════════════════════════════════════════════════════
    # 03. СЕМЕСТР 3 (Текущий активный семестр 2026 / 2 курс)
    # ═════════════════════════════════════════════════════════════════════════
    
    # 1. СИИБД
    ai_dir = sem3 / "01_Системы_искусственного_интеллекта_и_большие_данные"
    ensure_student_dirs(ai_dir)
    if (LOCAL_DOCUMENTS / "Системы искусственного интеллекта и большие данные").exists():
        copy_tree_safe(LOCAL_DOCUMENTS / "Системы искусственного интеллекта и большие данные", ai_dir / "Основы")
    if (LOCAL_STUDY_OS / "01_Disciplines" / "01_AI_and_Big_Data").exists():
        copy_tree_safe(LOCAL_STUDY_OS / "01_Disciplines" / "01_AI_and_Big_Data", ai_dir / "Основы")
    ai_lab_vaz = LOCAL_STUDY_OS / "02_Labs_and_Practices" / "Var_06_Vaz" / "AI_Lab_01_Var_06.md"
    if ai_lab_vaz.exists():
        copy_file_safe(ai_lab_vaz, ai_dir / "Жуков" / "AI_Lab_01_Var_06.md")

    # 2. ИТИ
    iti_dir = sem3 / "02_Информационно_технологическая_инфраструктура"
    ensure_student_dirs(iti_dir)
    if (LOCAL_DOCUMENTS / "Информационно-технологическая инфраструктура").exists():
        copy_tree_safe(LOCAL_DOCUMENTS / "Информационно-технологическая инфраструктура", iti_dir / "Основы")
    if (LOCAL_STUDY_OS / "01_Disciplines" / "02_IT_Infrastructure").exists():
        copy_tree_safe(LOCAL_STUDY_OS / "01_Disciplines" / "02_IT_Infrastructure", iti_dir / "Основы")

    # 3. Java ООП
    java_dir = sem3 / "03_Программирование_на_языке_Java_ООП"
    ensure_student_dirs(java_dir)
    if (LOCAL_DOCUMENTS / "java" / "Материалы_и_Практики_СДО").exists():
        copy_tree_safe(LOCAL_DOCUMENTS / "java" / "Материалы_и_Практики_СДО", java_dir / "Основы")
    if (LOCAL_DOCUMENTS / "java" / "1").exists():
        copy_tree_safe(LOCAL_DOCUMENTS / "java" / "1", java_dir / "Жуков" / "Практическая_1_Car_System")
    if (LOCAL_STUDY_OS / "01_Disciplines" / "03_Java_OOP").exists():
        copy_tree_safe(LOCAL_STUDY_OS / "01_Disciplines" / "03_Java_OOP", java_dir / "Основы")

    # 4. Электротехника
    ee_dir = sem3 / "04_Электротехника"
    ensure_student_dirs(ee_dir)
    if (LOCAL_DOCUMENTS / "Электротехника").exists():
        copy_tree_safe(LOCAL_DOCUMENTS / "Электротехника", ee_dir / "Основы")
    if (LOCAL_STUDY_OS / "01_Disciplines" / "07_Electrical_Engineering").exists():
        copy_tree_safe(LOCAL_STUDY_OS / "01_Disciplines" / "07_Electrical_Engineering", ee_dir / "Основы")

    # 5. Теория вычислительных процессов
    tvp_dir = sem3 / "05_Теория_вычислительных_процессов"
    ensure_student_dirs(tvp_dir)
    if (LOCAL_DOCUMENTS / "Теория вычислительных процессов").exists():
        copy_tree_safe(LOCAL_DOCUMENTS / "Теория вычислительных процессов", tvp_dir / "Основы")
    if (LOCAL_STUDY_OS / "01_Disciplines" / "06_Theory_of_Computation").exists():
        copy_tree_safe(LOCAL_STUDY_OS / "01_Disciplines" / "06_Theory_of_Computation", tvp_dir / "Основы")

    # 6. Архитектура вычислительных машин и систем
    arch_dir = sem3 / "06_Архитектура_вычислительных_машин_и_систем"
    ensure_student_dirs(arch_dir)
    if (LOCAL_DOCUMENTS / "Архитектура вычислительных машин и систем").exists():
        copy_tree_safe(LOCAL_DOCUMENTS / "Архитектура вычислительных машин и систем", arch_dir / "Основы")
    if (LOCAL_DOCUMENTS / "ИВБО-22-25").exists():
        copy_tree_safe(LOCAL_DOCUMENTS / "ИВБО-22-25", arch_dir / "Основы")

    # 7. Математический анализ 3
    ma3_dir = sem3 / "07_Математический_анализ_3"
    ensure_student_dirs(ma3_dir)
    if (LOCAL_DOCUMENTS / "Математический анализ 3").exists():
        copy_tree_safe(LOCAL_DOCUMENTS / "Математический анализ 3", ma3_dir / "Основы")

    # 8. Социальная психология и педагогика
    psy_dir = sem3 / "08_Социальная_психология_и_педагогика"
    ensure_student_dirs(psy_dir)
    if (LOCAL_DOCUMENTS / "Социальная психология и педагогика").exists():
        copy_tree_safe(LOCAL_DOCUMENTS / "Социальная психология и педагогика", psy_dir / "Основы")

    # 9. Философия
    phil_dir = sem3 / "09_Философия"
    ensure_student_dirs(phil_dir)
    if (LOCAL_DOCUMENTS / "Философия").exists():
        copy_tree_safe(LOCAL_DOCUMENTS / "Философия", phil_dir / "Основы")

    # 10. Аналитическая практика
    analyt_dir = sem3 / "10_Аналитическая_практика"
    ensure_student_dirs(analyt_dir)
    report_src = LOCAL_KNOWLEDGE_MIREA / "Отчет_Аналитическая_практика_Жуков_М_Д.docx"
    if report_src.exists():
        copy_file_safe(report_src, analyt_dir / "Жуков" / "Отчет_Аналитическая_практика_Жуков_М_Д.docx")

    # 11. Иностранный язык IT 3
    eng3_dir = sem3 / "11_Иностранный_язык_IT_3"
    ensure_student_dirs(eng3_dir)
    if (LOCAL_DOCUMENTS / "Иностранный язык (английский)").exists():
        copy_tree_safe(LOCAL_DOCUMENTS / "Иностранный язык (английский)", eng3_dir / "Основы")

    # ═════════════════════════════════════════════════════════════════════════
    # 04. ОБЩИЕ ХАБЫ (Книги, NotebookLM, ГОСТ, README)
    # ═════════════════════════════════════════════════════════════════════════
    
    # Книги и учебники
    books_dir = DRIVE_BOBUSY_ROOT / "Учебники и Книги для обучения"
    cs_dir = books_dir / "Компьютерные науки и Архитектура ЭВМ"
    math_dir = books_dir / "Высшая математика и Логика"
    ai_books_dir = books_dir / "Искусственный интеллект и Big Data"
    for d in (cs_dir, math_dir, ai_books_dir):
        d.mkdir(parents=True, exist_ok=True)

    arch_book_1 = LOCAL_DOCUMENTS / "Архитектура вычислительных машин и систем" / "Лекционные материалы (тексты)  Папка" / "Архитектура_ВМиС_Учебное пособие_2025.pdf"
    if arch_book_1.exists():
        copy_file_safe(arch_book_1, cs_dir / "Архитектура_ВМиС_Учебное_пособие_2025.pdf")

    arch_book_2 = LOCAL_DOCUMENTS / "Архитектура вычислительных машин и систем" / "Литература по дисциплине, источники  Папка" / "Архитектура_ВМиС_Учебное_пособие 2021.pdf"
    if arch_book_2.exists():
        copy_file_safe(arch_book_2, cs_dir / "Архитектура_ВМиС_Учебное_пособие_2021.pdf")

    java_book = LOCAL_DOCUMENTS / "java" / "Материалы_и_Практики_СДО" / "Литература по дисциплине, источники  Папка" / "2862.pdf"
    if java_book.exists():
        copy_file_safe(java_book, cs_dir / "Java_ООП_Учебно-методическое_пособие_2862.pdf")

    chelpanov_src = Path(r"C:\Users\Vaz\Documents\Саморазвитие\Конспекты_и_Заметки\chelpanov_uchebnik_logiki.md")
    if chelpanov_src.exists():
        copy_file_safe(chelpanov_src, math_dir / "Г_И_Челпанов_Учебник_Логики.md")

    # NotebookLM
    nlm_dir = DRIVE_BOBUSY_ROOT / "Материалы для изучения (NotebookLM)"
    nlm_dir.mkdir(parents=True, exist_ok=True)
    if LOCAL_NOTEBOOKLM_READY.exists():
        copy_tree_safe(LOCAL_NOTEBOOKLM_READY, nlm_dir)
    write_notebooklm_catalog(nlm_dir / "NOTEBOOKLM_CATALOG.md")

    # Шаблоны и ГОСТ
    if (LOCAL_STUDY_OS / "03_Templates").exists():
        copy_tree_safe(LOCAL_STUDY_OS / "03_Templates", DRIVE_BOBUSY_ROOT / "Шаблоны и ГОСТ")

    # Master README
    write_master_readme(DRIVE_BOBUSY_ROOT / "00_README_И_НАВИГАЦИЯ.md")

    logger.info("✅ Full 3-Semester study hub sync completed!")


def write_notebooklm_catalog(path: Path):
    content = [
        "# 🎓 Каталог Блокнотов Google NotebookLM для группы",
        "> **Цель:** Использование нейросетевых блокнотов Google NotebookLM для генерации аудиоподкастов (Audio Overview), ответов на вопросы по лекциям, составления карточек для запоминания и подготовки к зачетам/экзаменам.",
        "",
        "---",
        "",
        "## 🔗 Активные интерактивные блокноты",
        "",
        "| Предмет / Тема | Ссылка на Блокнот NotebookLM | Описание и применение |",
        "|:---|:---|:---|"
    ]
    for item in NOTEBOOKLM_LINKS:
        content.append(f"| **{item['subject']}** | [{item['title']}]({item['url']}) | {item['desc']} |")

    content.extend([
        "",
        "---",
        "",
        "## 🎙️ Как использовать блокноты команде:",
        "1. Перейдите по ссылке на нужный предмет.",
        "2. Нажмите **«Generate Audio Overview»** (Сгенерировать подкаст) — блокнот создаст 10-15 минутный живой диалог двух ведущих на английском/русском, полностью объясняющий всю тему занятия или лекции.",
        "3. В поле чата внизу введите любой сложный вопрос из билета — NotebookLM ответит со 100% точностью, опираясь только на загруженные лекции преподавателя без галлюцинаций.",
        "4. Используйте вкладку **«Study Guide»** и **«Briefing Doc»** для распечатки шпаргалок перед парами."
    ])
    path.write_text("\n".join(content), encoding="utf-8")


def write_master_readme(path: Path):
    content = [
        "# 🚀 Общий Учебный Хаб Группы («бобусы»)",
        "> **Направление:** 09.03.01 Информатика и вычислительная техника | Группа: **ИВБО-22-25**",
        "> **Команда:** Ваз (Жуков Максим, Вар. 6), Артём (Лунин Артём, Вар. 10), Вадим (Омельчак Вадим, Вар. 4).",
        "",
        "---",
        "",
        "## 📁 Академическая структура по 3 Семестрам",
        "",
        "### 🏛️ [01_Семестр_1](./01_Семестр_1) — Базовые дисциплины и долги 1 семестра",
        "- `01_Математический_анализ_1/`: 16 лекций (PDF), справочники формул, разборы экзаменационных билетов.",
        "- `02_Линейная_алгебра_1/`: 13 лекций, методы решения матриц и СЛАУ (Крамер, Гаусс).",
        "- `03_Математическая_логика/`: 16 лекций, минимизация булевых функций (СДНФ/СКНФ), предикаты.",
        "- `04_Иностранный_язык_IT_1/`: Пособие для инженеров МИРЭА, профессиональный словарь, топики.",
        "- `05_Русский_язык_и_культура_речи/`: Лекции, нормы речи, вопросы к зачетному тестированию.",
        "- `06_Основы_конструирования/`: ЕСКД, чертежи, методички практических работ.",
        "- `07_Ознакомительная_практика/`: Шаблоны дневников и индивидуальных заданий кафедры КИТПиПИ.",
        "- `08_Основы_российской_государственности/`: Вопросы к тестам СДО Moodle, эссе.",
        "- `09_Физическая_культура_и_спорт_1/`: Рефераты и методички атлетической гимнастики.",
        "",
        "### ⚙️ [02_Семестр_2](./02_Семестр_2) — Дисциплины и долги 2 семестра",
        "- `01_Математический_анализ_2/`: Интегралы, ряды, дифференциальные уравнения (РГР и билеты).",
        "- `02_Линейная_алгебра_2/`: Линейные операторы, квадратичные формы, евклидовы пространства.",
        "- `03_Физика/`: Лабораторный практикум по механике, оптике, электромагнетизму и квантовой физике.",
        "- `04_Информатика_и_Архитектура_ЭВМ/`: Базовая архитектура фон Неймана, основы Python/C++.",
        "- `05_Объектно_ориентированное_программирование/`: Курсовой проект по ООП, теория паттернов проектирования.",
        "- `06_Иностранный_язык_IT_2/`: Технический перевод профильной научной литературы.",
        "- `07_История_России/`: Хронологические таблицы, реформы, экзаменационные вопросы.",
        "- `08_Физическая_культура_и_спорт_2/`: Рефераты и зачетные требования.",
        "",
        "### 💻 [03_Семестр_3](./03_Семестр_3) — Текущий активный семестр (2026 / 2 курс)",
        "- `01_Системы_искусственного_интеллекта_и_большие_данные/`: Рабочие тетради 1-8, Pandas/NumPy предобработка, кластеризация.",
        "- `02_Информационно_технологическая_инфраструктура/`: Курсовая работа (ИТИ), практические 1-4, методички.",
        "- `03_Программирование_на_языке_Java_ООП/`: 8 лекций, 5 лабораторных работ, готовый проект Car System (Жуков).",
        "- `04_Электротехника/`: 8 лекций, методички TINA-TI, ДЗ-1 (мостовые схемы, 6x6 СЛАУ, баланс мощности).",
        "- `05_Теория_вычислительных_процессов/`: Практические работы 1-4, вопросы к дифференцированному зачету.",
        "- `06_Архитектура_вычислительных_машин_и_систем/`: Учебные пособия 2025/2021, Практикум 1 (Logisim, СДНФ/СКНФ).",
        "- `07_Математический_анализ_3/`: Демо-билеты, образцы контрольных, лекционные материалы.",
        "- `08_Социальная_психология_и_педагогика/`: Лекции, график консультаций БРС, литература.",
        "- `09_Философия/`: Хрестоматия, первоисточники, темы докладов и семинаров.",
        "- `10_Аналитическая_практика/`: Готовый отчет по практике 2026, структура оформления.",
        "- `11_Иностранный_язык_IT_3/`: Infotech English, критерии академического перевода.",
        "",
        "### 📚 Общесеместровые хабы",
        "- `Материалы для изучения (NotebookLM)/`: 8 активных блокнотов со ссылками, аудиоподкастами и карточками.",
        "- `Учебники и Книги для обучения/`: Книги по ИИ, архитектуре ЭВМ (Таненбаум), высшей математике и логике Челпанова.",
        "- `Шаблоны и ГОСТ/`: ГОСТ-шаблоны пояснительных записок, титульных листов и лабораторных отчетов.",
        "",
        "---",
        "",
        "## 🤝 Правила совместной работы команды",
        "1. В каждой дисциплине выделены папки: `Основы` (общие методички), `Жуков`, `Артём`, `Вадим`.",
        "2. Выкладывайте свои выполненные варианты в свою именную папку, чтобы не затирать чужой прогресс.",
        "3. Варианты группы: **Жуков М.Д. — Вариант 6**, **Лунин А.М. — Вариант 10**, **Омельчак В.С. — Вариант 4**."
    ]
    path.write_text("\n".join(content), encoding="utf-8")


if __name__ == "__main__":
    run_full_sync()
