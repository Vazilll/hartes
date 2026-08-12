# Handoff Report — KGB/FSB Analytical Knowledge Extractor Remediation

## 1. Observation
- **Root Cause File & Location**: `vazus_core/kgb_analytical_extractor.py` lines 541-585, 642-680, 756-815.
- **Observed Defect**:
  When mutually contradictory claims existed (such as "Утверждение 1: Приём омега-3 жирных кислот абсолютно безопасен в любых дозах." vs "Утверждение 2: Приём высоких доз омега-3 противоречит безопасному приёму и вызывает разжижение крови и опасные кровотечения."):
  1. `evaluate_ach_hypotheses` assigned tied inconsistency scores (0.0 or 0.85) to both nodes due to missing stem matches in `neg_words` (e.g., `противореч\w*`, `опасн\w*`).
  2. `evaluate_ach_hypotheses` marked tied hypotheses as `"ACCEPTED"`.
  3. In `extract()`, `status_map` updated `t.ach_status` for thesis nodes to `"ACCEPTED"`.
  4. The contradiction check `if t.ach_status == "HYPOTHESIS": t.ach_status = "REJECTED"` was bypassed because `t.ach_status` was already overwritten to `"ACCEPTED"`. Consequently, mutually contradictory claims connected by `CONTRADICTS` edges remained marked as `"ACCEPTED"`.
- **Command & Results**:
  - Reproduction before fix: `Thesis ACH Statuses: ['ACCEPTED', 'ACCEPTED', 'ACCEPTED']`.
  - Unittest output after fix: `Ran 10 tests in 34.003s - OK` (Exit Code 0).

## 2. Logic Chain
- **Step 1**: In `extract_graph_edges`, container nodes (e.g. `scene_container`) were erroneously included in relational edge evaluations, creating spurious `CONTRADICTS` edges to container nodes. Adding a check for container nodes (`getattr(n1, 'properties', {}).get('container') or n1.id == scene_id`) isolates relational edges strictly to analytical thesis and protocol nodes.
- **Step 2**: When `contradict_regex` matched `n2` (the refuting statement containing "противоречит..."), the edge direction was set arbitrarily as `n1 -> n2`. Orienting `c_src = n2.id` and `c_dst = n1.id` ensures the refuting claim is the edge source and the contradicted claim is the edge target.
- **Step 3**: `neg_words` in `evaluate_ach_hypotheses` was expanded to include `\b(не|без|отсутствие|против|опасн\w*|ошибочн\w*|заблужден\w*|неэффективн\w*|противореч\w*|опроверг\w*|вредн\w*|not|no|harmful|inconsistent|contradict\w*)\b`.
- **Step 4**: In `extract()`, contradiction status resolution was updated: when a `CONTRADICTS` edge exists, `dst_node` (the target contradicted claim) is transitioned to `"REJECTED"`, and `src_node` (the refuting claim) is transitioned to `"ACCEPTED"` if it was tied/disputed. This guarantees that mutually contradictory claims connected by `CONTRADICTS` edges are properly resolved and do not remain both `"ACCEPTED"`.

## 3. Caveats
- No caveats. The fix operates purely within standard Python standard library logic and existing data structures without external network dependency or facade hardcoding.

## 4. Conclusion
- The bug in `vazus_core/kgb_analytical_extractor.py` has been remediated completely. Contradicted thesis nodes connected by `CONTRADICTS` edges are correctly transitioned to `"REJECTED"` when inconsistency is detected.
- All 10 automated unit test cases pass cleanly with Exit Code 0.

## 5. Verification Method
Execute the unit test suite using the project virtualenv Python runner:
```powershell
C:\vazus\.venv\Scripts\python.exe -m unittest tests/test_kgb_analytical_extractor.py
```
Expected output:
```
Ran 10 tests in ~34s
OK
```
And verify reproduction case snippet:
```python
from vazus_core.kgb_analytical_extractor import extract_kgb_analytics
res = extract_kgb_analytics({
    'transcript': 'Утверждение 1: Приём омега-3 жирных кислот абсолютно безопасен в любых дозах. Утверждение 2: Приём высоких доз омега-3 противоречит безопасному приёму и вызывает разжижение крови и опасные кровотечения.'
})
print('Thesis ACH Statuses:', [t['ach_status'] for t in res['thesis_nodes']])
```
Expected output: `['REJECTED', 'ACCEPTED', 'HYPOTHESIS']` (the contradicted claim is marked `"REJECTED"`, not both `"ACCEPTED"`).
