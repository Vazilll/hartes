"""Audit helper: compare CURRENT .env secret values vs values in git history.

Prints only hash prefixes and match/no-match verdicts. Never prints secrets.
"""
import hashlib
import subprocess
import sys

REPO = "C:/vazus"
SECRET_KEYS = (
    "OPENCODE_GO_API_KEY", "JULES_API_KEY", "GEMINI_API_KEY",
    "GOOGLE_API_KEY", "AGENTROUTER_API_KEY", "DEEPSEEK_API_KEY",
    "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "TELEGRAM_BOT_TOKEN",
)


def parse_env(text):
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if v:
            out[k] = v
    return out


def h(v):
    return hashlib.sha256(v.encode("utf-8", "replace")).hexdigest()[:12]


def git_show(ref):
    r = subprocess.run(["git", "-C", REPO, "show", ref],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout if r.returncode == 0 else ""


current = parse_env(open(REPO + "/.env", encoding="utf-8", errors="replace").read())
print("CURRENT .env keys:", len(current))

history_refs = ["47ab20d:.env", "a1c47e0:.env"]
hist = {}
for ref in history_refs:
    txt = git_show(ref)
    if not txt:
        print(f"  {ref}: NOT READABLE")
        continue
    hist[ref] = parse_env(txt)
    print(f"  {ref}: {len(hist[ref])} keys")

print()
print("=== SECRET EXPOSURE / ROTATION MATRIX ===")
print(f"{'KEY':<26} {'in history':<12} {'current==hist':<14} VERDICT")
any_leak = False
for key in sorted(set(list(current) + [k for d in hist.values() for k in d])):
    if not any(s in key.upper() for s in ("KEY", "TOKEN", "SECRET", "PASSWORD")):
        continue
    in_hist = [ref for ref, d in hist.items() if key in d]
    cur = current.get(key)
    if not in_hist:
        verdict = "clean (never committed)" if cur else "-"
        print(f"{key:<26} {'no':<12} {'-':<14} {verdict}")
        continue
    same = any(cur and d.get(key) == cur for ref, d in hist.items() if key in d)
    if same:
        any_leak = True
        verdict = "*** LEAKED & NOT ROTATED ***"
    elif cur:
        verdict = "leaked but ROTATED (value differs)"
    else:
        verdict = "leaked, key removed from current .env"
    print(f"{key:<26} {'YES':<12} {str(same):<14} {verdict}")
    hp = [h(d[key]) for ref, d in hist.items() if key in d]
    print(f"{'':<26} hist sha256[:12]={hp} current={h(cur) if cur else None}")

print()
print("SUMMARY:", "UNROTATED SECRETS PRESENT IN GIT HISTORY" if any_leak
      else "no unrotated secrets found in the two inspected commits")
sys.exit(0)
