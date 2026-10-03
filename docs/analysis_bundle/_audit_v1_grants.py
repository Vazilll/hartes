#!/usr/bin/env python3
"""V-1 audit: full sweep of allow/deny grants in Antigravity/agy config.json.

Goal: find BROAD grants (wildcards, unrestricted command(), unsandboxed) as
opposed to point grants (command(Get-ChildItem ...)).
Read-only. Prints counts + every suspicious grant.
"""
import json
import re
import sys
from pathlib import Path

CFG = Path(r"C:/Users/Vaz/.gemini/config/config.json")


def walk(obj, path=""):
    """Yield (path, key, value) for every dict/list node."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield path, k, v
            yield from walk(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk(v, f"{path}[{i}]")


def main():
    if not CFG.exists():
        print("MISSING:", CFG)
        return 2
    raw = CFG.read_text(encoding="utf-8")
    print(f"config.json size={len(raw)}B")
    cfg = json.loads(raw)

    # 1. locate all allow/deny lists anywhere in the tree
    lists = []
    for path, key, val in walk(cfg):
        if key in ("allow", "deny", "ask", "allowedTools", "permissions") and isinstance(val, list):
            lists.append((f"{path}.{key}" if path else key, val))

    print("\n== GRANT LISTS FOUND ==")
    for p, v in lists:
        print(f"  {p}: {len(v)} entries")

    all_allow = []
    all_deny = []
    for p, v in lists:
        target = all_deny if p.endswith("deny") else all_allow
        for e in v:
            if isinstance(e, str):
                target.append((p, e))

    print(f"\nTOTAL allow entries={len(all_allow)}  deny entries={len(all_deny)}")

    # 2. classify allow entries
    # broad = wildcard-only argument, or bare tool grant with no argument
    broad, point, other = [], [], []
    for p, e in all_allow:
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\((.*)\)$", e.strip(), re.S)
        if m:
            tool, arg = m.group(1), m.group(2).strip()
            if arg in ("", "*", "**", ".*", "*:*"):
                broad.append((p, e, tool, arg))
            elif arg.startswith("*") or arg.endswith("*") and len(arg) <= 3:
                broad.append((p, e, tool, arg))
            else:
                point.append((p, e, tool, arg))
        else:
            # bare grant, no parentheses -> whole-tool grant = broad
            other.append((p, e))

    print(f"\n== CLASSIFICATION ==\nbroad(wildcard/empty-arg)={len(broad)}  point={len(point)}  bare/other={len(other)}")

    print("\n== BROAD GRANTS (P0 candidates) ==")
    if not broad:
        print("  NONE")
    for p, e, tool, arg in broad:
        print(f"  [{p}] {e}")

    print("\n== BARE / NON-PARENTHESISED GRANTS ==")
    if not other:
        print("  NONE")
    for p, e in sorted(set(other)):
        print(f"  [{p}] {e}")

    # 3. dangerous point grants: shell tools with rm/del/curl/powershell -c etc
    DANGER = re.compile(
        r"(rm\s+-rf|Remove-Item|del\s+/|format\s|reg\s+add|reg\s+delete|"
        r"Invoke-WebRequest|Invoke-Expression|iex\b|curl\s|wget\s|"
        r"powershell(\.exe)?\s+-(c|e|enc|Command|EncodedCommand)|cmd(\.exe)?\s+/c|"
        r"Set-ExecutionPolicy|schtasks|New-Service|sc\s+create|net\s+user|"
        r"git\s+push|gh\s+repo\s+delete|pip\s+install|npm\s+i(nstall)?\b|"
        r"chmod\s+777|Start-Process|bash\s+-c|sh\s+-c|python\s+-c|eval)",
        re.I,
    )
    dangerous = [(p, e) for p, e, t, a in point if DANGER.search(e)]
    print(f"\n== DANGEROUS POINT GRANTS ({len(dangerous)}) ==")
    for p, e in dangerous:
        print(f"  [{p}] {e}")

    # 4. tool histogram of allow entries
    hist = {}
    for p, e, t, a in point + [(x[0], x[1], x[2], x[3]) for x in broad]:
        hist[t] = hist.get(t, 0) + 1
    print("\n== ALLOW GRANTS BY TOOL ==")
    for t, c in sorted(hist.items(), key=lambda kv: -kv[1]):
        print(f"  {t}: {c}")

    # 5. autoApprove / sandbox related flags anywhere
    print("\n== APPROVAL / SANDBOX FLAGS ==")
    for path, key, val in walk(cfg):
        if isinstance(val, (bool, str, int)) and re.search(
            r"(autoApprove|autoRun|sandbox|unsandboxed|yolo|bypass|skipPermission|dangerous|trust)",
            key, re.I,
        ):
            print(f"  {path}.{key} = {val!r}")

    print("\n== DENY LIST ==")
    for p, e in all_deny:
        print(f"  [{p}] {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
