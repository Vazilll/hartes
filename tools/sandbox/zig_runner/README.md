# vazus_runner: Zig WASM Sandboxed Micro-Runner

High-performance zero-dependency capability-isolated runner for **vazus SuperGraph OS v4.0**.

## Architecture & Targets
Built with Zig 0.16.0 for Meteor Lake / Windows AMD64 and WASI preview1 (`wasm32-wasi`).

1. **CLI Executable (`vazus_runner.exe`)**:
   - Native capability-sandboxed command-line runner.
   - Requires `--root <PATH>` to specify sandbox workspace boundary.
   - Evaluates arithmetic, variables, control flow, loops, and print expressions.
   - Fast cold-start execution (< 5ms).

2. **C-ABI Shared Library (`vazus_runner.dll`)**:
   - Ultra-fast in-process capability bridge for Python `LocalREPL`.
   - Cold invocation latency < 1ms, warm invocation latency < 100µs.
   - Exported symbols:
     - `int check_path_allowed(const char* path)`
     - `int execute_sandboxed_snippet(const char* code, const char* allowed_root, char* out_buf, size_t out_len)`
     - `void* vazus_sandbox_init(const char* granted_roots_json, const char* write_roots_json)`
     - `int vazus_sandbox_validate_path(void* ctx, const char* path, bool is_write)`
     - `int vazus_sandbox_eval(void* ctx, const char* code, char* out_buf, size_t out_buf_len)`
     - `void vazus_sandbox_free(void* ctx)`

3. **WASI Module (`vazus_runner.wasm`)**:
   - Target: `wasm32-wasi` preview1.
   - Zero ambient filesystem access without explicit preopens.

## Building

```bash
# Build native CLI and shared library
zig build -Doptimize=ReleaseFast

# Build WASI target
zig build wasi -Doptimize=ReleaseFast
```

## Security Model
- **Strict Fail-Closed Policy**: Only `C:\vazus` and `~/.gemini` (plus ephemeral REPL workspace when granted) are permitted.
- **Strictly Forbidden Targets**: `.git`, `AGENTS.md`, `windows/system32`, `/etc/`.
- **Traversal & Injection Protection**: Rejects null bytes (`\0`) and parent directory escapes (`..`).
