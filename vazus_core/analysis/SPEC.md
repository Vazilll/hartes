# Domain Specification: `analysis` (Analysis Domain Subsystem)

> **Subsystem**: `vazus_core/analysis`  
> **Path**: `vazus_core/analysis`  
> **Last Auto-Synchronized**: 2026-10-05 16:39:57  

## 1. Core Mission & Domain Scope (Responsibilities & Boundaries)
### 1.1 Primary Mission
The `analysis` component operates as a self-contained modular domain within Vazus SuperGraph OS. It provides deterministic interfaces, handles domain logic, and enforces fail-closed error handling.

### 1.2 Strict Boundary Rules
- **ALLOWED**:
  - Deterministic execution of `analysis` public APIs and AST-verified symbols.
  - Thread-safe SQLite WAL queries and state mutations with exponential backoff.
  - Fast-fail validation and zero-trust parameter verification.
- **PROHIBITED**:
  - Unbounded memory consumption or persistent handle leaks.
  - Blocking event loops or unhandled exceptions escaping domain boundary.
  - Modifying external state outside workspace jail boundaries.

## 2. Public Typed Interface Contracts (Public Interface Contracts)
### 2.1 Primary Classes & Signatures
```python
from typing import Dict, Any, List, Optional, Union, Tuple, Set
from pathlib import Path

class Clone:
    pass

class ASTNormalizer:
    def visit_Name(self, node: ast.Name) -> ast.Name: ...
    def visit_arg(self, node: ast.arg) -> ast.arg: ...
    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef: ...
    def visit_ClassDef(self, node: ast.ClassDef) -> ast.ClassDef: ...

class CloneDetector:
    def detect_type1_to_3_jscpd(self) -> list[Clone]: ...
    def detect_type1_to_3_pylint(self) -> list[Clone]: ...
    def detect_type2_ast(self) -> list[Clone]: ...
    def detect_type4_semantic(self, threshold: float=0.92) -> list[Clone]: ...
    def detect_all(self, path: Path | str | None=None, semantic: bool=True, threshold: float=0.92) -> list[Clone]: ...
    def report(self, clones: list[Clone]) -> str: ...

class Twin:
    pass

class PatternMiner:
    def analyze_python_code(cls, source_code: str) -> Dict[str, Any]: ...
    def analyze_go_code(cls, source_code: str) -> Dict[str, Any]: ...
    def analyze_file(cls, file_path: str | Path) -> Dict[str, Any]: ...

class Suggestion:
    def to_prompt(self) -> str: ...
    def to_db_tuple(self) -> tuple: ...

class ProactiveSuggestionEngine:
    def store(self, suggestions: list[Suggestion]) -> None: ...
    def get_pending(db_path: Path | str | None=None, limit: int=5, user_prompt: str='') -> list[str]: ...
    def scan_file(self, filepath: str | Path) -> list[Suggestion]: ...
    def scan_changed_files(self) -> list[Suggestion]: ...
    def scan_full_codebase(self, root: Path | str | None=None) -> list[Suggestion]: ...
    def generate_improvement_report(self, suggestions: list[Suggestion]) -> str: ...

class StructField:
    pass

class ReconstructedStruct:
    pass

class ReverseEngineerEngine:
    def reconstruct_c_struct(cls, struct_code: str) -> Optional[ReconstructedStruct]: ...
    def reconstruct_go_struct(cls, struct_code: str) -> Optional[ReconstructedStruct]: ...
    def map_cross_language_types(cls, go_type: str) -> str: ...

def find_twins(query: str, root: Path | str=ROOT, top_k: int=5, min_score: float=RELATED, cached_only: bool=False) -> List[Twin]: ...
def main(argv=None) -> int: ...
def ensure_kg_schema(cursor) -> None: ...

```

### 2.2 Exported Classes
- **`Clone`** (`clone_detector.py`): No description
- **`ASTNormalizer`** (`clone_detector.py`): Normalizes AST for Type-2 clone detection by replacing identifiers
  - *Methods*: `visit_Name, visit_arg, visit_FunctionDef, visit_ClassDef`
- **`CloneDetector`** (`clone_detector.py`): 4-level code clone detector for vazus_core.
  - *Methods*: `detect_type1_to_3_jscpd, detect_type1_to_3_pylint, detect_type2_ast, detect_type4_semantic, detect_all, ... (+1)`
- **`Twin`** (`code_twin_finder.py`): No description
- **`PatternMiner`** (`pattern_miner.py`): Analyzes polyglot source code to discover design patterns,
  - *Methods*: `analyze_python_code, analyze_go_code, analyze_file`
- **`Suggestion`** (`proactive_suggestion_engine.py`): No description
  - *Methods*: `to_prompt, to_db_tuple`
- **`ProactiveSuggestionEngine`** (`proactive_suggestion_engine.py`): Autonomous code quality observer. Runs on every changed file and
  - *Methods*: `store, get_pending, scan_file, scan_changed_files, scan_full_codebase, ... (+1)`
- **`StructField`** (`reverse_engineer.py`): No description
- **`ReconstructedStruct`** (`reverse_engineer.py`): No description
- **`ReverseEngineerEngine`** (`reverse_engineer.py`): Reverse engineering analysis engine for struct layout reconstruction
  - *Methods*: `reconstruct_c_struct, reconstruct_go_struct, map_cross_language_types`

### 2.3 Exported Functions
- **`find_twins()`** (`code_twin_finder.py`): Existing functions closest in meaning to `query`; near-twins carry a unified diff of the differences.
- **`main()`** (`code_twin_finder.py`): No description
- **`ensure_kg_schema()`** (`kg_schema.py`): Create kg_nodes and kg_edges tables if they don't exist.

### 2.4 Invariant Guarantees & Safety Policies (Invariants & Safety Guarantees)
- Invariant 1: All operations enforce strict Zero-Trust input validation.
- Invariant 2: Database mutations utilize WAL mode and rollback on exception.
- Invariant 3: Public APIs maintain typed interfaces with sub-50ms latency guarantees.

## 3. Progressive Skill Level (Level 1..5 Capability Maturity) & Upgrade Criteria
- **Level 1 (Basic Operations)**: Foundational symbol definitions and synchronous executions.  
  *Upgrade criteria*: Add structured error handling and unit test coverage.
- **Level 2 (Resilient Handling)**: Fail-closed error boundaries and bounded memory usage.  
  *Upgrade criteria*: Integrate typed contracts and WAL storage.
- **Level 3 (Integrated Subsystem)**: Full integration with lifecycle hooks and SuperGraph OS telemetry.  
  *Upgrade criteria*: Add formal SMT Z3 contract verification.
- **Level 4 (Autonomous Closed-Loop)**: Self-healing error correction and Reflexion memory integration.  
  *Upgrade criteria*: Support distributed or NPU-accelerated execution.
- **Level 5 (Self-Sustaining Governor)**: Closed-loop autonomous adaptation, zero manual intervention, and verified invariant stability.

## 4. Known Bottlenecks & Failure Modes (Optimization Backlog)
- [ ] Concurrency contention during high-frequency SQLite WAL writes under peak load.
- [ ] Serialization latency on deep AST traversal across large files.
- [ ] Memory footprint under heavy micro-batching operations.

## 5. Extension Points & Integration
- Integrates with `vazus_core` through standard Python imports and canonical facade APIs.
- Auto-indexed by `AutoIndexRunner` and monitored by `hooks.json` lifecycle hooks.
