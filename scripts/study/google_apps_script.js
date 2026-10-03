// ============================================================================
// DNTS Brain — Google Apps Script
// Автоматическая генерация brain_state.md
// ============================================================================
//
// Что делает скрипт:
//   1. Читает последние 5 .md файлов из папки "dialogues cli" (внутри "ai")
//   2. Суммаризирует их через Gemini 2.5 Flash API
//   3. Читает профиль пользователя из USER.md (если есть на Google Drive)
//   4. Читает заметки из Google Sheet "DNTS Notes" (замена Google Keep)
//   5. Генерирует brain_state.md на русском языке
//   6. Сохраняет результат в папку "ai" на Google Drive
//   7. Логирует результаты в sync.log
//
// API-ключ хранится в Script Properties → GEMINI_API_KEY
// ============================================================================

// ─── Константы ───────────────────────────────────────────────────────────────

/** Имя корневой папки на Google Drive */
const AI_FOLDER_NAME = 'ai';

/** Имя подпапки с диалогами */
const DIALOGUES_FOLDER_NAME = 'dialogues cli';

/** Сколько последних диалогов читать */
const MAX_DIALOGUES = 5;

/** Имя файла профиля пользователя */
const USER_PROFILE_FILENAME = 'USER.md';

/** Имя Google Sheet с заметками (замена Google Keep) */
const NOTES_SHEET_NAME = 'DNTS Notes';

/** Имя выходного файла */
const OUTPUT_FILENAME = 'brain_state.md';

/** Имя лог-файла */
const LOG_FILENAME = 'sync.log';

/** Модель Gemini для суммаризации */
const GEMINI_MODEL = 'gemini-3.5-flash';

/** URL Gemini API */
const GEMINI_API_URL = `https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent`;


// ─── Захардкоженный профиль (фолбэк) ────────────────────────────────────────

/**
 * Возвращает профиль пользователя по умолчанию,
 * если USER.md не найден на Google Drive.
 */
function getDefaultProfile() {
  return [
    '## 👤 Профиль',
    '',
    '- **Имя:** Жуков М. Д.',
    '- **Статус:** студент РТУ МИРЭА',
    '- **Стек:** Go, Python (только ML), Intel SYCL',
    '- **Проекты:** Hermes, Clawd on Desk, DNTS Brain',
    '- **Академические долги:** 267',
    '- **Принципы:** privacy-first, действие важнее объяснений',
    ''
  ].join('\n');
}


// ─── Основная функция ───────────────────────────────────────────────────────

/**
 * Главная точка входа. Вызывается по триггеру или вручную.
 * Собирает все данные, генерирует brain_state.md и сохраняет на Drive.
 */
