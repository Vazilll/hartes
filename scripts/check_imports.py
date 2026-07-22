#!/usr/bin/env python3
import sys
import traceback
from pathlib import Path

# Add scripts and rlm-mit directories to path
sys.path.append(r"C:\vazus\pyenv\scripts")
sys.path.append(r"C:\vazus\pyenv\rlm-mit")

log_file = Path(r"C:\vazus\pyenv\scripts\check_imports.log")
results = []

def test_import(module_name):
    try:
        print(f"Testing import of {module_name}...")
        # Clear module from sys.modules if it was imported
        if module_name in sys.modules:
            del sys.modules[module_name]
        
        # Import module dynamically
        import importlib
        importlib.import_module(module_name)
        results.append(f"{module_name}: SUCCESS")
    except Exception as e:
        results.append(f"{module_name}: FAILED\n{traceback.format_exc()}")

for mod in ["ldr_mcp", "rlm_mcp", "evolution_mcp", "hybrid_search_mcp"]:
    test_import(mod)

log_file.write_text("\n\n".join(results), encoding="utf-8")
print("Import verification completed.")
