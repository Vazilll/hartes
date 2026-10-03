// ============================================================================
// Vazus SuperGraph OS — Cloud Hub & Academic Dispatcher (Google Apps Script)
// 24/7 Zero-Laptop Control Plane for RTU MIREA Student Zhukov M.D. (IVBO-22-25)
// ============================================================================
//
// Capabilities:
//   1. Mirea 2FA Interceptor: Intercepts SDO/Moodle login codes from Gmail
//   2. Academic HUD: Manages interactive Google Sheet with 18 debts (Deadline: 15.10.2026)
//   3. Brain State Generator: Auto-compiles brain_state.md for Gemini Spark on Drive
//   4. Webhook Engine: doPost/doGet endpoints for Cloud Run & GitHub Actions bridge
//   5. Cron Triggers: 24/7 background execution without any laptop or VPS
//
// ============================================================================

// --- Configuration Constants ---
const CONFIG = {
  AI_FOLDER_NAME: 'ai',
  DIALOGUES_FOLDER_NAME: 'dialogues cli',
  HUD_SHEET_NAME: 'Vazus Academic HUD',
  OUTPUT_BRAIN_STATE: 'brain_state.md',
  AUTH_TOKEN_FILE: 'auth_token.json',
  USER_PROFILE_FILE: 'USER.md',
  STUDENT_NAME: 'Жуков Максим Дмитриевич',
  STUDENT_GROUP: 'ИВБО-22-25',
  STUDENT_ID: '25И0566',
  STAGE1_DEADLINE: '15.10.2026',
  GEMINI_MODEL: 'gemini-2.5-flash',
  MAX_DIALOGUES: 5
};

// 18 Academic Debts SSOT Data
const ACADEMIC_DEBTS = [
  { id: 1, name: 'Иностранный язык (1 сем)', type: 'Зачет (1/3, № 86146)', moodleId: '16017', priority: 'P1 🔥 КРИТИЧНО', deadline: '15.10.2026', status: 'В процессе', task: 'Лексический минимум / перевод топиков' },
  { id: 2, name: 'Линейная алгебра (1 сем)', type: 'Экзамен (1/2, № 66804)', moodleId: '16480', priority: 'P1 🔥 КРИТИЧНО', deadline: '15.10.2026', status: 'В процессе', task: 'Матрицы, определители, СЛАУ, метод Гаусса' },
  { id: 3, name: 'Математический анализ (1 сем)', type: 'Экзамен (1/3, № 81917)', moodleId: '16479', priority: 'P1 🔥 КРИТИЧНО', deadline: '15.10.2026', status: 'В процессе', task: 'Пределы, производные, типовой расчет №1' },
  { id: 4, name: 'Мат. логика и теория алгоритмов', type: 'Экзамен (1/1, № 86958)', moodleId: '16486', priority: 'P2 Высокий', deadline: '15.10.2026', status: 'В процессе', task: 'Булева логика, исчисление предикатов, Z3' },
  { id: 5, name: 'Русский язык и культура речи', type: 'Зачет (1/1, № 69956)', moodleId: '', priority: 'P2 Быстрый зачет', deadline: '15.10.2026', status: 'В процессе', task: 'Пройти онлайн-тест СДО за 1 вечер' },
  { id: 6, name: 'Основы конструирования', type: 'Зачет (1/1, № 86971)', moodleId: '', priority: 'P3 Средний', deadline: '15.10.2026', status: 'В процессе', task: 'Отчет по практическим работам / чертежи' },
  { id: 7, name: 'ООП (Курсовая работа)', type: 'Курсовая работа (1/1, № 86959)', moodleId: '', priority: 'P2 Высокий', deadline: '15.10.2026', status: 'В процессе', task: 'Пояснительная записка и код проекта' },
  { id: 8, name: 'Иностранный язык (2 сем)', type: 'Зачет (2/3, № 86146)', moodleId: '16017', priority: 'P2 Высокий', deadline: '15.10.2026', status: 'В процессе', task: 'Технический терминологический словарь' },
  { id: 9, name: 'Физика (Зачет 2 сем)', type: 'Зачет (2/2, № 78208)', moodleId: '', priority: 'P3 Средний', deadline: '15.10.2026', status: 'В процессе', task: 'Защита лабораторных отчетов (механика/оптика)' },
  { id: 10, name: 'Ознакомительная практика', type: 'Дифф. зачет (1/1, № 6082)', moodleId: '', priority: 'P2 Быстрый зачет', deadline: '15.10.2026', status: 'В процессе', task: 'Подписать дневник и сдать шаблон отчета' },
  { id: 11, name: 'Физическая культура и спорт', type: 'Зачет (1/3, № 72287)', moodleId: '', priority: 'P3 Быстрый зачет', deadline: '15.10.2026', status: 'В процессе', task: 'Сдать реферат преподавателю' },
  { id: 12, name: 'Основы росс. государственности', type: 'Зачет (1/1, № 82576)', moodleId: '', priority: 'P2 Быстрый зачет', deadline: '15.10.2026', status: 'В процессе', task: 'Закрыть онлайн-курс и тесты в СДО' },
  { id: 13, name: 'Линейная алгебра (2 сем)', type: 'Экзамен (2/2, № 66804)', moodleId: '16480', priority: 'P2 Высокий', deadline: '15.10.2026', status: 'В процессе', task: 'Квадратичные формы, линейные операторы' },
  { id: 14, name: 'ООП (Экзамен)', type: 'Экзамен (1/1, № 86959)', moodleId: '', priority: 'P2 Высокий', deadline: '15.10.2026', status: 'В процессе', task: 'Теория ООП, паттерны и алгоритмы' },
  { id: 15, name: 'Математический анализ (2 сем)', type: 'Экзамен (2/3, № 81917)', moodleId: '16479', priority: 'P2 Высокий', deadline: '15.10.2026', status: 'В процессе', task: 'Интегралы, ряды, дифференциальные уравнения' },
  { id: 16, name: 'Физика (Экзамен 2 сем)', type: 'Экзамен (2/2, № 78208)', moodleId: '', priority: 'P3 Средний', deadline: '15.10.2026', status: 'В процессе', task: 'Билеты по электромагнетизму и оптике' },
  { id: 17, name: 'История России', type: 'Экзамен (2/2, № 82054)', moodleId: '', priority: 'P3 Средний', deadline: '15.10.2026', status: 'В процессе', task: 'Хронологические таблицы, тестирование' },
  { id: 18, name: 'Информатика', type: 'Экзамен (2/2, № 85415)', moodleId: '', priority: 'P2 Высокий', deadline: '15.10.2026', status: 'В процессе', task: 'Python, архитектура ЭВМ, зачетные задачи' }
];


