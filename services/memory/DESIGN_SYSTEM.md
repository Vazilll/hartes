# Vazus Design System — The Obsidian Neo-Brutalist Standard (SSOT)
*Authority: vazus SuperGraph OS | Tier 1 Architectural Invariant*
*References: Aeza Cloud Platform, Yandex Annushka (Habr 961768), Linear, Vercel*

---

## 🎯 1. Архитектурная философия
Интерфейсы в экосистеме Vazus — это профессиональные инженерные пульты управления, дашборды и презентационные платформы.
- **Главные ориентиры**: Максимальная эргономика, высокая плотность информации (High Information Density), строгий темный минимализм без аляповатости.
- **Абсолютный запрет**: Никаких дефолтных фиолетово-розовых градиентов из старых туториалов, никаких "грязных" серых плашек (`#808080`), никаких нестилизованных полос прокрутки.

---

## 🎨 2. Цветовая шкала (Obsidian Depth Scale)

| Уровень / Назначение | Точный цвет | Класс Tailwind / CSS |
| :--- | :--- | :--- |
| **L0 Base Canvas (Фон)** | `#08090c` | `bg-[#08090c]` |
| **L1 Surfaces (Карточки, Bento-блоки)** | `#0e1017` / `rgba(14, 16, 22, 0.75)` | `bg-[#0e1017]` или `.glass-panel` с `backdrop-blur-md` |
| **L2 Elevated (Модалки, Поповеры)** | `#141722` | `bg-[#141722]` |
| **Волосяные границы (Hairline Borders)** | `rgba(255, 255, 255, 0.07)` | `border border-white/[0.07]` |
| **Границы при наведении (Hover)** | `rgba(255, 255, 255, 0.16)` | `hover:border-white/[0.16]` |
| **Основной текст** | `#ededed` / `#ffffff` | `text-zinc-100` / `text-white` |
| **Приглушенный текст (Muted)** | `#888d9b` | `text-zinc-400` |
| **Микро-метки и подписи** | `#525866` | `text-zinc-500` |

### Статусные акценты (Neon on Obsidian)
- **Active / Success / Sync**: Emerald `#10b981` (`bg-emerald-500/10 text-emerald-400 border-emerald-500/20`) + пульсирующая точка `.radar-ping`.
- **Primary Action / Flow**: Cyan `#06b6d4` (`bg-cyan-500/10 text-cyan-400 border-cyan-500/20`).
- **Warning / Audit Attention**: Amber `#f59e0b` (`bg-amber-500/10 text-amber-400 border-amber-500/20`).
- **Critical / Drift / Error**: Rose `#f43f5e` (`bg-rose-500/10 text-rose-400 border-rose-500/20`).
- **AI / LLM Intelligence**: Violet `#8b5cf6` (`bg-violet-500/10 text-violet-400 border-violet-500/20`).

---

## 🔤 3. Типографика и Иерархия

1. **Заголовки и UI-элементы**:
   - Семейство: `Inter`, `Geist Sans`, `-apple-system`.
   - Кернинг: Обязательный `tracking-tight` (`letter-spacing: -0.025em`) на заголовках `h1`–`h4`.
2. **Инженерные данные (Monospace)**:
   - Семейство: `JetBrains Mono`, `Geist Mono`, `ui-monospace`.
   - Всё, что является числом, метрикой, IP-адресом, портом, Git-хэшем, таймштампом, статусом или бейджем — ОБЯЗАТЕЛЬНО рендерится в `font-mono text-xs`.

---

## 🧩 4. Компонентные паттерны

### 1. Bento Grid (Сетка карточек)
Все дашборды и слайды структурируются модульной сеткой:
`grid grid-cols-1 md:grid-cols-3 gap-4` с карточками разной ширины (например, 2/3 для главного графика/топологии и 1/3 для телеметрии).

### 2. Кнопки и контролы
- Кнопки компактные, с субтильным градиентом или плоским стеклом:
  `px-3 py-1.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-xs font-medium text-zinc-200 transition-all cursor-pointer`
- Акцентная кнопка:
  `bg-gradient-to-r from-cyan-500 to-indigo-600 hover:from-cyan-400 hover:to-indigo-500 text-white shadow-lg shadow-cyan-500/20`

### 3. Иконки
- Только библиотека `lucide-react`.
- Единая толщина линий: `strokeWidth={1.5}`.
- Стандартные размеры: `w-4 h-4` (в интерфейсе), `w-3.5 h-3.5` (в бейджах и кнопках).

---

## 🔄 5. Протокол валидации (Playwright Closed-Loop)
Каждый созданный или обновленный фронтенд обязан проходить проверку:
1. `npm run build` — 0 ошибок компиляции и типов.
2. Playwright headless navigation на `http://localhost:<port>/`:
   - `browser_console_messages` не содержат критических ошибок React/JS.
   - Проверка `scrollWidth <= innerWidth` (нет поломанной горизонтальной прокрутки).
