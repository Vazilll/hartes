# E2E Test Infra: Autonomous Absolute AI Flywheel

## Test Philosophy
- Opaque-box, requirement-driven verification derived directly from `ORIGINAL_REQUEST.md`.
- Completely independent of internal implementation details.
- Methodology: Systematic 4-tier approach (Category-Partition, Boundary Value Analysis, Pairwise Combinatorial Testing, Real-World Workload Scenarios).
- Zero-mock policy for core logic verification (Chelpanov's anti-*Petitio Principii*).

---

## Feature Inventory & Test Matrix
| # | Feature | Source Requirement | Tier 1 (Feature) | Tier 2 (Boundary) | Tier 3 (Pairwise) | Tier 4 (Workload) |
|---|---------|-------------------|:----------------:|:-----------------:|:-----------------:|:-----------------:|
| F1 | Quality Evaluation Rubric | R4 §31-38 | 5 | 5 | ✓ | ✓ |
| F2 | SMT Z3 Equivalence Prover | R4 §33, 61 | 5 | 5 | ✓ | ✓ |
| F3 | AST Bloat & Parsimony Analyzer | R4 §35 | 5 | 5 | ✓ | ✓ |
| F4 | Academic Sovereignty Guard | R4 §36 (USER.md#L37) | 5 | 5 | ✓ | ✓ |
| F5 | Continuous Reflexion Generator | R2 §19-20, 52 | 5 | 5 | ✓ | ✓ |
| F6 | Dual-Tier Episodic Memory Store | R2 §21 | 5 | 5 | ✓ | ✓ |
| F7 | Pre-Flight Negative Constraint Filter | R2 §22, 53 | 5 | 5 | ✓ | ✓ |
| F8 | Anti-Thrashing Circuit Breaker | R3 §25-27, 56-57 | 5 | 5 | ✓ | ✓ |
| F9 | Human Escalation Diagnostic Briefing | R3 §28, 56 | 5 | 5 | ✓ | ✓ |
| F10 | Lightweight VPS Daemon | R5 §40-42, 47 | 5 | 5 | ✓ | ✓ |
| F11 | Dual Deployment Setup Targets | R5 & User Update | 5 | 5 | ✓ | ✓ |
| F12 | OpenColab Asynchronous Bridge | R5 §39 | 5 | 5 | ✓ | ✓ |
| F13 | Asymmetric 4-Tier Topology | R1 §12-16, 48 | 5 | 5 | ✓ | ✓ |
| F14 | Laptop Power Multiplier & Lease Manager | R1 §16, 49 | 5 | 5 | ✓ | ✓ |

---

## Test Architecture & Directories
- Test Runner: `pytest`
- Root directory: `C:\vazus\hartes\tests\e2e\`
- Test suites:
  - `tests/e2e/test_tier1_features.py`: Happy-path feature verification in isolation.
  - `tests/e2e/test_tier2_boundaries.py`: Boundary value analysis, resource exhaustion, negative inputs, invalid contracts.
  - `tests/e2e/test_tier3_combinations.py`: Pairwise interactions (e.g. Reflexion + Circuit Breaker, Quality Engine + SMT, VPS Daemon + Colab Bridge).
  - `tests/e2e/test_tier4_workloads.py`: Full realistic lifecycle workloads (simulated 24/7 autonomous loop, laptop online/offline lifecycle, 3-cycle deadlock escalation).

---

## Coverage Thresholds
- Identified Features: 14 ($N = 14$)
- **Tier 1 Minimum**: $5 \times 14 = 70$ checks / test cases.
- **Tier 2 Minimum**: $5 \times 14 = 70$ checks / test cases.
- **Tier 3 Minimum**: $\ge 14$ pairwise combination test cases.
- **Tier 4 Minimum**: $\ge \max(5, 14 \div 2) = 7$ realistic application workload scenarios.
- **Total Suite Minimum**: $\ge 161$ test assertions / checks.

---

## Pass / Fail Semantics
- Zero regressions allowed across all existing 25 tests in `C:\vazus\hartes\tests`.
- 100% pass rate across all Tier 1–4 tests with exit code 0.
- All SMT Z3 assertions must resolve `UNSAT` on valid code and `SAT` with counterexamples on buggy code.
- Hard circuit-breaker trips on >= 3 consecutive failed cycles.
- Memory usage of Tier 0 daemon simulation must not exceed 200 MB RSS.
