#!/usr/bin/env python3
"""
sync_sem3_cohort_tasks.py — Populates all missing 3rd semester variant assignments
for the 3 cohort students:
  - Жуков Максим (Ваз) — Вариант 6
  - Лунин Артём — Вариант 10
  - Омельчак Вадим — Вариант 4
"""

import os
import sys
import shutil
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SEM3 = Path(r"G:\My Drive\бобусы\03_Семестр_3")
LOCAL_DOCS = Path(r"C:\Users\Vaz\Documents")
LOCAL_STUDY_OS = Path(r"C:\Users\Vaz\Documents\mirea_study_os")

STUDENTS = [
    {"name": "Жуков Максим Дмитриевич", "folder": "Жуков", "var": 6, "tvp_dir": "Для_Максима_Вариант_6"},
    {"name": "Лунин Артём Михайлович", "folder": "Артём", "var": 10, "tvp_dir": "Для_Артема_Вариант_10"},
    {"name": "Омельчак Вадим Сергеевич", "folder": "Вадим", "var": 4, "tvp_dir": "Для_Вадиса_Вариант_4"},
]

def sync_tvp():
    print("1. Syncing TVP (Теория вычислительных процессов)...")
    tvp_osn = SEM3 / "05_Теория_вычислительных_процессов" / "Основы"
    for st in STUDENTS:
        src = tvp_osn / st["tvp_dir"]
        dst = SEM3 / "05_Теория_вычислительных_процессов" / st["folder"]
        dst.mkdir(parents=True, exist_ok=True)
        if src.exists():
            for item in src.iterdir():
                if item.name != "desktop.ini":
                    target = dst / item.name
                    if item.is_dir():
                        shutil.copytree(item, target, dirs_exist_ok=True)
                    else:
                        shutil.copy2(item, target)
            print(f"   ✓ TVP copied to {st['folder']} from {st['tvp_dir']}")

def sync_ai():
    print("2. Syncing AI & Big Data (СИИБД) Labs...")
    ai_base = SEM3 / "01_Системы_искусственного_интеллекта_и_большие_данные"
    src_labs = LOCAL_STUDY_OS / "02_Labs_and_Practices"
    
    mapping = {
        "Жуков": src_labs / "Var_06_Vaz" / "AI_Lab_01_Var_06.md",
        "Артём": src_labs / "Var_10_Artyom" / "AI_Lab_01_Var_10.md",
        "Вадим": src_labs / "Var_04_Vadis" / "AI_Lab_01_Var_04.md"
    }
    for folder, src in mapping.items():
        dst = ai_base / folder / src.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.exists():
            shutil.copy2(src, dst)
            print(f"   ✓ Copied {src.name} -> {folder}")

def sync_java():
    print("3. Syncing Java Practice 1 (Car System)...")
    java_base = SEM3 / "03_Программирование_на_языке_Java_ООП"
    vaz_car = java_base / "Жуков" / "Практическая_1_Car_System"
    
    for st in STUDENTS:
        if st["folder"] == "Жуков": continue
        dst = java_base / st["folder"] / "Практическая_1_Car_System"
        dst.mkdir(parents=True, exist_ok=True)
        if vaz_car.exists():
            for item in vaz_car.iterdir():
                if item.name != "desktop.ini":
                    target = dst / item.name
                    if item.is_file():
                        shutil.copy2(item, target)
            # Create student readme
            (dst / "README.md").write_text(
                f"# Практическая работа №1: Разработка системы учёта автомобилей (Car System)\n"
                f"> **Дисциплина:** Программирование на языке Java (ООП)\n"
                f"> **Студент:** {st['name']} | **Группа:** ИВБО-22-25 | **Вариант:** {st['var']}\n\n"
                f"## 📋 Описание проекта:\n"
                f"- `Car.java`: Инкапсулированный класс сущности автомобиля с валидацией года выпуска (> 2000), неотрицательного пробега и неизменяемости модели.\n"
                f"- `Main.java`: Точка входа, демонстрация создания объектов, поездок и перекраски.\n",
                encoding="utf-8"
            )
            print(f"   ✓ Configured Java Practice 1 for {st['folder']}")

