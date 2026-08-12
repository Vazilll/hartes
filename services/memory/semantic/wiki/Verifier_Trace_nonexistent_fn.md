---
title: "Verifier_Trace_nonexistent_fn"
agent: "verifier_worker"
trace_kind: "CODE_VERIFICATION"
created_at: "2026-07-22 23:50:41"
tags:
  - subagent
  - memory_trace
  - vazus_supergraph
  - obsidian_wiki
---

# Verifier_Trace_nonexistent_fn

> **Agent**: [[verifier_worker]]  
> **Trace Kind**: `CODE_VERIFICATION`  
> **Timestamp**: 2026-07-22 23:50:41  
> **Summary**: Verifier worker status: overall_success=False

---

## Memory Trace Content

Syntax: {'success': True, 'ast_parse': 'PASSED', 'functions_found': ['foo'], 'classes_found': [], 'error': None}
Contract: {'success': False, 'contract_test': 'FAILED', 'missing_functions': ['nonexistent_fn'], 'found_functions': ['foo']}
SMT Z3: {'success': True, 'status': 'UNSAT', 'contract_satisfied': True, 'smt_z3_depth': 10, 'functions_verified': ['nonexistent_fn'], 'preconditions': [], 'postconditions': [], 'model_checking': {'solver': 'Z3_SMT_Solver', 'satisfiable': False, 'counterexample': None, 'proof_status': 'VACUOUSLY_VERIFIED_NO_CONTRACTS'}}
Execution: {'success': True, 'execution': 'PASSED', 'timeout': 10}

---

## Linked SuperGraph Memory Nodes
- [[verifier_worker_Memory_Hub]]
- [[SuperGraph_OS_Architecture]]