// ============================================================================
// 1. MIREA 2FA & AUTH CODE INTERCEPTOR
// ============================================================================

/**
 * Searches Gmail for recent confirmation codes from RTU MIREA / SDO Moodle.
 * Writes extracted code to auth_token.json on Google Drive.
 */
function checkMireaAuthCode() {
  const query = 'from:mirea.ru newer_than:15m';
  const threads = GmailApp.search(query, 0, 3);
  if (!threads || threads.length === 0) {
    return { status: 'not_found', message: 'No recent MIREA emails found in last 15 min.' };
  }

  for (let i = 0; i < threads.length; i++) {
    const messages = threads[i].getMessages();
    const latestMsg = messages[messages.length - 1];
    const body = latestMsg.getPlainBody();
    const subject = latestMsg.getSubject();
    const date = latestMsg.getDate();

    // Look for 6-digit verification code
    const codeMatch = body.match(/\b\d{6}\b/);
    // Look for confirmation URLs
    const urlMatch = body.match(/https?:\/\/[^\s<>"]+(?:confirm|verify|login|token|auth)[^\s<>"]*/i);

    if (codeMatch || urlMatch) {
      const code = codeMatch ? codeMatch[0] : null;
      const url = urlMatch ? urlMatch[0] : null;
      const payload = {
        code: code,
        verification_url: url,
        subject: subject,
        received_at: date.toISOString(),
        updated_at: new Date().toISOString()
      };

      saveAuthTokenToDrive(payload);
      Logger.log(`[AUTH] Intercepted MIREA 2FA code: ${code || 'link found'}`);
      return { status: 'success', data: payload };
    }
  }

  return { status: 'no_code', message: 'Email found, but no code/link matched.' };
}

/**
 * Saves auth token payload to Google Drive root or ai/ folder.
 */
function saveAuthTokenToDrive(payload) {
  const aiFolder = getOrCreateFolder(CONFIG.AI_FOLDER_NAME);
  const content = JSON.stringify(payload, null, 2);
  const existingFiles = aiFolder.getFilesByName(CONFIG.AUTH_TOKEN_FILE);

  if (existingFiles.hasNext()) {
    const file = existingFiles.next();
    file.setContent(content);
  } else {
    aiFolder.createFile(CONFIG.AUTH_TOKEN_FILE, content, MimeType.PLAIN_TEXT);
  }
}


// ============================================================================
// 2. ACADEMIC HUD (GOOGLE SHEETS MOBILE DASHBOARD)
// ============================================================================

/**
 * Initializes or updates the interactive "Vazus Academic HUD" Google Sheet.
 * This sheet is the user's mobile dashboard on their phone.
 */
