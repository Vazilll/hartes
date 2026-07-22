# USER — Профиль пользователя и Контекст Системы

> Этот файл обновляется агентом по мере изучения предпочтений пользователя. Включается в system prompt.

## Основное
- **Имя**: Жуков М. Д. (zhukov.m.d1@edu.mirea.ru), вариант 5.
- **Род деятельности**: Студент РТУ МИРЭА + Full-stack AI-разработчик (Python, Go, Telegram боты, Hermes/MCP). Самозанятый.
- **AI-Бизнес**: Support Bot, Госзакупки Telegram, AI Salon Bot, AI Тендеры bot.
- **Платформа**: Windows 10/11
- **Язык общения**: Русский
- **Стек**: Go (primary), Python (ML only), Intel SYCL
- **IDE**: Opencode (terminal), Antigravity (VS Code)
- **Железо**: Intel CPU + Intel GPU (Arc / iGPU с SYCL)

## Предпочтения
- Максимально убирать Python → Go или Zig
- Privacy-first, всё локально
- Obsidian для заметок и памяти
- Предпочитает действие, а не длинные объяснения
- Не любит лишние вопросы — действуй, если можешь. Нулевая толерантность к ошибкам.

## Модели
- Gemini: через API key (AI Studio)
- Локальные модели для мобильных устройств (телефон)
- Интегрированные модели Antigravity (Claude, Gemini)

## Активный Бэклог Задач
1. **СДО МИРЭА (Академические долги)**:
   - Обнаружено 267 задолженностей по 22 курсам.
   - Материалы по 6 основным предметам выгружены в `C:\Users\Vaz\clawd-on-desk\course_materials`.
   - Задача: Начать отправку готовых решений по Матанализу (`handwritten_solutions.pdf`/`math_analysis_solutions.docx` на диске) и выгрузить контакты преподавателей.
2. **Модернизация Hermes**:
   - Внедрить RLM-память и защиту от Context Rot (разбивка на под-агентов, точечный поиск по базе вместо раздувания контекста).
   - Внедрить Диалектическое автокодирование (loop: Generator -> Linter/Tests -> Critic Reviewer -> Generator).
   - Интегрировать Graphify (построение кодовой базы в виде Knowledge Graph на tree-sitter для сокращения расхода токенов).
   - Реализовать Multi-Agent Missions (Factory: Orchestrator -> Workers -> Validators) с Validation Contracts и Structured Handoffs.
