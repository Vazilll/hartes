# Technical Analysis: Web Dashboard Cognitive & Mastery Tab (Milestone 5 - R5)

## 1. Executive Summary
This document provides a comprehensive technical investigation and frontend UI architectural design for adding the **Cognitive & Mastery Tab** to `scripts/dashboard.html` in the **vazus SuperGraph OS**. 

The Cognitive & Mastery Tab equips users with active recall learning tools, spaced-repetition (SM-2) progress metrics, an interactive question trainer with automated rationale feedback, and an Obsidian Zettelkasten Atomic Note Reader capable of parsing bidirectional `[[Wikilinks]]` and interactive `- [ ]` task checkboxes.

---

## 2. Existing UI Structure & Integration Target

### 2.1 Current `scripts/dashboard.html` Architecture
- **Page Layout**: A dark-themed Single Page Application (SPA) using CSS variables (`--bg-dark: #0f1117`, `--panel-bg: #181c24`, `--accent: #6366f1`, `--success: #10b981`).
- **Header**: Contains title (`vazus SuperGraph OS`), badge (`Multimodal Knowledge Hub`), and live statistics bar (`#stats-bar`).
- **Main Container**: Uses standard CSS grid layout (`grid-template-columns: 420px 1fr`) dedicated to multimodal search and video player streaming.

### 2.2 Navigation Tab Integration Plan
To integrate the Cognitive & Mastery Tab cleanly without breaking the existing Multimodal Knowledge Hub:
1. **Top Sub-Header Tab Switcher**: Add a navigation bar directly under the header.
   ```html
   <div class="main-tab-bar">
     <button class="main-tab-btn active" id="tab-multimodal" onclick="switchMainTab('multimodal')">
       🌐 Multimodal Knowledge Hub
     </button>
     <button class="main-tab-btn" id="tab-cognitive" onclick="switchMainTab('cognitive')">
       🧠 Cognitive & Mastery Workspace
     </button>
   </div>
   ```
2. **View Containers**:
   - Wrap the existing search/video grid into `<div id="view-multimodal" class="tab-view active">`.
   - Create a new container `<div id="view-cognitive" class="tab-view" style="display: none;">`.

---

## 3. Cognitive & Mastery Tab Component Architecture

The `#view-cognitive` workspace is structured into a two-column grid (`420px 1fr`):
- **Left Column (420px)**:
  1. **Mastery Score Progress Bar & SM-2 Metrics Widget** (Top)
  2. **Zettelkasten Atomic Note Reader & Wikilink Explorer** (Bottom)
- **Right Column (Flex 1)**:
  3. **Interactive Question Trainer & Active Recall Workspace**

```
+-----------------------------------------------------------------------------------+
| HEADER: vazus SuperGraph OS | [🌐 Multimodal Knowledge]  [🧠 Cognitive & Mastery]  |
+-----------------------------------------------------------------------------------+
| LEFT COLUMN (420px)                     | RIGHT COLUMN (Flex 1)                   |
| +-------------------------------------+ | +-------------------------------------+ |
| | 1. Mastery & SM-2 Progress Bar      | | | 3. Interactive Question Trainer     | |
| |    - 75% Mastered (ProgressBar)     | | |    - Question / Prompt Box          | |
| |    - SM-2 EF: 2.50 | Ret: 91.2%      | | |    - User Answer Textarea           | |
| +-------------------------------------+ | |    - 0-100% Score Gauge & Grading   | |
| | 2. Zettelkasten Note Reader         | | |    - Rationale Feedback Card        | |
| |    - YAML Frontmatter Metadata      | | |    - Next Review Interval Countdown | |
| |    - Clickable [[Wikilinks]]        | | +-------------------------------------+ |
| |    - Interactive Checkboxes - [ ]   | |                                         |
| +-------------------------------------+ |                                         |
+-----------------------------------------------------------------------------------+
```

---

## 4. Component Technical Specifications & UI Wireframe Code