function generateBrainState() {
  const startTime = new Date();
  const log = [];

  log.push(`[${startTime.toISOString()}] ▶ Запуск синхронизации DNTS Brain`);

  try {
    // ── 1. Найти папку "ai" ──────────────────────────────────────────────
    const aiFolder = findFolder_(AI_FOLDER_NAME);
    if (!aiFolder) {
      throw new Error(`Папка "${AI_FOLDER_NAME}" не найдена на Google Drive`);
    }
    log.push(`[info] Папка "${AI_FOLDER_NAME}" найдена: ${aiFolder.getId()}`);

    // ── 2. Прочитать последние 5 диалогов ────────────────────────────────
    log.push(`[info] Поиск диалогов в "${DIALOGUES_FOLDER_NAME}"...`);
    const dialogues = readLastDialogues_(aiFolder);
    log.push(`[info] Найдено диалогов: ${dialogues.length}`);

    // ── 3. Суммаризировать диалоги через Gemini API ──────────────────────
    let summaries = [];
    if (dialogues.length > 0) {
      log.push(`[info] Отправка ${dialogues.length} диалогов на суммаризацию...`);
      summaries = summarizeDialogues_(dialogues);
      log.push(`[info] Суммаризация завершена, получено ${summaries.length} саммари`);
    } else {
      log.push(`[warn] Диалоги не найдены, пропуск суммаризации`);
    }

    // ── 4. Прочитать профиль пользователя ────────────────────────────────
    log.push(`[info] Поиск ${USER_PROFILE_FILENAME} на Google Drive...`);
    const profile = readUserProfile_();
    log.push(`[info] Профиль: ${profile.source}`);

    // ── 5. Прочитать заметки из Google Sheet ──────────────────────────────
    log.push(`[info] Чтение заметок из "${NOTES_SHEET_NAME}"...`);
    const notes = readNotesFromSheet_();
    log.push(`[info] Заметок найдено: ${notes.length}`);

    // ── 6. Собрать brain_state.md ────────────────────────────────────────
    const brainState = composeBrainState_(profile.content, summaries, notes);
    log.push(`[info] brain_state.md собран (${brainState.length} символов)`);

    // ── 7. Сохранить на Google Drive ─────────────────────────────────────
    saveFileToDrive_(aiFolder, OUTPUT_FILENAME, brainState);
    log.push(`[info] ${OUTPUT_FILENAME} сохранён в папку "${AI_FOLDER_NAME}"`);

    const elapsed = ((new Date() - startTime) / 1000).toFixed(1);
    log.push(`[${new Date().toISOString()}] ✔ Синхронизация завершена за ${elapsed}с`);

  } catch (error) {
    log.push(`[ERROR] ${error.message}`);
    log.push(`[${new Date().toISOString()}] ✖ Синхронизация прервана с ошибкой`);
    Logger.log(`DNTS Brain Error: ${error.message}\n${error.stack}`);
  }

  // ── 8. Записать лог ──────────────────────────────────────────────────────
  try {
    const aiFolder = findFolder_(AI_FOLDER_NAME);
    if (aiFolder) {
      appendLog_(aiFolder, log.join('\n') + '\n\n');
    }
  } catch (logError) {
    Logger.log(`Ошибка записи лога: ${logError.message}`);
  }

  // Дублируем в стандартный логгер Apps Script
  Logger.log(log.join('\n'));
}


// ─── Работа с файловой системой Google Drive ─────────────────────────────────

/**
 * Ищет папку по имени на верхнем уровне Google Drive.
 * @param {string} name — имя папки
 * @returns {DriveApp.Folder|null}
 */
function findFolder_(name) {
  const folders = DriveApp.getFoldersByName(name);
  return folders.hasNext() ? folders.next() : null;
}

/**
 * Ищет подпапку внутри указанной родительской папки.
 * @param {DriveApp.Folder} parent — родительская папка
 * @param {string} name — имя подпапки
 * @returns {DriveApp.Folder|null}
 */
function findSubfolder_(parent, name) {
  const folders = parent.getFoldersByName(name);
  return folders.hasNext() ? folders.next() : null;
}

/**
 * Читает последние MAX_DIALOGUES markdown-файлов из папки "dialogues cli".
 * Сортирует по дате последнего изменения (новые первые).
 *
 * @param {DriveApp.Folder} aiFolder — папка "ai"
 * @returns {Array<{name: string, content: string, date: Date}>}
 */
function readLastDialogues_(aiFolder) {
  const dialoguesFolder = findSubfolder_(aiFolder, DIALOGUES_FOLDER_NAME);
  if (!dialoguesFolder) {
    Logger.log(`Подпапка "${DIALOGUES_FOLDER_NAME}" не найдена внутри "${AI_FOLDER_NAME}"`);
    return [];
  }

  // Сначала собираем только метаданные (без чтения содержимого!)
  // В папке ~236 файлов, читать все — превышает лимит Drive API
  const fileMeta = [];
  const files = dialoguesFolder.getFiles();

  while (files.hasNext()) {
    const file = files.next();
    const fileName = file.getName();

    if (fileName.endsWith('.md') || fileName.endsWith('.markdown')) {
      fileMeta.push({
        name: fileName,
        file: file
      });
    }
  }

  // Сортируем по имени (формат "2026-06-21 - ... .md" → новые последние)
  fileMeta.sort((a, b) => b.name.localeCompare(a.name));

  // Берём только последние N и ТОЛЬКО для них читаем содержимое
  const result = [];
  const top = fileMeta.slice(0, MAX_DIALOGUES);
  for (const item of top) {
    try {
      result.push({
        name: item.name,
        content: item.file.getBlob().getDataAsString(),
        date: item.file.getLastUpdated()
      });
    } catch (e) {
      log_('[WARN] Не удалось прочитать ' + item.name + ': ' + e.message);
    }
  }

  return result;
}

