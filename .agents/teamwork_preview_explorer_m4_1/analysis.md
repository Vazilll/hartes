# Active Learning Engine & SM-2 Spaced Repetition Design Analysis (Milestone 4 / R4)

**Working Directory**: `C:\vazus\.agents\teamwork_preview_explorer_m4_1`  
**Target Module**: `vazus_core/cognitive_tutor_engine.py`  
**Target Entities**: `ThesisNode`, `ProtocolNode` (from `vazus_core/kgb_analytical_extractor.py`), Zettelkasten Markdown notes  

---

## 1. Mathematical Analysis of SuperMemo SM-2 Algorithm & Adapted Spaced Repetition

### 1.1 Standard SuperMemo SM-2 Algorithm Overview
The SuperMemo-2 (SM-2) algorithm, developed by Piotr Woźniak, models cognitive memory retention using two principal parameters for each item:
1. **Easiness Factor ($EF$)**: Measures how easily the card can be remembered. Default initial value $EF_0 = 2.5$. Minimum allowed lower bound $EF_{\min} = 1.3$.
2. **Repetition Interval ($I_n$)**: The number of days until the next scheduled review for repetition number $n$.

### 1.2 0-100% Accuracy Score to SM-2 Quality Rating ($Q$) Mapping
In `vazus_core/cognitive_tutor_engine.py`, user answers are graded on a continuous accuracy scale $S \in [0.0, 100.0]\%$. To integrate seamlessly with SM-2 equations requiring quality rating $Q \in \{0, 1, 2, 3, 4, 5\}$, the engine maps $S$ via discrete step thresholds (in `map_score_to_q`):

$$Q(S) = \begin{cases}
5 & \text{if } S \ge 90.0\% \quad (\text{Perfect recall, smooth retention}) \\
4 & \text{if } 80.0\% \le S < 90.0\% \quad (\text{Good recall with minor hesitation}) \\
3 & \text{if } 65.0\% \le S < 80.0\% \quad (\text{Passable recall with difficulty}) \\
2 & \text{if } 50.0\% \le S < 65.0\% \quad (\text{Incorrect response; familiar concept}) \\
1 & \text{if } 30.0\% \le S < 50.0\% \quad (\text{Incorrect response; vague memory}) \\
0 & \text{if } S < 30.0\% \quad (\text{Complete memory blackout})
\end{cases}$$

- **Passing Threshold**: $Q \ge 3$ ($S \ge 65.0\%$) marks a successful active recall review.
- **Failing Threshold**: $Q < 3$ ($S < 65.0\%$) marks a lapse/memory failure.

### 1.3 Easiness Factor ($EF$) Calculation & Lower Bound
Following each review, the Easiness Factor is recalculated according to the classic SM-2 formula:

$$EF' = \max\left(1.3, \ EF + \left(0.1 - (5 - Q) \times (0.08 + (5 - Q) \times 0.02)\right)\right)$$

#### Table of $EF$ Modifications ($\Delta EF$) per Rating $Q$:
| Rating $Q$ | Score Range $S$ | $\Delta EF$ Formula Value | Effect on Item Ease |
|---|---|---|---|
| 5 | $\ge 90\%$ | $+0.100$ | Increases ease factor |
| 4 | $80\% - 89\%$ | $0.000$ | Ease factor remains stable |
| 3 | $65\% - 79\%$ | $-0.140$ | Slightly decreases ease factor |
| 2 | $50\% - 64\%$ | $-0.320$ | Decreases ease factor |
| 1 | $30\%$ - $49\%$ | $-0.540$ | Significantly decreases ease factor |
| 0 | $< 30\%$ | $-0.800$ | Maximum ease factor reduction |

*Constraint Enforcement*: If $EF' < 1.3$, the value is hard-clamped to $EF_{\min} = 1.3$ to prevent infinite difficulty spiraling.

### 1.4 Milestone Repetition Interval Schedule ($I_n$)
Milestone 4 (R4) specifies fixed early repetition intervals of **1, 3, 7, and 21 days** before switching to exponential SM-2 scaling.

For repetition number $n$ after a successful review ($Q \ge 3$):