def sync_iti():
    print("4. Syncing IT Infrastructure (ИТИ) Coursework & Practicals...")
    iti_base = SEM3 / "02_Информационно_технологическая_инфраструктура"
    
    for st in STUDENTS:
        st_dir = iti_base / st["folder"]
        st_dir.mkdir(parents=True, exist_ok=True)
        
        # Coursework specification
        kr_file = st_dir / f"Курсовая_работа_ИТИ_Вариант_{st['var']:02d}.md"
        kr_file.write_text(
            f"# Курсовая работа: Проектирование корпоративной IT-инфраструктуры предприятия\n"
            f"> **Дисциплина:** Информационно-технологическая инфраструктура (ИТИ)\n"
            f"> **Студент:** {st['name']} | **Группа:** ИВБО-22-25 | **Вариант:** {st['var']}\n\n"
            f"--- \n\n"
            f"## 🎯 1. Исходные требования и параметры варианта {st['var']}\n"
            f"- **Количество автоматизированных рабочих мест (АРМ):** {st['var'] * 15 + 80} шт.\n"
            f"- **Топология сети:** Иерархическая (Core - Distribution - Access).\n"
            f"- **Требования к серверному сегменту:** Кластер отказоустойчивости VMware vSphere / Proxmox VE (2 ноды).\n"
            f"- **Система хранения данных (СХД):** SAN / NAS с RAID-10 (4x Enterprise SSD/HDD).\n"
            f"- **Резервное электропитание (ИБП):** Расчет мощности стоек с запасом 30% на 30 минут автономии.\n\n"
            f"--- \n\n"
            f"## 📑 2. План выполнения курсовой работы:\n"
            f"1. [ ] Анализ предметной области и расчет пропускной способности каналов передачи данных.\n"
            f"2. [ ] Выбор активного сетевого оборудования (коммутаторы L2/L3, маршрутизаторы Mikrotik/Eltex).\n"
            f"3. [ ] Расчет конфигурации серверных стоек (U), распределения питания (PDU) и тепловыделения.\n"
            f"4. [ ] Построение схемы сети в Cisco Packet Tracer / draw.io.\n"
            f"5. [ ] Оформление расчетно-пояснительной записки по ГОСТ 7.32-2017.\n",
            encoding="utf-8"
        )
        
        # Practicals 1-4 guide
        pr_file = st_dir / f"Практические_работы_1_4_Вариант_{st['var']:02d}.md"
        pr_file.write_text(
            f"# Практические работы №1–4: IT-инфраструктура\n"
            f"> **Студент:** {st['name']} | **Вариант:** {st['var']}\n\n"
            f"## Состав работ:\n"
            f"- **Практическая 1:** Архитектура локальных вычислительных сетей, адресация IPv4/IPv6, маски подсетей (CIDR).\n"
            f"- **Практическая 2:** Виртуализация вычислительных ресурсов, гипервизоры 1 и 2 типа.\n"
            f"- **Практическая 3:** Системы хранения данных, архитектуры DAS, NAS, SAN, уровни RAID.\n"
            f"- **Практическая 4:** Инженерная инфраструктура ЦОД: охлаждение (PUE), кабельные трассы (СКС), бесперебойное питание.\n",
            encoding="utf-8"
        )
        print(f"   ✓ Generated ITI tasks for {st['folder']}")

def sync_analytics_practice():
    print("5. Syncing Analytics Practice...")
    analyt_base = SEM3 / "10_Аналитическая_практика"
    for st in STUDENTS:
        if st["folder"] == "Жуков": continue
        st_dir = analyt_base / st["folder"]
        st_dir.mkdir(parents=True, exist_ok=True)
        report_file = st_dir / f"Шаблон_Отчета_Аналитическая_практика_{st['folder']}.md"
        report_file.write_text(
            f"# Отчет по Аналитической практике (2026)\n"
            f"> **Студент:** {st['name']} | **Группа:** ИВБО-22-25 | **Кафедра:** КИТПиПИ\n\n"
            f"## Структура для заполнения:\n"
            f"1. **Титульный лист:** Кафедра КИТПиПИ, направление 09.03.01.\n"
            f"2. **Индивидуальное задание:** Анализ предметной области и программного обеспечения.\n"
            f"3. **Методы исследования:** Сбор метрик, алгоритмический анализ, построение диаграмм.\n"
            f"4. **Результаты работы:** Сводные таблицы, графики производительности, выводы.\n",
            encoding="utf-8"
        )
        print(f"   ✓ Configured analytics practice template for {st['folder']}")

def main():
    sync_tvp()
    sync_ai()
    sync_java()
    sync_iti()
    sync_analytics_practice()
    print("\nALL_SEM3_COHORT_TASKS_SYNCED_SUCCESSFULLY")
    return 0

if __name__ == "__main__":
    sys.exit(main())
