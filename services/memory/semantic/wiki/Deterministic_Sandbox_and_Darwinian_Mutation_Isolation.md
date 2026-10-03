---
id: Deterministic_Sandbox_and_Darwinian_Mutation_Isolation
title: "Deterministic Windows Sandbox & Darwinian Mutation Isolation Architecture"
date: "2026-09-04"
domain: evolution
tags:
  - darwinian-evolution
  - windows-sandbox
  - mutation-testing
  - isolation
  - v5.2
status: VERIFIED
sources:
  - "ORIGINAL_REQUEST.md"
  - "vazus_core/evolution/darwinian_evolver.py"
  - "services/sandbox_bridge/vazus_sandbox.wsb"
  - "tools/virtualization-mcp/src/virtualization_mcp/utils/windows_sandbox_helper.py"
---

# Deterministic Windows Sandbox & Darwinian Mutation Isolation Architecture

> **Architecture Hub**: [[SuperGraph_OS_v5_2_Architecture]]  
> **Security Gate**: [[SMT_Z3_Substrate_Guard_Security_Gate]]  
> **Evolutionary Search**: [[AlphaProof_CEL_Auto_Formalizer_and_FunSearch]]  
> **Status**: `VERIFIED`

---

## 🧬 Defect Autopsy: The Darwinian Mutation Flaw

In prior versions of `vazus_core/evolution/darwinian_evolver.py` (lines 200–224), the evolutionary loop executed candidate mutations through an invalid verification path:

```python
# DEFECTIVE HISTORICAL FLOW (Lines 214-219)
mutated_code = mutator(sample_code)
if ASTPruner.validate_signatures(mutated_code):
    # CRITICAL BUG: mutated_code is NEVER written to disk or isolated!
    # evaluate_variant_pytest executes pytest directly against the UNTOUCHED base repo!
    variant_fitness = evaluate_variant_pytest(test_suite)
```

### Consequences of the Flaw
1. **Zero-Mutation Measurement**: Pytest executed solely against the base workspace on disk.
2. **Artificial Fitness Scores**: The evolutionary engine reported illusory fitness gains that were actually measurements of the unmutated, baseline code.
3. **Silent Drift**: Destructive or degenerate mutations were accepted because their altered bytecode was never actually imported or executed.

---

## 🔧 Solution: tmp_path Overlay & PYTHONPATH Prepending

The v5.2 patch implements a strictly isolated temporary disk overlay for every evaluated mutant:

1. **Virtual Workspace Mirroring (`tmp_path`)**: The target module containing `mutated_code` is written into an isolated temporary directory preserving the Python package namespace (e.g. `C:\Users\Vaz\AppData\Local\Temp\mutant_xyz\vazus_core\target_module.py`).
2. **Dynamic `PYTHONPATH` Injection**: When launching the child `pytest` process via `subprocess.Popen`, the environment variable `PYTHONPATH` is explicitly prepended with `tmp_path`:
   $$\text{PYTHONPATH} = \text{tmp\_path} + \text{os.pathsep} + \text{BASE\_REPO}$$
3. **Empirical Proof of Mutant Execution**: Verified by integration tests demonstrating that a mutant containing an intentional `AssertionError` or altered return value produces immediate test failures in the runner, proving that the python runtime executes the mutant's bytecode and not the base repository file.

---

## 📦 Hardened Windows Sandbox Controller (`wsb_sandbox_controller.py`)

For untrusted code evaluation, complex builds, and APT-vulnerable dependencies, the system provisions an ephemeral hardware-isolated **Windows Sandbox** session via `wsb.exe`:

### Mandatory WSB XML Directives

```xml
<Configuration>
  <!-- Hardware-level virtualization isolation -->
  <ProtectedClient>Enable</ProtectedClient>
  
  <!-- Complete network disconnection preventing data exfiltration -->
  <Networking>Disable</Networking>
  
  <!-- Controlled folder mappings -->
  <MappedFolders>
    <!-- Target project sandbox (Read/Write) -->
    <MappedFolder>
      <HostFolder>C:\vazus\lab\sandbox_workspace</HostFolder>
      <SandboxFolder>C:\sandbox_run</SandboxFolder>
      <ReadOnly>false</ReadOnly>
    </MappedFolder>
    <!-- Pre-compiled Python virtualenv & pip cache (Strictly Read-Only) -->
    <MappedFolder>
      <HostFolder>C:\vazus\.venv\Lib\site-packages</HostFolder>
      <SandboxFolder>C:\pip_cache</SandboxFolder>
      <ReadOnly>true</ReadOnly>
    </MappedFolder>
  </MappedFolders>
  
  <LogonCommand>
    <Command>cmd.exe /c "set PYTHONPATH=C:\pip_cache;C:\sandbox_run && pytest C:\sandbox_run\tests"</Command>
  </LogonCommand>
</Configuration>
```

### Security Benefits
- **Zero APT Exfiltration**: Network disconnection `<Networking>Disable</Networking>` renders malware or suspicious dependencies incapable of communicating externally.
- **Cache Poisoning Prevention**: The host dependency library is mapped strictly as `<ReadOnly>true</ReadOnly>`, ensuring the guest VM cannot tamper with host binaries.

---

## 🔗 Interlinked Wiki Nodes
- [[SuperGraph_OS_v5_2_Architecture]]: Core architecture overview.
- [[SMT_Z3_Substrate_Guard_Security_Gate]]: Pre-tool gate verification.
- [[AlphaProof_CEL_Auto_Formalizer_and_FunSearch]]: Island population models.