/**
 * Сохраняет (или перезаписывает) файл в указанной папке на Google Drive.
 *
 * @param {DriveApp.Folder} folder — целевая папка
 * @param {string} fileName — имя файла
 * @param {string} content — содержимое
 */
function saveFileToDrive_(folder, fileName, content) {
  // Проверяем, существует ли файл
  const existingFiles = folder.getFilesByName(fileName);

  if (existingFiles.hasNext()) {
    // Перезаписываем существующий файл
    const file = existingFiles.next();
    file.setContent(content);
  } else {
    // Создаём новый файл
    folder.createFile(fileName, content, MimeType.PLAIN_TEXT);
  }
}

/**
 * Дописывает текст в лог-файл. Если файла нет — создаёт.
 *
 * @param {DriveApp.Folder} folder — папка для лога
 * @param {string} entry — текст для добавления
 */
function appendLog_(folder, entry) {
  const existingFiles = folder.getFilesByName(LOG_FILENAME);

  if (existingFiles.hasNext()) {
    const file = existingFiles.next();
    const currentContent = file.getBlob().getDataAsString();

    // Ограничиваем размер лога (последние ~50КБ)
    const maxLogSize = 50 * 1024;
    let newContent = currentContent + entry;
    if (newContent.length > maxLogSize) {
      // Обрезаем старые записи
      newContent = newContent.slice(newContent.length - maxLogSize);
      // Обрезаем до ближайшего полного блока записи
      const firstNewline = newContent.indexOf('\n');
      if (firstNewline > 0) {
        newContent = newContent.slice(firstNewline + 1);
      }
    }

    file.setContent(newContent);
  } else {
    folder.createFile(LOG_FILENAME, entry, MimeType.PLAIN_TEXT);
  }
}


// ─── Профиль пользователя ───────────────────────────────────────────────────

/**
 * Ищет USER.md на Google Drive (в любом месте) и возвращает его содержимое.
 * Если файл не найден — возвращает захардкоженный профиль.
 *
 * @returns {{content: string, source: string}}
 */
function readUserProfile_() {
  try {
    const files = DriveApp.getFilesByName(USER_PROFILE_FILENAME);

    if (files.hasNext()) {
      const file = files.next();
      const content = file.getBlob().getDataAsString();

      if (content && content.trim().length > 0) {
        return {
          content: '## 👤 Профиль\n\n' + content.trim() + '\n',
          source: `загружен из ${USER_PROFILE_FILENAME} (${file.getId()})`
        };
      }
    }
  } catch (error) {
    Logger.log(`Ошибка чтения ${USER_PROFILE_FILENAME}: ${error.message}`);
  }

  // Фолбэк: захардкоженный профиль
  return {
    content: getDefaultProfile(),
    source: 'использован профиль по умолчанию (USER.md не найден)'
  };
}


// ─── Заметки из Google Sheet ─────────────────────────────────────────────────

/**
 * Читает заметки из Google Sheet "DNTS Notes".
 * Ожидаемый формат таблицы:
 *   | Дата | Тег | Заметка | Статус |
 *
 * Читает все строки с тегом #dnts (или все, если тегов нет).
 *
 * @returns {Array<{date: string, tag: string, note: string, status: string}>}
 */
function readNotesFromSheet_() {
  const notes = [];

  try {
    // Ищем таблицу по имени
    const spreadsheets = DriveApp.getFilesByName(NOTES_SHEET_NAME);

    if (!spreadsheets.hasNext()) {
      Logger.log(`Таблица "${NOTES_SHEET_NAME}" не найдена`);
      return notes;
    }

    const spreadsheetFile = spreadsheets.next();
    const spreadsheet = SpreadsheetApp.openById(spreadsheetFile.getId());
    const sheet = spreadsheet.getActiveSheet();
    const data = sheet.getDataRange().getValues();

    // Пропускаем заголовок (первая строка)
    for (let i = 1; i < data.length; i++) {
      const row = data[i];

      // Минимально: нужна хотя бы заметка (третий столбец)
      if (!row[2] || String(row[2]).trim() === '') continue;

      const tag = String(row[1] || '').trim();
      const note = String(row[2]).trim();
      const status = String(row[3] || '').trim();
      const date = row[0] ? formatDate_(new Date(row[0])) : '';

      // Фильтруем по тегу #dnts (если тег указан)
      if (tag && !tag.toLowerCase().includes('#dnts') && !tag.toLowerCase().includes('dnts')) {
        continue;
      }

      notes.push({ date, tag, note, status });
    }
  } catch (error) {
    Logger.log(`Ошибка чтения заметок: ${error.message}`);
  }

  return notes;
}


