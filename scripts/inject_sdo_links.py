#!/usr/bin/env python3
"""
inject_sdo_links.py — Enriches all disciplines across Semesters 1, 2, and 3
with direct clickable hyperlinks to RTU MIREA Moodle SDO (online-edu.mirea.ru),
tests, quizzes, and verification manifests.
"""

import sys
import urllib.parse
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(r"G:\My Drive\бобусы")

SDO_COURSES = {
    # ── 01_Семестр_1 ──
    "01_Математический_анализ_1": {
        "title": "Математический анализ (1 семестр)",
        "url": "https://online-edu.mirea.ru/course/view.php?id=16479",
        "id": 16479,
        "links": [
            ("Входной тест", "https://online-edu.mirea.ru/mod/quiz/view.php?id=770652"),
            ("Итоговый тест", "https://online-edu.mirea.ru/mod/quiz/view.php?id=876076"),
            ("Вопросы к промежуточной аттестации", "https://online-edu.mirea.ru/mod/resource/view.php?id=768718"),
            ("Пример экзаменационного билета", "https://online-edu.mirea.ru/mod/resource/view.php?id=768719"),
        ]
    },
    "02_Линейная_алгебра_1": {
        "title": "Линейная алгебра и аналитическая геометрия (1 семестр)",
        "url": "https://online-edu.mirea.ru/course/view.php?id=16480",
        "id": 16480,
        "links": [
            ("Входной тест", "https://online-edu.mirea.ru/mod/quiz/view.php?id=790085"),
            ("Итоговый тест", "https://online-edu.mirea.ru/mod/quiz/view.php?id=793996"),
            ("Вопросы на сессию", "https://online-edu.mirea.ru/mod/resource/view.php?id=769127"),
            ("Образец экзаменационного билета", "https://online-edu.mirea.ru/mod/resource/view.php?id=842310"),
            ("Требования к экзамену", "https://online-edu.mirea.ru/mod/resource/view.php?id=828246"),
        ]
    },
    "03_Математическая_логика": {
        "title": "Математическая логика и теория алгоритмов",
        "url": "https://online-edu.mirea.ru/course/view.php?id=16486",
        "id": 16486,
        "links": [
            ("Итоговый тест (пересдача)", "https://online-edu.mirea.ru/mod/quiz/view.php?id=807390"),
            ("Итоговый тест", "https://online-edu.mirea.ru/mod/quiz/view.php?id=797827"),
            ("Вопросы на сессию", "https://online-edu.mirea.ru/mod/resource/view.php?id=768647"),
            ("Контрольная работа 1", "https://online-edu.mirea.ru/mod/resource/view.php?id=819619"),
            ("Контрольная работа 2", "https://online-edu.mirea.ru/mod/resource/view.php?id=826945"),
        ]
    },
    "04_Иностранный_язык_IT_1": {
        "title": "Иностранный язык (1 семестр)",
        "url": "https://online-edu.mirea.ru/course/view.php?id=16017",
        "id": 16017,
        "links": [
            ("Итоговый тест (пересдача)", "https://online-edu.mirea.ru/mod/quiz/view.php?id=766361"),
            ("Задание для допуска на пересдачу", "https://online-edu.mirea.ru/mod/quiz/view.php?id=974559"),
            ("Аттестация по английскому языку", "https://online-edu.mirea.ru/mod/resource/view.php?id=766419"),
            ("Вопросы на сессию", "https://online-edu.mirea.ru/mod/resource/view.php?id=845988"),
        ]
    },
    "05_Русский_язык_и_культура_речи": {
        "title": "Русский язык и культура речи",
        "url": "https://online-edu.mirea.ru/course/search.php?search=%D0%A0%D1%83%D1%81%D1%81%D0%BA%D0%B8%D0%B9+%D1%8F%D0%B7%D1%8B%D0%BA",
        "id": None,
        "links": [("Поиск курса в СДО", "https://online-edu.mirea.ru/course/search.php?search=%D0%A0%D1%83%D1%81%D1%81%D0%BA%D0%B8%D0%B9+%D1%8F%D0%B7%D1%8B%D0%BA")]
    },
    "06_Основы_конструирования": {
        "title": "Основы конструирования",
        "url": "https://online-edu.mirea.ru/course/search.php?search=%D0%9E%D1%81%D0%BD%D0%BE%D0%B2%D1%8B+%D0%BA%D0%BE%D0%BD%D1%81%D1%82%D1%80%D1%83%D0%B8%D1%80%D0%BE%D0%B2%D0%B0%D0%BD%D0%B8%D1%8F",
        "id": None,
        "links": [("Поиск курса в СДО", "https://online-edu.mirea.ru/course/search.php?search=%D0%9E%D1%81%D0%BD%D0%BE%D0%B2%D1%8B+%D0%BA%D0%BE%D0%BD%D1%81%D1%82%D1%80%D1%83%D0%B8%D1%80%D0%BE%D0%B2%D0%B0%D0%BD%D0%B8%D1%8F")]
    },
    "07_Ознакомительная_практика": {
        "title": "Ознакомительная практика",
        "url": "https://online-edu.mirea.ru/course/search.php?search=%D0%9E%D0%B7%D0%BD%D0%B0%D0%BA%D0%BE%D0%BC%D0%B8%D1%82%D0%B5%D0%BB%D1%8C%D0%BD%D0%B0%D1%8F+%D0%BF%D1%80%D0%B0%D0%BA%D1%82%D0%B8%D0%BA%D0%B0",
        "id": None,
        "links": [("Поиск курса в СДО", "https://online-edu.mirea.ru/course/search.php?search=%D0%9E%D0%B7%D0%BD%D0%B0%D0%BA%D0%BE%D0%BC%D0%B8%D1%82%D0%B5%D0%BB%D1%8C%D0%BD%D0%B0%D1%8F+%D0%BF%D1%80%D0%B0%D0%BA%D1%82%D0%B8%D0%BA%D0%B0")]
    },
    "08_Основы_российской_государственности": {
        "title": "Основы российской государственности",
        "url": "https://online-edu.mirea.ru/course/search.php?search=%D0%9E%D1%81%D0%BD%D0%BE%D0%B2%D1%8B+%D1%80%D0%BE%D1%81%D1%81%D0%B8%D0%B9%D1%81%D0%BA%D0%BE%D0%B9+%D0%B3%D0%BE%D1%81%D1%83%D0%B4%D0%B0%D1%80%D1%81%D1%82%D0%B2%D0%B5%D0%BD%D0%BD%D0%BE%D1%81%D1%82%D0%B8",
        "id": None,
        "links": [("Поиск курса в СДО", "https://online-edu.mirea.ru/course/search.php?search=%D0%9E%D1%81%D0%BD%D0%BE%D0%B2%D1%8B+%D1%80%D0%BE%D1%81%D1%81%D0%B8%D0%B9%D1%81%D0%BA%D0%BE%D0%B9+%D0%B3%D0%BE%D1%81%D1%83%D0%B4%D0%B0%D1%80%D1%81%D1%82%D0%B2%D0%B5%D0%BD%D0%BD%D0%BE%D1%81%D1%82%D0%B8")]
    },
    "09_Физическая_культура_и_спорт_1": {
        "title": "Физическая культура и спорт (1 семестр)",
        "url": "https://online-edu.mirea.ru/course/search.php?search=%D0%A4%D0%B8%D0%B7%D0%B8%D1%87%D0%B5%D1%81%D0%BA%D0%B0%D1%8F+%D0%BA%D1%83%D0%BB%D1%8C%D1%82%D1%83%D1%80%D0%B0",
        "id": None,
        "links": [("Поиск курса в СДО", "https://online-edu.mirea.ru/course/search.php?search=%D0%A4%D0%B8%D0%B7%D0%B8%D1%87%D0%B5%D1%81%D0%BA%D0%B0%D1%8F+%D0%BA%D1%83%D0%BB%D1%8C%D1%82%D1%83%D1%80%D0%B0")]
    },

    # ── 02_Семестр_2 ──
    "01_Математический_анализ_2": {
        "title": "Математический анализ (2 семестр)",
        "url": "https://online-edu.mirea.ru/course/view.php?id=16479",
        "id": 16479,
        "links": [
            ("Курс в СДО Moodle", "https://online-edu.mirea.ru/course/view.php?id=16479"),
            ("Итоговый тест", "https://online-edu.mirea.ru/mod/quiz/view.php?id=876076"),
            ("Пример билета и критерии", "https://online-edu.mirea.ru/mod/resource/view.php?id=768719"),
        ]
    },
    "02_Линейная_алгебра_2": {
        "title": "Линейная алгебра и геометрия (2 семестр)",
        "url": "https://online-edu.mirea.ru/course/view.php?id=16480",
        "id": 16480,
        "links": [
            ("Курс в СДО Moodle", "https://online-edu.mirea.ru/course/view.php?id=16480"),
            ("Итоговый тест", "https://online-edu.mirea.ru/mod/quiz/view.php?id=793996"),
            ("Вопросы на сессию", "https://online-edu.mirea.ru/mod/resource/view.php?id=769127"),
        ]
    },
    "03_Физика": {
        "title": "Общая физика",
        "url": "https://online-edu.mirea.ru/course/search.php?search=%D0%A4%D0%B8%D0%B7%D0%B8%D0%BA%D0%B0",
        "id": None,
        "links": [("Поиск курса в СДО", "https://online-edu.mirea.ru/course/search.php?search=%D0%A4%D0%B8%D0%B7%D0%B8%D0%BA%D0%B0")]
    },
    "04_Информатика_и_Архитектура_ЭВМ": {
        "title": "Информатика и Архитектура ЭВМ",
        "url": "https://online-edu.mirea.ru/course/search.php?search=%D0%98%D0%BD%D1%84%D0%BE%D1%80%D0%BC%D0%B0%D1%82%D0%B8%D0%BA%D0%B0",
        "id": None,
        "links": [("Поиск курса в СДО", "https://online-edu.mirea.ru/course/search.php?search=%D0%98%D0%BD%D1%84%D0%BE%D1%80%D0%BC%D0%B0%D1%82%D0%B8%D0%BA%D0%B0")]
    },
    "05_Объектно_ориентированное_программирование": {
        "title": "Объектно-ориентированное программирование",
        "url": "https://online-edu.mirea.ru/course/search.php?search=%D0%9E%D0%B1%D1%8A%D0%B5%D0%BA%D1%82%D0%BD%D0%BE-%D0%BE%D1%80%D0%B8%D0%B5%D0%BD%D1%82%D0%B8%D1%80%D0%BE%D0%B2%D0%B0%D0%BD%D0%BD%D0%BE%D0%B5",
        "id": None,
        "links": [("Поиск курса в СДО", "https://online-edu.mirea.ru/course/search.php?search=%D0%9E%D0%B1%D1%8A%D0%B5%D0%BA%D1%82%D0%BD%D0%BE-%D0%BE%D1%80%D0%B8%D0%B5%D0%BD%D1%82%D0%B8%D1%80%D0%BE%D0%B2%D0%B0%D0%BD%D0%BD%D0%BE%D0%B5")]
    },
    "06_Иностранный_язык_IT_2": {
        "title": "Иностранный язык (2 семестр)",
        "url": "https://online-edu.mirea.ru/course/view.php?id=16017",
        "id": 16017,
        "links": [
            ("Курс в СДО Moodle", "https://online-edu.mirea.ru/course/view.php?id=16017"),
            ("Итоговый тест", "https://online-edu.mirea.ru/mod/quiz/view.php?id=766361"),
        ]
    },
    "07_История_России": {
        "title": "История России",
        "url": "https://online-edu.mirea.ru/course/search.php?search=%D0%98%D1%81%D1%82%D0%BE%D1%80%D0%B8%D1%8F+%D0%A0%D0%BE%D1%81%D1%81%D0%B8%D0%B8",
        "id": None,
        "links": [("Поиск курса в СДО", "https://online-edu.mirea.ru/course/search.php?search=%D0%98%D1%81%D1%82%D0%BE%D1%80%D0%B8%D1%8F+%D0%A0%D0%BE%D1%81%D1%81%D0%B8%D0%B8")]
    },
    "08_Физическая_культура_и_спорт_2": {
        "title": "Физическая культура и спорт (2 семестр)",
        "url": "https://online-edu.mirea.ru/course/search.php?search=%D0%A4%D0%B8%D0%B7%D0%B8%D1%87%D0%B5%D1%81%D0%BA%D0%B0%D1%8F+%D0%BA%D1%83%D0%BB%D1%8C%D1%82%D1%83%D1%80%D0%B0",
        "id": None,
        "links": [("Поиск курса в СДО", "https://online-edu.mirea.ru/course/search.php?search=%D0%A4%D0%B8%D0%B7%D0%B8%D1%87%D0%B5%D1%81%D0%BA%D0%B0%D1%8F+%D0%BA%D1%83%D0%BB%D1%8C%D1%82%D1%83%D1%80%D0%B0")]
    },

    # ── 03_Семестр_3 ──
    "01_Системы_искусственного_интеллекта_и_большие_данные": {
        "title": "Системы ИИ и большие данные",
        "url": "https://online-edu.mirea.ru/course/search.php?search=%D0%A1%D0%B8%D1%81%D1%82%D0%B5%D0%BC%D1%8B+%D0%B8%D1%81%D0%BA%D1%83%D1%81%D1%81%D1%82%D0%B2%D0%B5%D0%BD%D0%BD%D0%BE%D0%B3%D0%BE+%D0%B8%D0%BD%D1%82%D0%B5%D0%BB%D0%BB%D0%B5%D0%BA%D1%82%D0%B0",
        "id": None,
        "links": [("Поиск в СДО", "https://online-edu.mirea.ru/course/search.php?search=%D0%A1%D0%B8%D1%81%D1%82%D0%B5%D0%BC%D1%8B+%D0%B8%D1%81%D0%BA%D1%83%D1%81%D1%81%D1%82%D0%B2%D0%B5%D0%BD%D0%BD%D0%BE%D0%B3%D0%BE+%D0%B8%D0%BD%D1%82%D0%B5%D0%BB%D0%BB%D0%B5%D0%BA%D1%82%D0%B0")]
    },
    "02_Информационно_технологическая_инфраструктура": {
        "title": "Информационно-технологическая инфраструктура",
        "url": "https://online-edu.mirea.ru/course/search.php?search=%D0%98%D0%BD%D1%84%D0%BE%D1%80%D0%BC%D0%B0%D1%82%D0%B8%D0%BA%D0%B0",
        "id": None,
        "links": [("Поиск в СДО", "https://online-edu.mirea.ru/course/search.php?search=%D0%98%D0%BD%D1%84%D0%BE%D1%80%D0%BC%D0%B0%D1%82%D0%B8%D1%86%D0%B8%D0%BE%D0%BD%D0%BD%D0%BE-%D1%82%D0%B5%D1%85%D0%BD%D0%BE%D0%BB%D0%BE%D0%B3%D0%B8%D1%87%D0%B5%D1%81%D0%BA%D0%B0%D1%8F")]
    },
    "03_Программирование_на_языке_Java_ООП": {
        "title": "Программирование на языке Java (ООП)",
        "url": "https://online-edu.mirea.ru/course/search.php?search=Java",
        "id": None,
        "links": [("Поиск в СДО", "https://online-edu.mirea.ru/course/search.php?search=Java")]
    },
    "04_Электротехника": {
        "title": "Электротехника и электроника",
        "url": "https://online-edu.mirea.ru/course/search.php?search=%D0%AD%D0%BB%D0%B5%D0%BA%D1%82%D1%80%D0%BE%D1%82%D0%B5%D1%85%D0%BD%D0%B8%D0%BA%D0%B0",
        "id": None,
        "links": [("Поиск в СДО", "https://online-edu.mirea.ru/course/search.php?search=%D0%AD%D0%BB%D0%B5%D0%BA%D1%82%D1%80%D0%BE%D1%82%D0%B5%D1%85%D0%BD%D0%B8%D0%BA%D0%B0")]
    },
    "05_Теория_вычислительных_процессов": {
        "title": "Теория вычислительных процессов",
        "url": "https://online-edu.mirea.ru/course/search.php?search=%D0%A2%D0%B5%D0%BE%D1%80%D0%B8%D1%8F+%D0%B2%D1%8B%D1%87%D0%B8%D1%81%D0%BB%D0%B8%D1%82%D0%B5%D0%BB%D1%8C%D0%BD%D1%8B%D1%85+%D0%BF%D1%80%D0%BE%D1%86%D0%B5%D1%81%D1%81%D0%BE%D0%B2",
        "id": None,
        "links": [("Поиск в СДО", "https://online-edu.mirea.ru/course/search.php?search=%D0%A2%D0%B5%D0%BE%D1%80%D0%B8%D1%8F+%D0%B2%D1%8B%D1%87%D0%B8%D1%81%D0%BB%D0%B8%D1%82%D0%B5%D0%BB%D1%8C%D0%BD%D1%8B%D1%85+%D0%BF%D1%80%D0%BE%D1%86%D0%B5%D1%81%D1%81%D0%BE%D0%B2")]
    },
    "06_Архитектура_вычислительных_машин_и_систем": {
        "title": "Архитектура вычислительных машин и систем",
        "url": "https://online-edu.mirea.ru/course/search.php?search=%D0%90%D1%80%D1%85%D0%B8%D1%82%D0%B5%D0%BA%D1%82%D1%83%D1%80%D0%B0+%D0%B2%D1%8B%D1%87%D0%B8%D1%81%D0%BB%D0%B8%D1%82%D0%B5%D0%BB%D1%8C%D0%BD%D1%8B%D1%85",
        "id": None,
        "links": [("Поиск в СДО", "https://online-edu.mirea.ru/course/search.php?search=%D0%90%D1%80%D1%85%D0%B8%D1%82%D0%B5%D0%BA%D1%82%D1%83%D1%80%D0%B0+%D0%B2%D1%8B%D1%87%D0%B8%D1%81%D0%BB%D0%B8%D1%82%D0%B5%D0%BB%D1%8C%D0%BD%D1%8B%D1%85")]
    },
    "07_Математический_анализ_3": {
        "title": "Математический анализ (3 семестр)",
        "url": "https://online-edu.mirea.ru/course/search.php?search=%D0%9C%D0%B0%D1%82%D0%B5%D0%BC%D0%B0%D1%82%D0%B8%D1%87%D0%B5%D1%81%D0%BA%D0%B8%D0%B9+%D0%B0%D0%BD%D0%B0%D0%BB%D0%B8%D0%B7",
        "id": None,
        "links": [("Поиск в СДО", "https://online-edu.mirea.ru/course/search.php?search=%D0%9C%D0%B0%D1%82%D0%B5%D0%BC%D0%B0%D1%82%D0%B8%D1%87%D0%B5%D1%81%D0%BA%D0%B8%D0%B9+%D0%B0%D0%BD%D0%B0%D0%BB%D0%B8%D0%B7")]
    },
    "08_Социальная_психология_и_педагогика": {
        "title": "Социальная психология и педагогика",
        "url": "https://online-edu.mirea.ru/course/search.php?search=%D0%A1%D0%BE%D1%86%D0%B8%D0%B0%D0%BB%D1%8C%D0%BD%D0%B0%D1%8F+%D0%BF%D1%81%D0%B8%D1%85%D0%BE%D0%BB%D0%BE%D0%B3%D0%B8%D1%8F",
        "id": None,
        "links": [("Поиск в СДО", "https://online-edu.mirea.ru/course/search.php?search=%D0%A1%D0%BE%D1%86%D0%B8%D0%B0%D0%BB%D1%8C%D0%BD%D0%B0%D1%8F+%D0%BF%D1%81%D0%B8%D1%85%D0%BE%D0%BB%D0%BE%D0%B3%D0%B8%D1%8F")]
    },
    "09_Философия": {
        "title": "Философия",
        "url": "https://online-edu.mirea.ru/course/search.php?search=%D0%A4%D0%B8%D0%BB%D0%BE%D1%81%D0%BE%D1%84%D0%B8%D1%8F",
        "id": None,
        "links": [("Поиск в СДО", "https://online-edu.mirea.ru/course/search.php?search=%D0%A4%D0%B8%D0%BB%D0%BE%D1%81%D0%BE%D1%84%D0%B8%D1%8F")]
    },
    "10_Аналитическая_практика": {
        "title": "Аналитическая практика (2026)",
        "url": "https://online-edu.mirea.ru/course/search.php?search=%D0%90%D0%BD%D0%B0%D0%BB%D0%B8%D1%82%D0%B8%D1%87%D0%B5%D1%81%D0%BA%D0%B0%D1%8F+%D0%BF%D1%80%D0%B0%D0%BA%D1%82%D0%B8%D0%BA%D0%B0",
        "id": None,
        "links": [("Поиск в СДО", "https://online-edu.mirea.ru/course/search.php?search=%D0%90%D0%BD%D0%B0%D0%BB%D0%B8%D1%82%D0%B8%D1%87%D0%B5%D1%81%D0%BA%D0%B0%D1%8F+%D0%BF%D1%80%D0%B0%D0%BA%D1%82%D0%B8%D0%BA%D0%B0")]
    },
    "11_Иностранный_язык_IT_3": {
        "title": "Иностранный язык (3 семестр)",
        "url": "https://online-edu.mirea.ru/course/view.php?id=16017",
        "id": 16017,
        "links": [
            ("Курс в СДО Moodle", "https://online-edu.mirea.ru/course/view.php?id=16017"),
        ]
    }
}

