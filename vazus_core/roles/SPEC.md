# Domain Specification: `roles` (Subagent Roles & Archetype Definitions)

> **Subsystem**: `vazus_core/roles`  
> **Path**: `vazus_core/roles`  
> **Last Auto-Synchronized**: 2026-10-03 15:43:53  

## 1. Core Mission & Domain Scope (Responsibilities & Boundaries)
### 1.1 Primary Mission
The `roles` component defines declarative archetypes, capabilities, system prompts, and tool access matrices for specialized Vazus OS subagents (planner, coder, verifier, reviewer, finance, health, vision).

### 1.2 Strict Boundary Rules
- **ALLOWED**:
  - Declarative archetype definition and Hermes skill loading configuration.
  - Role capability mapping and token budget allocation.
  - Dynamic persona switching and task-specific prompt customization.
- **PROHIBITED**:
  - Assigning privileged execution rights to unverified subagents.
  - Exceeding subagent memory or token allocation thresholds.

## 2. Public Typed Interface Contracts (Public Interface Contracts)
### 2.1 Primary Classes & Signatures
```python
from typing import Dict, Any, List, Optional, Union, Tuple, Set
from pathlib import Path

def normalize_role_name(role: str) -> str: ...
def get_persona_prompt(role_name: str) -> str: ...
def get_subagent_definition_spec(role_name: str) -> Dict[str, Any]: ...
def get_native_invoke_spec(role_name: str, task_prompt: str, model: str='inherit', workspace: str='inherit') -> Dict[str, Any]: ...

```

### 2.3 Exported Functions
- **`normalize_role_name()`** (`system_personas.py`): Normalizes role aliases to canonical role keys.
- **`get_persona_prompt()`** (`system_personas.py`): Returns canonical system prompt for a role.
- **`get_subagent_definition_spec()`** (`system_personas.py`): Returns arguments for Antigravity native `define_subagent` tool:
- **`get_native_invoke_spec()`** (`system_personas.py`): Returns a single subagent entry for Antigravity native `invoke_subagent` tool:

### 2.4 Invariant Guarantees & Safety Policies (Invariants & Safety Guarantees)
- Invariant 1: Subagent archetypes operate strictly within their declared capability boundaries.
- Invariant 2: Role prompt templates preserve security jail and fail-closed instructions.

## 3. Progressive Skill Level (Level 1..5 Capability Maturity) & Upgrade Criteria
- **Level 1 (Static Prompts)**: Hardcoded role descriptions.  
  *Upgrade criteria*: Implement declarative role templates.
- **Level 2 (Declarative Templates)**: Config-driven subagent definitions with tool bindings.  
  *Upgrade criteria*: Add dynamic skill selection.
- **Level 3 (Dynamic Skill Integration)**: Context-aware Hermes skill and MCP tool disclosure.  
  *Upgrade criteria*: Implement multi-agent teamwork orchestration.
- **Level 4 (Autonomous Teamwork)**: Collaborative multi-role teamwork with specialized handoffs.  
  *Upgrade criteria*: Integrate continuous role capability evolution.
- **Level 5 (Self-Evolving Subagent Matrix)**: Continuous self-assessment and autonomous archetype specialization.

## 4. Known Bottlenecks & Failure Modes (Optimization Backlog)
- [ ] Prompt overhead during multi-role context switching.

## 5. Extension Points & Integration
- Integrates with `vazus_core` through standard Python imports and canonical facade APIs.
- Auto-indexed by `AutoIndexRunner` and monitored by `hooks.json` lifecycle hooks.