// ─── Суммаризация через Gemini API ──────────────────────────────────────────

/**
 * Получает API-ключ Gemini из Script Properties.
 * @returns {string}
 * @throws {Error} если ключ не задан
 */
function getGeminiApiKey_() {
  const key = PropertiesService.getScriptProperties().getProperty('GEMINI_API_KEY');

  if (!key || key.trim() === '') {
    throw new Error(
      'GEMINI_API_KEY не задан в Script Properties. ' +
      'Откройте Project Settings → Script Properties → добавьте ключ.'
    );
  }

  return key.trim();
}

/**
 * Суммаризирует массив диалогов через Gemini API.
 * Каждый диалог суммаризируется отдельным запросом для надёжности.
 *
 * @param {Array<{name: string, content: string}>} dialogues
 * @returns {Array<{name: string, summary: string}>}
 */
function summarizeDialogues_(dialogues) {
  const apiKey = getGeminiApiKey_();
  const summaries = [];

  for (const dialogue of dialogues) {
    try {
      const summary = callGeminiApi_(apiKey, dialogue.content, dialogue.name);
      summaries.push({
        name: dialogue.name,
        summary: summary
      });

      // Задержка между запросами, чтобы не упереться в лимит
      Utilities.sleep(1000);
    } catch (error) {
      Logger.log(`Ошибка суммаризации "${dialogue.name}": ${error.message}`);
      summaries.push({
        name: dialogue.name,
        summary: `⚠️ Ошибка суммаризации: ${error.message}`
      });
    }
  }

  return summaries;
}

/**
 * Вызывает Gemini API для суммаризации одного диалога.
 *
 * @param {string} apiKey — ключ API
 * @param {string} content — текст диалога
 * @param {string} fileName — имя файла (для контекста)
 * @returns {string} — саммари на русском языке
 */
function callGeminiApi_(apiKey, content, fileName) {
  // Обрезаем слишком длинные диалоги (лимит ~30К символов для запроса)
  const maxContentLength = 30000;
  const truncatedContent = content.length > maxContentLength
    ? content.slice(0, maxContentLength) + '\n\n[...обрезано...]'
    : content;

  const prompt = [
    'Ты — ассистент, который суммаризирует диалоги с AI на русском языке.',
    'Сделай краткое, информативное саммари следующего диалога.',
    'Формат: 2-4 предложения, ключевые решения и результаты.',
    'Отвечай ТОЛЬКО на русском языке.',
    '',
    `Файл: ${fileName}`,
    '---',
    truncatedContent
  ].join('\n');

  const payload = {
    contents: [{
      parts: [{
        text: prompt
      }]
    }],
    generationConfig: {
      temperature: 0.3,
      maxOutputTokens: 512
    }
  };

  const options = {
    method: 'post',
    contentType: 'application/json',
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  };

  const url = `${GEMINI_API_URL}?key=${apiKey}`;
  const response = UrlFetchApp.fetch(url, options);
  const responseCode = response.getResponseCode();

  if (responseCode !== 200) {
    const errorBody = response.getContentText();
    throw new Error(`Gemini API вернул ${responseCode}: ${errorBody.slice(0, 200)}`);
  }

  const json = JSON.parse(response.getContentText());

  // Извлекаем текст из ответа
  if (json.candidates && json.candidates.length > 0 &&
      json.candidates[0].content &&
      json.candidates[0].content.parts &&
      json.candidates[0].content.parts.length > 0) {
    return json.candidates[0].content.parts[0].text.trim();
  }

  throw new Error('Пустой ответ от Gemini API');
}


// ─── Сборка brain_state.md ──────────────────────────────────────────────────

/**
 * Собирает финальный brain_state.md из всех компонентов.
 *
 * @param {string} profileSection — секция профиля
 * @param {Array<{name: string, summary: string}>} summaries — саммари диалогов
 * @param {Array<{date: string, tag: string, note: string, status: string}>} notes — заметки
 * @returns {string} — полный текст brain_state.md
 */