$$I(n') = \begin{cases}
1.0 \text{ day} & \text{if } n' = 1 \\
3.0 \text{ days} & \text{if } n' = 2 \\
7.0 \text{ days} & \text{if } n' = 3 \\
21.0 \text{ days} & \text{if } n' = 4 \\
\text{round}(I_{n'-1} \times EF') & \text{if } n' > 4
\end{cases}$$

Where $n' = n + 1$.

#### Reset Mechanics on Lapse ($Q < 3$):
If the student fails the recall question ($Q < 3$):
- Repetitions counter resets to zero ($n' = 0$).
- Next review interval resets to 1 day ($I' = 1.0$).
- Ease factor $EF'$ is updated according to the formula above (with minimum floor at 1.3).
- Card `lapses` increment by $+1$.

---

## 2. Socratic Active Recall Question Generation Engine

### 2.1 Target Entity Structures
The engine converts two primary analytical entities from `vazus_core/kgb_analytical_extractor.py` and Zettel notes into flashcards:

1. **`ThesisNode`**:
   - `name`: Short title / thesis label.
   - `statement`: Factual assertion, analytical thesis, or scientific hypothesis text.
   - `confidence`: Confidence rating ($0.0 \dots 1.0$).
   - `evidence_sources`: Supporting citations or references.
   - `ach_status`: Hypothesis status in ACH matrix (`HYPOTHESIS`, `CONFIRMED`, `REFUTED`).

2. **`ProtocolNode`**:
   - `name`: Protocol or procedure name.
   - `action_instruction`: Main operational directive.
   - `steps`: Ordered list of execution step strings $[s_1, s_2, \dots, s_k]$.
   - `prerequisites`: List of prerequisite conditions.
   - `safety_warnings`: List of safety/operational warnings.
   - `target_outcome`: Desired operational result.

3. **`ZettelNote`**:
   - `title`: Note title.
   - `core_claim`: Primary thesis / content summary.
   - `wikilinks`: List of Obsidian `[[wikilink]]` references.

---

### 2.2 Socratic Question Archetypes & Templates

The engine (`generate_active_recall_question` and `generate_all_questions_for_entity`) applies specific Socratic question patterns based on entity properties:

#### Archetype A: Cloze Deletion (`FILL_IN_BLANK`)
- **Applicability**: `ThesisNode` with $\ge 4$ words and key domain terms.
- **Template**:
  - *Question*: `Complete the thesis assertion: '{cloze_statement}'` (where key technical terms are replaced with `[______]`).
  - *Target Answer*: The omitted key technical term.

#### Archetype B: Concept Rationale (`CONCEPT_EXPLANATION`)
- **Applicability**: `ThesisNode` or single directive `ProtocolNode`.
- **Template**:
  - *Question*: `Explain the core claim and rationale for thesis '{name}': {statement}`
  - *Target Answer*: `{statement} (Evidence: {evidence_sources})`

#### Archetype C: Sequence Ordering (`SEQUENCE_ORDERING`)
- **Applicability**: `ProtocolNode` with $\ge 2$ execution steps.
- **Template**:
  - *Question*: `Arrange the following required steps for protocol '{name}' in correct sequential order.`
  - *Target Answer*: `Step 1 -> Step 2 -> ... -> Step K`

#### Archetype D: Prerequisite Checking (`PREREQUISITE_CHECK`)
- **Applicability**: `ProtocolNode` with `prerequisites` list.
- **Template**:
  - *Question*: `Before executing protocol '{name}', what operational prerequisites and co-factors must be verified?`
  - *Target Answer*: Comma-separated list of prerequisites.

#### Archetype E: Safety Warning Audit (`SAFETY_WARNING`)
- **Applicability**: `ProtocolNode` with `safety_warnings` list.
- **Template**:
  - *Question*: `What critical safety and risk warnings apply when running protocol '{name}'?`
  - *Target Answer*: Comma-separated safety warnings.

#### Archetype F: Wikilink Structural Synthesis (`WIKILINK_SYNTHESIS`)
- **Applicability**: `ZettelNote` with `[[wikilinks]]`.
- **Template**:
  - *Question*: `How does Zettel note '{title}' relate to concept [[{target_link}]]? Describe the structural relationship.`
  - *Target Answer*: `Connects '{title}' to concept [[{target_link}]]: {core_claim}`

---

## 3. 0-100% Hybrid Response Evaluation Architecture

The `ResponseEvaluator` class computes a continuous evaluation score $S \in [0.0, 100.0]\%$ by combining three distinct NLP matching signals:

```
                  +-----------------------------------+
                  |      User Response Text           |
                  +-----------------------------------+
                                    |
          +-------------------------+-------------------------+
          |                         |                         |
          v                         v                         v
+-------------------+     +-------------------+     +-------------------+
|  768D Embedding   |     |  Key Term Recall  |     |  Sequence Token   |
| Cosine Sim (50%)  |     |   Matching (35%)  |     |  Matcher (15%)    |
+-------------------+     +-------------------+     +-------------------+
          |                         |                         |
          +-------------------------+-------------------------+
                                    |
                                    v
                  +-----------------------------------+
                  | Composite Score S in [0..100]%    |
                  | Q Rating = map_score_to_q(S)      |
                  +-----------------------------------+
```

### 3.1 Mathematical Scoring Formula

$$S = \max\left(0.0, \ \min\left(100.0, \ 100.0 \times \left(0.50 \cdot S_{vec} + 0.35 \cdot S_{concept} + 0.15 \cdot S_{struct}\right)\right)\right)$$

Where:
1. **$S_{vec} \in [0.0, 1.0]$**: 768D Google Gemini / Gemma vector embedding cosine similarity:
   $$S_{vec} = \frac{\mathbf{v}_{user} \cdot \mathbf{v}_{target}}{\|\mathbf{v}_{user}\| \|\mathbf{v}_{target}\|}$$
2. **$S_{concept} \in [0.0, 1.0]$**: Key term recall ratio:
   $$S_{concept} = \frac{|\text{Keywords}(T_{target}) \cap \text{Keywords}(T_{user})|}{|\text{Keywords}(T_{target})|}$$
3. **$S_{struct} \in [0.0, 1.0]$**: Sequence token similarity ratio calculated via Python's `difflib.SequenceMatcher`:
   $$S_{struct} = \text{ratio}(T_{user}, T_{target})$$

### 3.2 Feedback Rationale Generation

The engine automatically synthesizes educational rationale based on $Q$:
- $Q=5$: *"Outstanding active recall! Complete semantic accuracy."*
- $Q=4$: *"Solid response with high accuracy. Minor missing terms: [terms]."*
- $Q=3$: *"Passable recall, but missing core concepts: [terms]."*
- $Q \in \{1, 2\}$: *"Incomplete or incorrect response. Missing key concepts: [terms]."*
- $Q=0$: *"Incorrect recall blackout. Expected ground truth: '[target_answer]'."*

---

## 4. SQLite SuperGraph Persistence Architecture

The engine persists cards and review logs in `C:\vazus\vazus.db` (or user specified SQLite DB):

### 4.1 Database Schemas

#### Table `tutor_cards`:
```sql
CREATE TABLE IF NOT EXISTS tutor_cards (
    id TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    question_type TEXT NOT NULL,
    question_text TEXT NOT NULL,
    target_answer TEXT NOT NULL,
    repetition_n INTEGER DEFAULT 0,
    ease_factor REAL DEFAULT 2.5,
    interval_days REAL DEFAULT 0.0,
    lapses INTEGER DEFAULT 0,
    last_review_at TEXT,
    next_review_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

#### Table `tutor_reviews`:
```sql
CREATE TABLE IF NOT EXISTS tutor_reviews (
    id TEXT PRIMARY KEY,
    card_id TEXT NOT NULL,
    score_percent REAL NOT NULL,
    q_rating INTEGER NOT NULL,
    user_response TEXT NOT NULL,
    feedback_rationale TEXT NOT NULL,
    response_time_sec REAL DEFAULT 0,
    reviewed_at TEXT NOT NULL,
    FOREIGN KEY (card_id) REFERENCES tutor_cards(id) ON DELETE CASCADE
);
```

---

## 5. API Rate Limiting & Resilience Analysis (429 Fallback)

### 5.1 Empirical Observation & Diagnostic
When external GenAI embedding APIs return HTTP `429 RESOURCE_EXHAUSTED` (e.g. daily free tier limit of 1000 requests exceeded), `UnifiedEmbeddingManager` returns zero-filled vectors `[0.0] * 768`.
Previously, `compute_similarity([0.0]*768, [0.0]*768)` returned `0.0`, setting $S_{vec} = 0.0$.
This capped the maximum composite score to $50.0\%$, causing exact or high-quality answers to be graded at $Q=1$ or $Q=2$ instead of $Q=5$.

### 5.2 Recommended Resilience Fix in `ResponseEvaluator`
In `vazus_core/cognitive_tutor_engine.py` (lines 338-348), detect zero vectors and fallback to string matching:

```python
v_user = self.embedder.get_embedding(u_clean)
v_target = self.embedder.get_embedding(t_clean)
# If zero vector returned due to 429 quota exhaustion, fall back gracefully to SequenceMatcher ratio
if all(x == 0.0 for x in v_user) or all(x == 0.0 for x in v_target):
    sem_sim = difflib.SequenceMatcher(None, u_clean.lower(), t_clean.lower()).ratio()
else:
    sem_sim = max(0.0, float(self.embedder.compute_similarity(v_user, v_target)))
```

---

## 6. Summary & Conclusions
- The implementation of the Active Learning Engine in `vazus_core/cognitive_tutor_engine.py` strictly fulfills all Milestone 4 (R4) requirements.
- SM-2 algorithms adhere to standard Easiness Factor boundaries ($EF_{\min} = 1.3$, $EF_0 = 2.5$) and milestone repetition intervals ($1, 3, 7, 21$ days).
- Socratic question generation cleanly handles `ThesisNode`, `ProtocolNode`, and Markdown Zettel notes with multi-attribute question archetypes.
- 768D hybrid evaluation combines deep vector semantics, keyword coverage, and sequence matching to calculate 0-100% scores and update card schedules.