### 4.1 Component A: Mastery Score & SM-2 Metrics Widget
Calculates and renders real-time retention progress:
- **Visual Progress Bar**: Displays `% cards mastered` with an animated fill bar (`linear-gradient(90deg, #6366f1, #10b981)`).
- **Stat Cards**: Total Cards, Mastered Cards, Learning Cards, Due Today (with alert styling if > 0).
- **SuperMemo-2 (SM-2) Parameters**:
  - **Ease Factor (EF)**: Default `2.50` (min 1.30, max 3.20).
  - **Average Interval**: Days between reviews.
  - **Estimated Retention Rate**: Calculated as $R = e^{-\frac{t}{S \cdot EF}} \times 100\%$.

#### HTML Component Code
```html
<div class="cognitive-card mastery-overview-card">
  <div class="card-header-sm">
    <span class="card-label">MASTERY SCORE & SM-2 RETENTION</span>
    <span class="badge-tag" id="mastery-pct-badge">75.0%</span>
  </div>
  
  <div class="progress-bar-container">
    <div class="progress-bar-fill" id="mastery-progress-bar" style="width: 75%;"></div>
  </div>
  
  <div class="mastery-grid">
    <div class="m-stat"><span class="m-val" id="m-stat-mastered">90</span><span class="m-lbl">Mastered</span></div>
    <div class="m-stat"><span class="m-val" id="m-stat-learning">20</span><span class="m-lbl">Learning</span></div>
    <div class="m-stat alert"><span class="m-val" id="m-stat-due">10</span><span class="m-lbl">Due Today</span></div>
    <div class="m-stat"><span class="m-val" id="m-stat-total">120</span><span class="m-lbl">Total Cards</span></div>
  </div>

  <div class="sm2-metrics-row">
    <div class="sm2-metric">Avg Ease Factor: <strong id="sm2-ef">2.50</strong></div>
    <div class="sm2-metric">Avg Interval: <strong id="sm2-interval">14.2 days</strong></div>
    <div class="sm2-metric">Est. Retention: <strong id="sm2-retention" style="color:var(--success);">91.2%</strong></div>
  </div>
</div>
```

---

### 4.2 Component B: Interactive Question Trainer
Provides active recall testing with answer entry, automated scoring, rationale feedback, and SM-2 interval updates.

#### HTML Component Code
```html
<div class="cognitive-card trainer-card">
  <div class="trainer-header">
    <div class="trainer-title-group">
      <span class="trainer-badge" id="trainer-status-badge">DUE FOR REVIEW</span>
      <span class="trainer-domain" id="trainer-domain-tag">neuroscience_review</span>
    </div>
    <div class="trainer-meta" id="trainer-card-id">Card: Zettel_thesis_review_test_99</div>
  </div>

  <!-- Active Recall Question Prompt -->
  <div class="question-prompt-box">
    <h3 id="trainer-question-text">Применение ноотропов совместно с аэробной нагрузкой: каков основной механизм воздействия на гиппокамп?</h3>
  </div>

  <!-- User Active Recall Input Area -->
  <div class="answer-input-container">
    <textarea id="user-answer-input" class="user-answer-textarea" rows="4" placeholder="Type your active recall explanation or key thesis points here..."></textarea>
    <div class="answer-actions">
      <button class="btn btn-secondary" onclick="revealRationaleOnly()">Reveal Rationale</button>
      <button class="btn btn-primary" id="submit-answer-btn" onclick="submitRecallAnswer()">Submit & Grade Answer</button>
    </div>
  </div>

  <!-- Evaluation & Rationale Card (Shown post-submission) -->
  <div class="evaluation-panel" id="evaluation-panel" style="display: none;">
    <div class="score-gauge-row">
      <div class="gauge-circle" id="score-gauge-circle">
        <span class="gauge-val" id="score-gauge-val">88%</span>
      </div>
      <div class="score-meta">
        <div class="score-label" id="score-rating-label">STRONG RECALL</div>
        <div class="score-subtext">Semantic & Analytical Keyword Alignment</div>
      </div>
    </div>

    <!-- Manual / Auto Quality Grade Selector (SM-2 Grades 0-5) -->
    <div class="quality-grade-selector">
      <span class="grade-lbl">SM-2 Quality Grade:</span>
      <button class="btn-grade" data-grade="0" onclick="selectGrade(0)">0 (Blackout)</button>
      <button class="btn-grade" data-grade="1" onclick="selectGrade(1)">1 (Wrong)</button>
      <button class="btn-grade" data-grade="2" onclick="selectGrade(2)">2 (Hard)</button>
      <button class="btn-grade" data-grade="3" onclick="selectGrade(3)">3 (Good)</button>
      <button class="btn-grade active" data-grade="4" onclick="selectGrade(4)">4 (Great)</button>
      <button class="btn-grade" data-grade="5" onclick="selectGrade(5)">5 (Perfect)</button>
    </div>

    <!-- Rationale Feedback Card -->
    <div class="rationale-feedback-card">
      <div class="rationale-header">Target Rationale & Analytical Assertions:</div>
      <div class="rationale-body" id="rationale-text">
        > <strong>Thesis Assertion</strong>: Применение ноотропов совместно с аэробной нагрузкой увеличивает нейропластичность гиппокампа и синаптическую передачу за счет интегративного ускорения экспрессии BDNF.
      </div>
    </div>

    <!-- Next Review Interval Countdown -->
    <div class="interval-countdown-card">
      <div class="interval-text">
        ⏳ Next Review Scheduled In: <strong id="next-interval-days">15 days</strong>
        <span class="interval-sub">(New EF: <span id="new-ef-val">2.60</span>)</span>
      </div>
      <button class="btn btn-success" onclick="loadNextQuestion()">Next Question &rarr;</button>
    </div>
  </div>
</div>
```