function composeBrainState_(profileSection, summaries, notes) {
  const now = new Date();
  const timestamp = formatDateTime_(now);
  const sections = [];

  // ── Заголовок ──────────────────────────────────────────────────────────
  sections.push([
    '# 🧠 DNTS Brain State',
    '',
    `> Сгенерировано автоматически: **${timestamp}**`,
    `> Модель суммаризации: \`${GEMINI_MODEL}\``,
    '',
    '---',
    ''
  ].join('\n'));

  // ── Профиль ────────────────────────────────────────────────────────────
  sections.push(profileSection);
  sections.push('---\n');

  // ── Активные задачи ────────────────────────────────────────────────────
  sections.push(composeActiveTasks_(notes));
  sections.push('---\n');

  // ── Последние диалоги ──────────────────────────────────────────────────
  sections.push(composeDialoguesSummaries_(summaries));
  sections.push('---\n');

  // ── Быстрые заметки ────────────────────────────────────────────────────
  sections.push(composeQuickNotes_(notes));
  sections.push('---\n');

  // ── Статус системы ─────────────────────────────────────────────────────
  sections.push(composeSystemStatus_(now, summaries.length, notes.length));

  return sections.join('\n');
}

/**
 * Формирует секцию активных задач.
 * Извлекает задачи из заметок со статусами "todo", "in progress", "wip".
 *
 * @param {Array} notes — заметки из таблицы
 * @returns {string}
 */
function composeActiveTasks_(notes) {
  const lines = ['## 📋 Активные задачи', ''];

  // Фильтруем заметки, которые выглядят как задачи
  const taskStatuses = ['todo', 'in progress', 'wip', 'в работе', 'сделать'];
  const tasks = notes.filter(n => {
    const status = (n.status || '').toLowerCase();
    return taskStatuses.some(s => status.includes(s));
  });

  if (tasks.length === 0) {
    lines.push('_Нет активных задач в таблице (или таблица не найдена)._');
    lines.push('');
    return lines.join('\n');
  }

  for (const task of tasks) {
    const statusEmoji = getStatusEmoji_(task.status);
    const dateStr = task.date ? ` (${task.date})` : '';
    lines.push(`- ${statusEmoji} ${task.note}${dateStr}`);
  }

  lines.push('');
  return lines.join('\n');
}

/**
 * Формирует секцию с саммари диалогов.
 *
 * @param {Array<{name: string, summary: string}>} summaries
 * @returns {string}
 */
function composeDialoguesSummaries_(summaries) {
  const lines = ['## 💬 Последние диалоги', ''];

  if (summaries.length === 0) {
    lines.push('_Диалоги не найдены в папке "dialogues cli"._');
    lines.push('');
    return lines.join('\n');
  }

  for (let i = 0; i < summaries.length; i++) {
    const s = summaries[i];
    const cleanName = s.name.replace(/\.md$/i, '').replace(/\.markdown$/i, '');
    lines.push(`### ${i + 1}. ${cleanName}`);
    lines.push('');
    lines.push(s.summary);
    lines.push('');
  }

  return lines.join('\n');
}

/**
 * Формирует секцию быстрых заметок.
 *
 * @param {Array} notes — заметки из таблицы
 * @returns {string}
 */
function composeQuickNotes_(notes) {
  const lines = ['## 📝 Быстрые заметки', ''];

  if (notes.length === 0) {
    lines.push('_Заметки не найдены. Создайте таблицу "DNTS Notes" с колонками:_');
    lines.push('_| Дата | Тег | Заметка | Статус |_');
    lines.push('');
    return lines.join('\n');
  }

  for (const note of notes) {
    const dateStr = note.date ? `**${note.date}**` : '';
    const statusStr = note.status ? ` \`${note.status}\`` : '';
    lines.push(`- ${dateStr} ${note.note}${statusStr}`);
  }

  lines.push('');
  return lines.join('\n');
}

/**
 * Формирует секцию статуса системы.
 *
 * @param {Date} now — текущее время
 * @param {number} dialogueCount — количество обработанных диалогов
 * @param {number} notesCount — количество прочитанных заметок
 * @returns {string}
 */