def enrich_readme_files():
    print("Enriching README files across all semesters with direct SDO hyperlinks...")
    for sem in ["01_Семестр_1", "02_Семестр_2", "03_Семестр_3"]:
        sem_dir = ROOT / sem
        if not sem_dir.exists(): continue
        for subj in sem_dir.iterdir():
            if not subj.is_dir(): continue
            osn = subj / "Основы"
            osn.mkdir(parents=True, exist_ok=True)
            readme = osn / "README.md"
            
            sdo_info = SDO_COURSES.get(subj.name)
            if not sdo_info: continue
            
            sdo_header = f"""# 🏛️ {sdo_info['title']}
> **Прямая ссылка на курс в СДО:** [{sdo_info['url']}]({sdo_info['url']})  
> **Личный кабинет студента (ЛКС):** [https://lk.mirea.ru](https://lk.mirea.ru) | **Аттестация:** [https://online-edu.mirea.ru/my/](https://online-edu.mirea.ru/my/)

## 🔗 Быстрый переход к тестам и контрольным работам СДО:
"""
            for name, url in sdo_info.get("links", []):
                sdo_header += f"- 📝 [{name}]({url})\n"
            
            sdo_header += "\n---\n\n"
            
            # Read existing content if any
            existing = ""
            if readme.exists():
                existing = readme.read_text(encoding="utf-8")
                # Remove old SDO header if present
                if "# 🏛️" in existing and "---" in existing:
                    parts = existing.split("---", 1)
                    existing = parts[1].strip() if len(parts) > 1 else existing
            
            new_content = sdo_header + existing
            readme.write_text(new_content, encoding="utf-8")
            print(f"  ✓ Updated SDO links in {sem}/{subj.name}/Основы/README.md")

def main():
    enrich_readme_files()
    print("ALL_SDO_HYPERLINKS_INJECTED_SUCCESSFULLY")
    return 0

if __name__ == "__main__":
    sys.exit(main())