function initOrUpdateAcademicHud() {
  let spreadsheet;
  const files = DriveApp.getFilesByName(CONFIG.HUD_SHEET_NAME);
  
  if (files.hasNext()) {
    spreadsheet = SpreadsheetApp.open(files.next());
  } else {
    spreadsheet = SpreadsheetApp.create(CONFIG.HUD_SHEET_NAME);
    Logger.log(`[HUD] Created new spreadsheet: ${spreadsheet.getUrl()}`);
  }

  let sheet = spreadsheet.getSheetByName('18 Задолженностей');
  if (!sheet) {
    sheet = spreadsheet.insertSheet('18 Задолженностей');
  }

  // Header styling
  const headers = ['№', 'Дисциплина', 'Приоритет', 'Тип', 'Дедлайн', 'Статус', 'Moodle Ссылка', 'Конкретная задача', 'Отметка о сдаче'];
  sheet.getRange(1, 1, 1, headers.length).setValues([headers])
    .setBackground('#1a73e8')
    .setFontColor('#ffffff')
    .setFontWeight('bold');

  // Populate debt rows
  const rows = ACADEMIC_DEBTS.map(d => [
    d.id,
    d.name,
    d.priority,
    d.type,
    d.deadline,
    d.status,
    d.moodleId ? `https://online-edu.mirea.ru/course/view.php?id=${d.moodleId}` : '-',
    d.task,
    false // Checkbox for user on phone
  ]);

  sheet.getRange(2, 1, rows.length, headers.length).setValues(rows);
  sheet.getRange(2, 9, rows.length, 1).insertCheckboxes();
  sheet.autoResizeColumns(1, headers.length);

  // Add summary cards on top / metadata sheet
  let metaSheet = spreadsheet.getSheetByName('Обзор спринта');
  if (!metaSheet) {
    metaSheet = spreadsheet.insertSheet('Обзор спринта');
  }
  metaSheet.getRange('A1:B6').setValues([
    ['Студент:', CONFIG.STUDENT_NAME],
    ['Группа / ID:', `${CONFIG.STUDENT_GROUP} | ${CONFIG.STUDENT_ID}`],
    ['Дедлайн 1 этапа:', CONFIG.STAGE1_DEADLINE],
    ['Всего долгов:', 18],
    ['Топ-приоритет:', 'Математика 1 сем + Английский 1 сем'],
    ['Последнее обновление:', new Date().toLocaleString('ru-RU')]
  ]);

  Logger.log(`[HUD] Academic HUD updated successfully. URL: ${spreadsheet.getUrl()}`);
  return spreadsheet.getUrl();
}


// ============================================================================
// 3. BRAIN STATE COMPILER (SSOT CONTEXT FOR GEMINI SPARK)
// ============================================================================

/**
 * Gathers user profile, debt statuses from HUD, and recent dialogues.
 * Compiles a clean, compact brain_state.md on Google Drive for Gemini Spark.
 */
function generateBrainState() {
  const startTime = new Date();
  const aiFolder = getOrCreateFolder(CONFIG.AI_FOLDER_NAME);

  // 1. Read profile
  let profile = getDefaultProfile();
  const profileFiles = DriveApp.getFilesByName(CONFIG.USER_PROFILE_FILE);
  if (profileFiles.hasNext()) {
    profile = profileFiles.next().getBlob().getDataAsString();
  }

  // 2. Read HUD status
  let debtsSummary = '';
  const hudFiles = DriveApp.getFilesByName(CONFIG.HUD_SHEET_NAME);
  if (hudFiles.hasNext()) {
    const ss = SpreadsheetApp.open(hudFiles.next());
    const sheet = ss.getSheetByName('18 Задолженностей');
    if (sheet) {
      const data = sheet.getDataRange().getValues();
      debtsSummary = '### Текущий статус по долгам (из Google Таблицы):\n';
      for (let i = 1; i < data.length; i++) {
        const checked = data[i][8] ? '✅ СДАНО' : '⏳ В процессе';
        debtsSummary += `- **${data[i][1]}** (${data[i][2]}): ${checked} | *${data[i][7]}*\n`;
      }
    }
  }

  // 3. Assemble Markdown document
  const brainState = [
    `# 🧠 Vazus SuperGraph OS — Live Brain State`,
    `> **Синхронизировано**: ${new Date().toLocaleString('ru-RU')} | **Дедлайн этапа**: ${CONFIG.STAGE1_DEADLINE}`,
    `> **Контекст**: Zero-Laptop Автономия (Gemini Spark + Apps Script + Cloud Run)`,
    ``,
    `## 👤 Профиль студента`,
    profile,
    ``,
    `## 🎓 Академический план ликвидации долгов`,
    debtsSummary || 'Таблица HUD еще не инициализирована.',
    ``,
    `## 🛡️ Сократический кодекс наставника (USER.md#L37)`,
    `- Никогда не выдавать готовые решения тестов и типовых расчетов.`,
    `- Вести диалог пошагово: формула -> интуиция -> контрольный вопрос студенту -> проверка ответа.`,
    `- Поддерживать фокус на 1-м семестре: Линейная алгебра (матрицы/СЛАУ) и Матанализ (пределы/производные).`,
    ``,
    `*Сгенерировано автоматически Google Apps Script 24/7 Engine.*`
  ].join('\n');

  // 4. Save to Drive
  saveFileToDrive(aiFolder, CONFIG.OUTPUT_BRAIN_STATE, brainState);
  Logger.log(`[BRAIN] Generated ${CONFIG.OUTPUT_BRAIN_STATE} in ${((new Date() - startTime)/1000).toFixed(1)}s`);
}