---

### 4.3 Component C: Atomic Note Reader (Obsidian Zettelkasten Integration)
Renders Zettelkasten Markdown notes with live YAML frontmatter metadata, interactive task checkboxes `- [ ]`, and clickable `[[Wikilinks]]` navigation.

#### Markdown Parser Logic (JavaScript Regex)
1. **Wikilinks**: Transforms `[[Zettel_ID|Display Title]]` or `[[Zettel_ID]]` into:
   ```javascript
   function parseWikilinks(text) {
     return text.replace(/\[\[([a-zA-Z0-9_\-\.]+)(?:\|([^\]]+))?\]\]/g, (match, noteId, label) => {
       const display = label || noteId.replace('Zettel_', '');
       return `<a class="wikilink-badge" onclick="loadAtomicNote('${noteId}')" title="Navigate to ${noteId}">🔗 ${escapeHtml(display)}</a>`;
     });
   }
   ```
2. **Interactive Checkboxes**: Transforms `- [ ] Task text` and `- [x] Task text` into interactive HTML input elements:
   ```javascript
   function parseActionCheckboxes(text, noteId) {
     let taskIdx = 0;
     return text.replace(/^[ \t]*- \[([ xX])\] (.*)$/gm, (match, checkedState, taskText) => {
       const isChecked = checkedState.toLowerCase() === 'x';
       const currentIdx = taskIdx++;
       return `
         <div class="action-task-item">
           <input type="checkbox" id="task_${noteId}_${currentIdx}" ${isChecked ? 'checked' : ''} 
                  onchange="toggleTaskCheckbox('${noteId}', ${currentIdx}, this.checked)">
           <label for="task_${noteId}_${currentIdx}" class="${isChecked ? 'task-done' : ''}">${escapeHtml(taskText)}</label>
         </div>`;
     });
   }
   ```

#### HTML Component Code
```html
<div class="cognitive-card note-reader-card">
  <div class="note-reader-header">
    <div class="note-selector-row">
      <select id="note-dropdown-select" class="search-input" onchange="loadAtomicNote(this.value)">
        <option value="Zettel_thesis_review_test_99">Zettel_thesis_review_test_99 (Thesis)</option>
        <option value="Zettel_protocol_review_test_99">Zettel_protocol_review_test_99 (Protocol)</option>
      </select>
      <div class="note-nav-buttons">
        <button class="btn btn-sm" id="note-back-btn" onclick="popNoteHistory()" disabled>&larr; Back</button>
      </div>
    </div>
  </div>

  <!-- Rendered Note Area -->
  <div class="note-render-area" id="note-render-area">
    <!-- Rendered Markdown, YAML metadata badge, Wikilinks, and Action Checkboxes inserted here -->
  </div>
</div>
```

---

## 5. CSS Styling Specification (`scripts/dashboard.html` `<style>`)

