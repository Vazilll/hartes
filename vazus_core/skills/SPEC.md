# Domain Specification: `skills` (Skills Domain Subsystem)

> **Subsystem**: `vazus_core/skills`  
> **Path**: `vazus_core/skills`  
> **Last Auto-Synchronized**: 2026-10-03 14:03:04  

## 1. Core Mission & Domain Scope (Responsibilities & Boundaries)
### 1.1 Primary Mission
The `skills` component operates as a self-contained modular domain within Vazus SuperGraph OS. It provides deterministic interfaces, handles domain logic, and enforces fail-closed error handling.

### 1.2 Strict Boundary Rules
- **ALLOWED**:
  - Deterministic execution of `skills` public APIs and AST-verified symbols.
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

class HermesToolCall:
    pass

class HermesParsedOutput:
    pass

class HermesToolRegistry:
    def register_tool(self, name: str, description: str, parameters: Dict[str, Any], handler: Callable): ...
    def get_tools_xml(self) -> str: ...
    def get_handler(self, name: str) -> Optional[Callable]: ...

class HermesXMLParser:
    def parse_output(cls, model_output: str) -> HermesParsedOutput: ...
    def format_tool_response(tool_name: str, result: Any) -> str: ...

class HermesAgentEngine:
    def build_system_prompt(self, base_instructions: str) -> str: ...
    def execute_step(self, ctx: SubagentContext, model_output: str) -> HermesParsedOutput: ...

class HermesSkillEngine:
    def list_all_skills(self) -> List[Dict[str, Any]]: ...
    def view_skill(self, name: str) -> Dict[str, Any]: ...
    def route_skills(self, user_prompt: str, top_k: int=2) -> List[Dict[str, Any]]: ...
    def get_progressive_disclosure_context(self, user_prompt: str) -> Optional[str]: ...
    def build_compact_index(self, max_skills: int=40) -> str: ...
    def create_skill(self, name: str, description: str, instructions: str, category: str='vazus') -> Dict[str, Any]: ...
    def patch_skill(self, name: str, old_string: str, new_string: str) -> Dict[str, Any]: ...

class AutomaticSkillSelector:
    def select_matching_skills(self, prompt: str, top_k: int=2) -> list: ...
    def load_skill_content(self, skill_name: str) -> str: ...

def sync_hermes_skills(): ...

```

### 2.2 Exported Classes
- **`HermesToolCall`** (`hermes_agent_engine.py`): Represents an extracted Hermes 3 tool call.
- **`HermesParsedOutput`** (`hermes_agent_engine.py`): Parsed output of a Hermes 3 model execution step.
- **`HermesToolRegistry`** (`hermes_agent_engine.py`): Converts Python functions or tool dicts into Hermes 3 compliant <tools> JSON schemas.
  - *Methods*: `register_tool, get_tools_xml, get_handler`
- **`HermesXMLParser`** (`hermes_agent_engine.py`): High-speed C/Rust regex parser for Nous Hermes 3 XML tags.
  - *Methods*: `parse_output, format_tool_response`
- **`HermesAgentEngine`** (`hermes_agent_engine.py`): Nous Hermes 3 Agent Execution Loop Manager.
  - *Methods*: `build_system_prompt, execute_step`
- **`HermesSkillEngine`** (`hermes_engine.py`): Production Skill Engine adhering to NousResearch Hermes standards.
  - *Methods*: `list_all_skills, view_skill, route_skills, get_progressive_disclosure_context, build_compact_index, ... (+2)`
- **`AutomaticSkillSelector`** (`hermes_skill_syncer.py`): Automatic Skill Selection & Context Injection Engine.
  - *Methods*: `select_matching_skills, load_skill_content`

### 2.3 Exported Functions
- **`sync_hermes_skills()`** (`hermes_skill_syncer.py`): No description

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
