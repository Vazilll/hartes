"""
Binary tools auto-provisioner script for Cremniy Automation (Milestone 2 - Requirement R2).

Automates provisioning of disassemblers/debuggers/assembler engines:
- Radare2 6.1.8
- Rizin v0.9.1
- GDB (w64devkit v2.8.0 / GDB 15.1)
- Capstone 5.0.9 (Python bindings & C shared library)
- Keystone 0.9.2 (Python bindings & C shared library)

Usage:
  python scripts/provision_binary_tools.py          # Run full auto-provisioning
  python scripts/provision_binary_tools.py --check  # Check status only (exit code 0 if all OK)
  python scripts/provision_binary_tools.py --force  # Force re-download/re-extract all
  python scripts/provision_binary_tools.py --quiet  # Suppress verbose output
"""

import os
import sys
import shutil
import argparse
import subprocess
import importlib

sys.path.insert(0, r"C:\vazus")
from resilient_downloader import download_file, BINARY_TOOLS

DEFAULT_BIN_DIR = r"C:\vazus\bin"

REQUIRED_EXECUTABLES = {
    "Radare2": ["r2.exe", "rabin2.exe", "rasm2.exe"],
    "Rizin": ["rizin.exe", "rz-bin.exe", "rz-asm.exe"],
    "GDB": ["gdb.exe"]
}

REQUIRED_PYTHON_PACKAGES = {
    "capstone": "capstone",
    "keystone-engine": "keystone"
}


def check_tool_status(bin_dir: str = DEFAULT_BIN_DIR) -> dict:
    """
    Checks status of all required binary executables and Python packages.
    Self-heals gdb.exe from w64devkit subfolder if missing in root bin_dir.
    Returns dict mapping tool name to boolean (True if present and valid, False otherwise).
    """
    status = {}
    bin_dir = os.path.normpath(os.path.abspath(bin_dir))

    # Self-heal gdb.exe if present in w64devkit subfolder
    w64_gdb = os.path.join(bin_dir, "w64devkit", "bin", "gdb.exe")
    target_gdb = os.path.join(bin_dir, "gdb.exe")
    if not os.path.exists(target_gdb) and os.path.exists(w64_gdb):
        try:
            w64_bin = os.path.dirname(w64_gdb)
            for f in os.listdir(w64_bin):
                src = os.path.join(w64_bin, f)
                dst = os.path.join(bin_dir, f)
                if os.path.isfile(src):
                    shutil.copy2(src, dst)
        except Exception:
            pass

    for tool_name, exes in REQUIRED_EXECUTABLES.items():
        all_present = True
        for exe in exes:
            exe_path = os.path.join(bin_dir, exe)
            if not os.path.exists(exe_path):
                all_present = False
                break
        status[tool_name] = all_present

    for pkg_name, module_name in REQUIRED_PYTHON_PACKAGES.items():
        try:
            importlib.import_module(module_name)
            status[pkg_name] = True
        except ImportError:
            status[pkg_name] = False

    return status


def provision_python_packages(quiet: bool = False) -> bool:
    """
    Ensures capstone and keystone-engine are installed in active Python environment.
    """
    packages = ["capstone>=5.0.0", "keystone-engine>=0.9.2"]
    missing = []

    for pkg in packages:
        mod_name = "capstone" if "capstone" in pkg else "keystone"
        try:
            importlib.import_module(mod_name)
        except ImportError:
            missing.append(pkg)

    if not missing:
        if not quiet:
            print("[Provisioner] All required Python packages (capstone, keystone-engine) are already installed.")
        return True

    if not quiet:
        print(f"[Provisioner] Installing missing Python packages: {missing}...")

    cmd = [sys.executable, "-m", "pip", "install"] + missing
    res = subprocess.run(cmd, capture_output=quiet, text=True)
    return res.returncode == 0


def provision_all_tools(bin_dir: str = DEFAULT_BIN_DIR, force: bool = False, quiet: bool = False) -> dict:
    """
    Main auto-provisioning function. Checks and downloads missing binary tools.
    """
    bin_dir = os.path.normpath(os.path.abspath(bin_dir))
    os.makedirs(bin_dir, exist_ok=True)

    if not quiet:
        print("====== CREMNIY M2 BINARY TOOLS PROVISIONER ======")
        print(f"Target Directory: {bin_dir}")

    # Provision Python packages first
    provision_python_packages(quiet=quiet)

    _status = check_tool_status(bin_dir)

    for tool_info in BINARY_TOOLS:
        name = tool_info.get("name", os.path.basename(tool_info.get("path", "tool")))
        url = tool_info.get("url")
        target_path = tool_info.get("path", "")
        if not quiet:
            print(f"[Provisioner] Checking {name}...")
        if not os.path.exists(target_path) or force:
            if not quiet:
                print(f"[Provisioner] Downloading {name} to {target_path}...")
            download_file(url, target_path)
        else:
            if not quiet:
                print(f"[Provisioner] {name} is already provisioned.")

    final_status = check_tool_status(bin_dir)

    if not quiet:
        print("\n====== PROVISIONING COMPLETE ======")
        for k, v in final_status.items():
            print(f"  - {k:18s}: {'OK' if v else 'FAILED'}")

    return final_status


def main():
    parser = argparse.ArgumentParser(description="Cremniy M2 Binary Tools Auto-Provisioner")
    parser.add_argument("--bin-dir", default=DEFAULT_BIN_DIR, help="Target binaries directory")
    parser.add_argument("--check", action="store_true", help="Check status of tools without downloading")
    parser.add_argument("--force", action="store_true", help="Force re-download and extraction")
    parser.add_argument("--quiet", action="store_true", help="Suppress verbose output")

    args = parser.parse_args()

    if args.check:
        status = check_tool_status(args.bin_dir)
        if not args.quiet:
            print("====== CREMNIY M2 TOOL STATUS ======")
            for k, v in status.items():
                print(f"  - {k:18s}: {'OK' if v else 'MISSING'}")
        all_ok = all(status.values())
        sys.exit(0 if all_ok else 1)

    final_status = provision_all_tools(args.bin_dir, force=args.force, quiet=args.quiet)
    all_ok = all(final_status.values())
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