// ============================================================================
// 4. WEBHOOK & HTTP API ENDPOINTS (doPost / doGet)
// ============================================================================

/**
 * Handles incoming webhooks from Gemini Spark, GitHub Actions, or Phone Shortcuts.
 */
function doPost(e) {
  try {
    const raw = e.postData ? e.postData.contents : '{}';
    const body = JSON.parse(raw);
    const action = body.action || 'sync';

    let result = {};
    if (action === 'get_auth_code') {
      result = checkMireaAuthCode();
    } else if (action === 'update_hud') {
      const url = initOrUpdateAcademicHud();
      result = { status: 'success', hud_url: url };
    } else if (action === 'sync_brain') {
      generateBrainState();
      result = { status: 'success', message: 'Brain state regenerated' };
    } else {
      result = { status: 'received', action: action, timestamp: new Date().toISOString() };
    }

    return ContentService.createTextOutput(JSON.stringify(result))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({ error: err.message }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

/**
 * Handles GET status checks.
 */
function doGet(e) {
  const authRes = checkMireaAuthCode();
  const resp = {
    system: 'Vazus OS Google Apps Script Hub',
    status: 'ONLINE_24_7',
    student: `${CONFIG.STUDENT_NAME} (${CONFIG.STUDENT_GROUP})`,
    latest_2fa: authRes,
    timestamp: new Date().toISOString()
  };
  return ContentService.createTextOutput(JSON.stringify(resp, null, 2))
    .setMimeType(ContentService.MimeType.JSON);
}


// ============================================================================
// 5. AUTOMATION TRIGGERS SETUP
// ============================================================================

/**
 * Installs all recurring background triggers with one click.
 * Call this function ONCE in the Apps Script editor.
 */
function setupAutomationTriggers() {
  // Clear old triggers
  const existingTriggers = ScriptApp.getProjectTriggers();
  for (let i = 0; i < existingTriggers.length; i++) {
    ScriptApp.deleteTrigger(existingTriggers[i]);
  }

  // 1. Check MIREA 2FA emails every 1 minute
  ScriptApp.newTrigger('checkMireaAuthCode')
    .timeBased()
    .everyMinutes(1)
    .create();

  // 2. Refresh Brain State every 1 hour
  ScriptApp.newTrigger('generateBrainState')
    .timeBased()
    .everyHours(1)
    .create();

  // 3. Daily Academic Progress Sweep at 8:00 AM
  ScriptApp.newTrigger('generateBrainState')
    .timeBased()
    .atHour(8)
    .everyDays(1)
    .create();

  Logger.log('[TRIGGERS] All 3 autonomous background triggers installed successfully.');
}


// ============================================================================
// HELPER UTILITIES
// ============================================================================

function getOrCreateFolder(name) {
  const folders = DriveApp.getFoldersByName(name);
  if (folders.hasNext()) {
    return folders.next();
  }
  return DriveApp.createFolder(name);
}

function saveFileToDrive(folder, filename, content) {
  const files = folder.getFilesByName(filename);
  if (files.hasNext()) {
    files.next().setContent(content);
  } else {
    folder.createFile(filename, content, MimeType.PLAIN_TEXT);
  }
}

function getDefaultProfile() {
  return [
    `- **Студент:** Жуков Максим Дмитриевич`,
    `- **Институт:** РТУ МИРЭА, ИИТ, кафедра КИТПиПИ`,
    `- **Группа:** ИВБО-22-25 (09.03.01 ИВТ), шифр 25И0566`,
    `- **Академический статус:** 18 долгов, дедлайн 1-го этапа: 15.10.2026`,
    `- **Педагогический суверенитет:** строгий Сократический наставник.`
  ].join('\n');
}