```css
/* Tab Navigation Bar */
.main-tab-bar {
  display: flex;
  background-color: var(--panel-bg);
  border-bottom: 1px solid var(--border-color);
  padding: 0 24px;
  gap: 12px;
}
.main-tab-btn {
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--text-muted);
  padding: 12px 16px;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}
.main-tab-btn.active, .main-tab-btn:hover {
  color: #ffffff;
  border-bottom-color: var(--accent);
}

/* Cognitive Layout View */
.tab-view-cognitive {
  display: grid;
  grid-template-columns: 420px 1fr;
  gap: 20px;
  padding: 20px;
  flex: 1;
  overflow-y: auto;
}

.cognitive-card {
  background-color: var(--panel-bg);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* Mastery Progress Bar & SM-2 Cards */
.progress-bar-container {
  height: 10px;
  background-color: #0f1117;
  border-radius: 5px;
  overflow: hidden;
}
.progress-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #6366f1, #10b981);
  transition: width 0.4s ease-in-out;
}
.mastery-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  text-align: center;
}
.m-stat {
  background: #0f1117;
  padding: 8px;
  border-radius: 6px;
}
.m-stat.alert { border: 1px solid #ef4444; }
.m-val { display: block; font-size: 1.1rem; font-weight: 700; color: #ffffff; }
.m-lbl { font-size: 0.7rem; color: var(--text-muted); }

.sm2-metrics-row {
  display: flex;
  justify-content: space-between;
  font-size: 0.78rem;
  color: var(--text-muted);
  background: #0f1117;
  padding: 8px 12px;
  border-radius: 6px;
}

/* Interactive Question Trainer */
.user-answer-textarea {
  width: 100%;
  background: #0f1117;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  color: #ffffff;
  padding: 12px;
  font-size: 0.95rem;
  resize: vertical;
}
.user-answer-textarea:focus { border-color: var(--accent); outline: none; }
.answer-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 10px; }

.quality-grade-selector {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 12px 0;
}
.btn-grade {
  background: #0f1117;
  border: 1px solid var(--border-color);
  color: var(--text-muted);
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.75rem;
  cursor: pointer;
}
.btn-grade.active, .btn-grade:hover {
  background: var(--accent);
  color: #ffffff;
  border-color: var(--accent);
}

/* Wikilinks & Action Checkboxes */
.wikilink-badge {
  display: inline-block;
  background-color: #262c3a;
  color: #818cf8;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.82rem;
  font-weight: 600;
  cursor: pointer;
  text-decoration: none;
  border: 1px solid #374151;
  transition: all 0.15s;
}
.wikilink-badge:hover {
  background-color: var(--accent);
  color: #ffffff;
}
.action-task-item {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 6px 0;
}
.task-done {
  text-decoration: line-through;
  color: var(--text-muted);
}
```

---

## 6. Backend API Contracts (`dashboard.py` endpoints)

1. `GET /api/v1/cognitive/stats`
   - Returns overall card counts, SM-2 retention metrics, and mastery score %.
2. `GET /api/v1/cognitive/next-question`
   - Fetches due flashcard/thesis prompt for active recall.
3. `POST /api/v1/cognitive/evaluate-answer`
   - Accepts `{ "card_id": "...", "user_answer": "...", "quality_grade": 4 }`. Calculates SM-2 formula:
     $$EF' = EF + (0.1 - (5 - q) \times (0.08 + (5 - q) \times 0.02))$$
     $$I(1) = 1, \quad I(2) = 6, \quad I(n) = I(n-1) \times EF'$$
   - Returns `{ "score_pct": 88.0, "feedback_rationale": "...", "new_ease_factor": 2.60, "new_interval_days": 15 }`.
4. `GET /api/v1/wiki/note?id=...`
   - Returns note raw markdown and parsed metadata.
5. `POST /api/v1/wiki/checkbox`
   - Toggles task checkbox state in markdown file on disk.

---

## 7. Next Steps & Recommendations for Implementation (Implementer)
1. Add `.main-tab-bar` and `#view-cognitive` HTML markup to `scripts/dashboard.html`.
2. Add JavaScript handlers (`loadMasteryStats`, `submitRecallAnswer`, `loadAtomicNote`, `parseWikilinks`, `toggleTaskCheckbox`).
3. Add backend REST routes to `scripts/dashboard.py`.
