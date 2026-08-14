# E2E Test Infra: Vazus OS Core Engine SOTA Upgrade

## Test Philosophy
- Opaque-box, requirement-driven. No dependency on implementation design.
- Methodology: Category-Partition + BVA + Pairwise + Workload Testing.

## Feature Inventory
| # | Feature | Source (requirement) | Tier 1 | Tier 2 | Tier 3 | Tier 4 |
|---|---------|---------------------|:------:|:------:|:------:|:------:|
| 1 | R1: asyncio-Native Core Architecture | ORIGINAL_REQUEST §R1 | 5 | 5 | ✓ | ✓ |
| 2 | R2: LLM-Powered Reflexion Loop & Concordia Jury | ORIGINAL_REQUEST §R2 | 5 | 5 | ✓ | ✓ |
| 3 | R3: 768D Vector Embeddings & Cosine Retrieval | ORIGINAL_REQUEST §R3 | 5 | 5 | ✓ | ✓ |

## Test Architecture
- Test runner: `pytest C:\vazus\tests`
- Test cases location: `C:\vazus\tests\`
  - `test_e2e_tier1_feature_coverage.py`: Tier 1 Feature Coverage (>=5 test cases per feature R1, R2, R3)
  - `test_e2e_tier2_boundary_corner.py`: Tier 2 Boundary & Corner Cases (>=5 test cases per feature: timeouts, AST syntax errors, empty vectors, API fallbacks)
  - `test_e2e_tier3_cross_feature.py`: Tier 3 Cross-Feature Combinations (pairwise async + LLM reflexion + vector memory)
  - `test_e2e_tier4_real_world.py`: Tier 4 Real-World Application Scenarios (end-to-end multi-agent self-repair loop)

## Real-World Application Scenarios (Tier 4)
| # | Scenario | Features Exercised | Complexity |
|---|----------|--------------------|------------|
| 1 | Multi-Agent Self-Repair Loop | R1 (Async Engine), R2 (LLM Reflexion), R3 (Vector Memory) | High |

## Coverage Thresholds
- Tier 1: ≥5 per feature (Total ≥15)
- Tier 2: ≥5 per feature (Total ≥15)
- Tier 3: Pairwise combinations (Total ≥5)
- Tier 4: Real-world E2E self-repair scenario (Total ≥5)
- Total E2E Test Cases: ≥40
