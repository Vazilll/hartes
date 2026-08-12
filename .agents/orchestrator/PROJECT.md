# Project: vazus SuperGraph OS Extension (ASR, KGB Analytics, Zettelkasten, SM-2 Tutor, Mastery Dashboard)

## Architecture
- **Target Directory**: `C:\vazus`
- **Core Packages & Modules**:
  - `vazus_core/multimodal_knowledge.py` (High-Precision ASR upgrade with Whisper large-v3-turbo/medium, OpenVINO/PyTorch CPU, Russian text normalization, garbage transcript filter) [DONE]
  - `vazus_core/kgb_analytical_extractor.py` (KGB/FSB ИАД + ACH analytical extractor decomposing transcript scenes/discussions into `ThesisNode`, `ProtocolNode`, `CAUSES`, `REQUIRES`, `CONTRADICTS` edges) [DONE]
  - `vazus_core/zettelkasten_exporter.py` (Automated Zettelkasten Obsidian Markdown exporter writing to `C:\vazus\services\memory\semantic\wiki\` with 3+ bidirectional [[Wikilinks]] and action checklists) [DONE]
  - `vazus_core/cognitive_tutor_engine.py` (Active Learning Engine & SuperMemo SM-2 Spaced Repetition tutor with 0-100% scoring, Socratic Active Recall, SM-2 scheduling intervals 1, 3, 7, 21 days) [DONE]
  - `scripts/personal_tutor.py` (CLI runner for active recall session, testing, interactive review, SM-2 updates) [DONE]
  - `scripts/dashboard.py` & `scripts/dashboard.html` (Web Dashboard update adding Cognitive & Mastery Tab: Mastery Score progress bar, interactive question trainer, atomic note reader) [DONE]
- **Database**: SQLite Graph DB at `C:\vazus\vazus.db` and `C:\vazus\memory\dnts.db` storing nodes (`ThesisNode`, `ProtocolNode`, `MediaScene`, etc.) and edges (`CAUSES`, `REQUIRES`, `CONTRADICTS`, etc.) with 768D Gemini embeddings.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | R1: High-Precision ASR Upgrade | Upgrade `vazus_core/multimodal_knowledge.py` with Whisper large-v3-turbo / medium, OpenVINO / PyTorch CPU, Russian speech normalization, filtering garbage/hallucinated transcripts | None | DONE |
| 2 | R2: KGB/FSB Analytical Knowledge Extractor | Create `vazus_core/kgb_analytical_extractor.py` implementing ИАД + ACH algorithms, decomposing scenes/messages into `ThesisNode`, `ProtocolNode`, creating `CAUSES`, `REQUIRES`, `CONTRADICTS` edges in `vazus.db` | M1 | DONE |
| 3 | R3: Automated Zettelkasten Exporter | Exporter in `vazus_core` writing atomic markdown notes to `C:\vazus\services\memory\semantic\wiki\` with 3+ bidirectional [[Wikilinks]] per note, tags, and action checklists | M2 | DONE |
| 4 | R4: Active Learning & SM-2 Engine | Create `vazus_core/cognitive_tutor_engine.py` and CLI `scripts/personal_tutor.py` implementing Socratic active recall questions, 0-100% scoring, SuperMemo SM-2 interval scheduling (1, 3, 7, 21 days) | M2, M3 | DONE |
| 5 | R5: Web Dashboard Cognitive & Mastery Tab | Update `scripts/dashboard.py` & `scripts/dashboard.html` adding Cognitive & Mastery tab with Mastery Score progress bar, interactive question trainer, and atomic note reader | M3, M4 | DONE |

## Interface Contracts
### `vazus_core.multimodal_knowledge` (DONE)
- `transcribe_media_high_precision(file_path: str, model_name: str = "large-v3-turbo") -> List[Dict]`
- Includes Russian speech normalization and garbage/hallucination transcript filtering.

### `vazus_core.kgb_analytical_extractor`
- `extract_kgb_analytics(scene_or_text_dict: Dict) -> Dict`
- Inserts `ThesisNode` and `ProtocolNode` into `vazus.db` with `CAUSES`, `REQUIRES`, and `CONTRADICTS` edges.

### Zettelkasten Exporter (`vazus_core/zettelkasten_exporter.py` or integrated)
- `export_zettelkasten_note(thesis_data: Dict, output_dir: str = r"C:\vazus\services\memory\semantic\wiki") -> str`
- Writes atomic markdown note with 3+ bidirectional [[Wikilinks]] and action checklists.

### `vazus_core.cognitive_tutor_engine` & `scripts/personal_tutor.py`
- `generate_active_recall_question(thesis_node_id: str) -> Dict`
- `evaluate_answer(question_id: str, user_answer: str) -> Dict` (returns score 0-100%, SM-2 update: next_review_days=1,3,7,21)
- `scripts/personal_tutor.py --test` runs self-test CLI verification.

### `dashboard.py` & `dashboard.html`
- Serves `/api/v1/cognitive/mastery`, `/api/v1/cognitive/trainer`, `/api/v1/cognitive/notes`
- HTML UI tab for Cognitive & Mastery view.

## Acceptance Criteria
1. Syntax checks pass on all updated/created files. (M1 DONE)
2. `vazus.db` nodes (`ThesisNode`, `ProtocolNode`) and edges (`CAUSES`, `REQUIRES`, `CONTRADICTS`) populated and verified.
3. Zettelkasten atomic notes in `C:\vazus\services\memory\semantic\wiki\` generated with 3+ bidirectional [[Wikilinks]] and action checklists.
4. `python scripts/personal_tutor.py --test` executes cleanly with Exit Code 0.
5. `scripts/dashboard.py` starts, serves REST API, and renders Cognitive & Mastery tab.
