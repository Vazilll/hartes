---
tags: [mirea, study, dashboard, university, debts, notebooklm]
created: 2026-08-23
aliases: [MIREA Master Dashboard, Академический центр МИРЭА]
---

# 🎓 МИРЭА: Академический Центр & Древо Обучения (1 курс)

> **Статус**: Критический фокус ликвидации академических долгов 1-го курса. Все 4 блокнота в **Google Gemini NotebookLM** созданы и укомплектованы официальными лекциями!
> **Таблица Excel**: [[C:/vazus/data/life_operating_system.xlsx|Открыть Master Excel]] | [[C:/vazus/data/mirea_learning_tree.csv|CSV]]

---

## 🌳 Древо Дисциплин 1-го курса

```mermaid
graph TD
    Root[🎓 МИРЭА 1 Курс] --> MA[📐 [[01_Math_Analysis|Математический анализ]]]
    Root --> LA[🔢 [[02_Linear_Algebra|Линейная алгебра и геометрия]]]
    Root --> ML[🧠 [[03_Math_Logic|Математическая логика и алгоритмы]]]
    Root --> ENG[🌐 [[04_English_IT|Иностранный язык для IT]]]

    MA --> MA_Docs[📁 16 лекций СДО]
    MA --> MA_NB[🔗 NotebookLM: Math Analysis]
    MA --> MA_Video[🎥 3Blue1Brown + МФТИ]

    LA --> LA_Docs[📁 13 лекций + Презентации]
    LA --> LA_NB[🔗 NotebookLM: Linear Algebra]
    LA --> LA_Video[🎥 3Blue1Brown + MIT Strang]

    ML --> ML_Docs[📁 16 лекций СДО]
    ML --> ML_NB[🔗 NotebookLM: Math Logic]
    ML --> ML_Video[🎥 CSC + Stepik]

    ENG --> ENG_Docs[📁 Пособие инженеров МИРЭА]
    ENG --> ENG_NB[🔗 NotebookLM: English IT]
    ENG --> ENG_Video[🎥 CS50 + Technical Comm]
```

---

## 📋 Сводная таблица дисциплин и быстрого перехода

| Предмет | Контроль | Официальные лекции СДО | Прямой AI Тьютор (NotebookLM) | Видеокурс | Статус |
|:---|:---:|:---:|:---:|:---:|:---:|
| [[01_Math_Analysis\|Математический анализ]] | Экзамен (1/3) | `16 лекций PDF` | [🚀 Открыть блокнот](https://notebook.google.com/notebook/b61efe0f-9b7f-4438-8792-79aa13671a79) | **3Blue1Brown + МФТИ** | 🟢 `ACTIVE_NOTEBOOK` |
| [[02_Linear_Algebra\|Линейная алгебра]] | Экзамен (1/2) | `13 лекций + 17 МБ` | [🚀 Открыть блокнот](https://notebook.google.com/notebook/94b713d9-2a5b-4d7e-a4a1-8804bfd2031e) | **3Blue1Brown + MIT Strang** | 🟢 `ACTIVE_NOTEBOOK` |
| [[03_Math_Logic\|Математическая логика]] | Экзамен (1/1) | `16 лекций PDF` | [🚀 Открыть блокнот](https://notebook.google.com/notebook/6236ddcb-f6af-432a-bc5f-6144eea9d94b) | **CSC + Stepik** | 🟢 `ACTIVE_NOTEBOOK` |
| [[04_English_IT\|Иностранный язык]] | Зачет (1/3) | `Пособие инженеров 16 МБ` | [🚀 Открыть блокнот](https://notebook.google.com/notebook/a5cb58c1-d990-4d25-9fc0-fd3981437f70) | **CS50 + Technical English** | 🟢 `ACTIVE_NOTEBOOK` |

---
%% Связанные заметки %%
- [[AI_Lessons_and_Mistakes]]
- [[Buy_Supplements_Task]]