function composeSystemStatus_(now, dialogueCount, notesCount) {
  const lines = [
    '## ⚙️ Статус системы',
    '',
    `| Параметр | Значение |`,
    `|----------|----------|`,
    `| Последняя синхронизация | ${formatDateTime_(now)} |`,
    `| Модель | \`${GEMINI_MODEL}\` |`,
    `| Диалогов обработано | ${dialogueCount} |`,
    `| Заметок прочитано | ${notesCount} |`,
    `| Платформа | Google Apps Script |`,
    `| Триггер | каждые 6 часов |`,
    ''
  ];

  return lines.join('\n');
}


// ─── Утилиты ────────────────────────────────────────────────────────────────

/**
 * Форматирует дату в читаемый формат: "21 июня 2026, 17:03"
 * @param {Date} date
 * @returns {string}
 */
function formatDateTime_(date) {
  const months = [
    'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
    'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'
  ];

  const day = date.getDate();
  const month = months[date.getMonth()];
  const year = date.getFullYear();
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');

  return `${day} ${month} ${year}, ${hours}:${minutes}`;
}

/**
 * Форматирует дату в короткий формат: "21.06.2026"
 * @param {Date} date
 * @returns {string}
 */
function formatDate_(date) {
  const day = String(date.getDate()).padStart(2, '0');
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const year = date.getFullYear();
  return `${day}.${month}.${year}`;
}

/**
 * Возвращает эмодзи для статуса задачи.
 * @param {string} status
 * @returns {string}
 */
function getStatusEmoji_(status) {
  const s = (status || '').toLowerCase();

  if (s.includes('done') || s.includes('готово')) return '✅';
  if (s.includes('in progress') || s.includes('wip') || s.includes('в работе')) return '🔄';
  if (s.includes('todo') || s.includes('сделать')) return '⬜';
  if (s.includes('blocked') || s.includes('заблокировано')) return '🚫';
  if (s.includes('urgent') || s.includes('срочно')) return '🔴';

  return '📌';
}


// ─── Тестовые функции ───────────────────────────────────────────────────────

/**
 * Тестовый запуск — проверяет доступ к Drive и API.
 * Запустите эту функцию первой для проверки конфигурации.
 */
function testSetup() {
  Logger.log('=== DNTS Brain: Тестовый запуск ===\n');

  // 1. Проверяем папку ai
  const aiFolder = findFolder_(AI_FOLDER_NAME);
  Logger.log(aiFolder
    ? `✔ Папка "${AI_FOLDER_NAME}" найдена`
    : `✖ Папка "${AI_FOLDER_NAME}" НЕ найдена — создайте её на Google Drive`
  );

  // 2. Проверяем подпапку dialogues cli
  if (aiFolder) {
    const dialoguesFolder = findSubfolder_(aiFolder, DIALOGUES_FOLDER_NAME);
    Logger.log(dialoguesFolder
      ? `✔ Подпапка "${DIALOGUES_FOLDER_NAME}" найдена`
      : `✖ Подпапка "${DIALOGUES_FOLDER_NAME}" НЕ найдена — создайте её внутри "${AI_FOLDER_NAME}"`
    );
  }

  // 3. Проверяем API-ключ
  try {
    const key = getGeminiApiKey_();
    Logger.log(`✔ GEMINI_API_KEY задан (${key.slice(0, 4)}...${key.slice(-4)})`);
  } catch (e) {
    Logger.log(`✖ ${e.message}`);
  }

  // 4. Проверяем USER.md
  const profile = readUserProfile_();
  Logger.log(`ℹ Профиль: ${profile.source}`);

  // 5. Проверяем таблицу DNTS Notes
  const notesFiles = DriveApp.getFilesByName(NOTES_SHEET_NAME);
  Logger.log(notesFiles.hasNext()
    ? `✔ Таблица "${NOTES_SHEET_NAME}" найдена`
    : `⚠ Таблица "${NOTES_SHEET_NAME}" не найдена (необязательно)`
  );

  Logger.log('\n=== Тест завершён. Проверьте логи выше. ===');
}

/**
 * Тест вызова Gemini API с простым промптом.
 * Используйте для проверки, что API-ключ работает.
 */
function testGeminiApi() {
  try {
    const apiKey = getGeminiApiKey_();
    const result = callGeminiApi_(apiKey, 'Скажи "привет" на русском.', 'test.md');
    Logger.log(`✔ Gemini API работает. Ответ: ${result}`);
  } catch (error) {
    Logger.log(`✖ Ошибка Gemini API: ${error.message}`);
  }
}
