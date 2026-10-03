"""
vazus_core.agy_customizations_hud
===================================
Terminal HUD for Antigravity Customization System.

Scans all customization layers (Rules, Skills, MCP Servers, Hooks, Plugins,
Vazus Internal Harness) and renders a live ANSI status panel to stdout.

Usage (terminal):
    python -m vazus_core.agy_customizations_hud           # full HUD
    python -m vazus_core.agy_customizations_hud --watch   # refresh every 10s
    python -m vazus_core.agy_customizations_hud --skills  # skills only
    python -m vazus_core.agy_customizations_hud --mcp     # MCP only

Auto-registered as SubagentFramework on_start hook when module is imported.
"""

import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────
# ANSI helpers (ASCII-safe boxes, no Unicode chars)
# ─────────────────────────────────────────────────────────
RESET   = "\033[0m"
BOLD    = "\033[1m"
DIM     = "\033[2m"
GREEN   = "\033[32m"
CYAN    = "\033[36m"
YELLOW  = "\033[33m"
RED     = "\033[31m"
MAGENTA = "\033[35m"
BLUE    = "\033[34m"
WHITE   = "\033[97m"
GRAY    = "\033[90m"


def _vt100():
    if sys.platform == "win32":
        try:
            import ctypes
            k = ctypes.windll.kernel32
            h = k.GetStdHandle(-11)
            m = ctypes.c_ulong()
            k.GetConsoleMode(h, ctypes.byref(m))
            m.value |= 0x0004
            k.SetConsoleMode(h, m)
        except Exception as exc:
            logger.debug("Failed setting VT100 mode: %s", exc)


def _p(text: str):
    try:
        print(text, flush=True)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode("ascii"), flush=True)


def _box(title: str, body_lines: List[str], color: str = CYAN, width: int = 74) -> List[str]:
    """Renders a clean ASCII box."""
    out = []
    out.append(f"{color}+{'=' * (width - 2)}+{RESET}")
    out.append(f"{color}| {BOLD}{title:<{width-3}}{RESET}{color}|{RESET}")
    out.append(f"{color}|{'-' * (width - 2)}|{RESET}")
    for l in body_lines:
        # Strip ANSI for width calculation
        clean = re.sub(r'\x1B\[[0-?]*[ -/]*[@-~]', '', l)
        pad = max(0, width - 4 - len(clean))
        out.append(f"{color}|{RESET}  {l}{' ' * pad}{color}|{RESET}")
    out.append(f"{color}+{'=' * (width - 2)}+{RESET}")
    return out


# ─────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────

@dataclass
class SkillInfo:
    name: str
    description: str
    path: str
    source: str      # "global" | "workspace" | "plugin"
    score: float = 0.5


@dataclass
class RuleInfo:
    path: str
    source: str
    trigger: str
    size_bytes: int = 0


@dataclass
class McpServerInfo:
    name: str
    command: str
    args: List[str]
    status: str = "configured"


@dataclass
class PluginInfo:
    name: str
    path: str
    skills_count: int = 0
    has_hooks: bool = False


@dataclass
class CustomizationSnapshot:
    rules: List[RuleInfo] = field(default_factory=list)
    skills: List[SkillInfo] = field(default_factory=list)
    mcp_servers: List[McpServerInfo] = field(default_factory=list)
    plugins: List[PluginInfo] = field(default_factory=list)
    hooks_path: Optional[str] = None
    scanned_at: float = field(default_factory=time.time)


# ─────────────────────────────────────────────────────────
# Known paths
# ─────────────────────────────────────────────────────────

GLOBAL_CONFIG  = Path(r"C:\Users\Vaz\.gemini\config")
WORKSPACE_ROOT = Path(r"C:\vazus")
AGENTS_DIR     = WORKSPACE_ROOT / ".agents"
SKILLS_DIR     = GLOBAL_CONFIG / "skills"
PLUGINS_DIR    = GLOBAL_CONFIG / "plugins"
MCP_CONFIG     = GLOBAL_CONFIG / "mcp_config.json"


# ─────────────────────────────────────────────────────────
# Scanner
# ─────────────────────────────────────────────────────────

class CustomizationScanner:

    def scan(self) -> CustomizationSnapshot:
        snap = CustomizationSnapshot()
        snap.rules       = self._scan_rules()
        snap.skills      = self._scan_skills()
        snap.mcp_servers = self._scan_mcp()
        snap.plugins     = self._scan_plugins()
        snap.hooks_path  = self._find_hooks()
        return snap

    # ── Rules ─────────────────────────────────────────────
    def _scan_rules(self) -> List[RuleInfo]:
        """Only scans known rule files — not agent handoff docs in .agents/ subdirs."""
        rules = []
        known = [
            GLOBAL_CONFIG / "AGENTS.md",
            WORKSPACE_ROOT / "AGENTS.md",
            WORKSPACE_ROOT / "GEMINI.md",
        ]
        # Add any .md files explicitly in .agents/rules/ subfolder
        rules_dir = AGENTS_DIR / "rules"
        if rules_dir.exists():
            known.extend(sorted(rules_dir.glob("*.md")))

        seen = set()
        for p in known:
            if p.exists() and str(p) not in seen:
                seen.add(str(p))
                rules.append(RuleInfo(
                    path=str(p),
                    source="global" if str(GLOBAL_CONFIG) in str(p) else "workspace",
                    trigger="always_on",
                    size_bytes=p.stat().st_size,
                ))
        return rules

    # ── Skills ────────────────────────────────────────────
    def _scan_skills(self) -> List[SkillInfo]:
        skills = []
        seen = set()

        # Load EMA scores from AutoImprover
        scores: Dict[str, float] = {}
        try:
            from vazus_core.memory.auto_improver import SkillUsageTracker
            for s in SkillUsageTracker().get_top_skills(500):
                scores[s["name"]] = s["score"]
        except Exception as exc:
            logger.debug("Failed loading AutoImprover skill scores: %s", exc)

        def _walk(base: Path, source: str):
            if not base.exists():
                return
            for root, dirs, files in os.walk(base):
                if "SKILL.md" in files:
                    skill_md = Path(root) / "SKILL.md"
                    name = os.path.basename(root)
                    desc = ""
                    try:
                        content = skill_md.read_text(encoding="utf-8", errors="ignore")
                        m = re.search(r"^name:\s*(.+)$", content, re.MULTILINE)
                        d = re.search(r"^description:\s*[\"']?(.+?)[\"']?$", content, re.MULTILINE)
                        if m:
                            name = m.group(1).strip()
                        if d:
                            desc = d.group(1).strip()
                    except Exception as exc:
                        logger.debug("Failed parsing SKILL.md for %s: %s", skill_md, exc)
                    if name not in seen:
                        seen.add(name)
                        skills.append(SkillInfo(
                            name=name,
                            description=desc[:70],
                            path=str(skill_md),
                            source=source,
                            score=scores.get(name, 0.5),
                        ))

        _walk(SKILLS_DIR, "global")
        _walk(PLUGINS_DIR, "plugin")
        _walk(WORKSPACE_ROOT / ".agents" / "skills", "workspace")

        skills.sort(key=lambda s: s.score, reverse=True)
        return skills

    # ── MCP ───────────────────────────────────────────────
    def _scan_mcp(self) -> List[McpServerInfo]:
        servers = []
        if not MCP_CONFIG.exists():
            return servers
        try:
            data = json.loads(MCP_CONFIG.read_text(encoding="utf-8"))
            for name, cfg in data.get("mcpServers", {}).items():
                cmd = cfg.get("command", "")
                args = cfg.get("args", [])
                status = self._check_status(name, cmd, args)
                servers.append(McpServerInfo(name=name, command=cmd, args=args, status=status))
        except Exception as exc:
            logger.debug("Failed loading MCP config %s: %s", MCP_CONFIG, exc)
        return servers

    def _check_status(self, name: str, cmd: str, args: List[str]) -> str:
        if "vazus_organic_mcp" in " ".join(args):
            return "ready" if Path(r"C:\vazus\tools\scripts\vazus_organic_mcp.py").exists() else "missing"
        if "playwright" in " ".join(args):
            return "lazy"
        return "configured"

    # ── Plugins ───────────────────────────────────────────
    def _scan_plugins(self) -> List[PluginInfo]:
        plugins = []
        if not PLUGINS_DIR.exists():
            return plugins
        for d in PLUGINS_DIR.iterdir():
            if not d.is_dir():
                continue
            manifest = d / "plugin.json"
            if not manifest.exists():
                continue
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
                plugins.append(PluginInfo(
                    name=data.get("name", d.name),
                    path=str(d),
                    skills_count=sum(1 for _ in d.rglob("SKILL.md")),
                    has_hooks=(d / "hooks.json").exists(),
                ))
            except Exception as exc:
                logger.debug("Failed parsing plugin manifest %s: %s", manifest, exc)
        return plugins

    # ── Hooks ─────────────────────────────────────────────
    def _find_hooks(self) -> Optional[str]:
        for p in [
            GLOBAL_CONFIG / "hooks.json",
            WORKSPACE_ROOT / ".agents" / "hooks.json",
            WORKSPACE_ROOT / "hooks.json",
        ]:
            if p.exists():
                return str(p)
        return None


# ─────────────────────────────────────────────────────────
# Renderer
# ─────────────────────────────────────────────────────────

class CustomizationsHUD:
    """Renders a live ANSI Customizations HUD to terminal stdout."""

    def __init__(self):
        self.scanner = CustomizationScanner()
        _vt100()

    def render(self, snap: Optional[CustomizationSnapshot] = None):
        if snap is None:
            snap = self.scanner.scan()
        self._render_header(snap)
        self._render_rules(snap.rules)
        self._render_skills(snap.skills)
        self._render_mcp(snap.mcp_servers)
        self._render_plugins(snap.plugins)
        self._render_hooks(snap.hooks_path)
        self._render_internal_harness()
        _p(f"{GRAY}  Refresh: python -m vazus_core.agy_customizations_hud{RESET}")
        _p(f"{GRAY}  Watch:   python -m vazus_core.agy_customizations_hud --watch{RESET}")
        _p("")

    def render_skills_only(self):
        snap = self.scanner.scan()
        self._render_skills(snap.skills)

    def render_mcp_only(self):
        snap = self.scanner.scan()
        self._render_mcp(snap.mcp_servers)

    def watch(self, interval: int = 10):
        try:
            while True:
                _p("\033[2J\033[H")  # clear screen
                self.render()
                _p(f"{GRAY}  [watch] refreshing every {interval}s — Ctrl+C to stop{RESET}")
                time.sleep(interval)
        except KeyboardInterrupt:
            _p(f"\n{YELLOW}[HUD] Watch stopped.{RESET}")

    # ── Section renderers ──────────────────────────────────

    def _render_header(self, snap: CustomizationSnapshot):
        ts = time.strftime("%H:%M:%S", time.localtime(snap.scanned_at))
        lines = [
            f"Rules: {GREEN}{len(snap.rules)}{RESET}  "
            f"Skills: {CYAN}{len(snap.skills)}{RESET}  "
            f"MCP: {YELLOW}{len(snap.mcp_servers)}{RESET}  "
            f"Plugins: {MAGENTA}{len(snap.plugins)}{RESET}",
            f"Workspace: {BOLD}C:\\vazus{RESET}    Global: {BOLD}~/.gemini/config{RESET}",
        ]
        for l in _box(f"AGY CUSTOMIZATIONS HUD  [{ts}]", lines, color=CYAN):
            _p(l)

    def _render_rules(self, rules: List[RuleInfo]):
        if not rules:
            return
        lines = []
        for r in rules:
            name = Path(r.path).name
            src  = f"{CYAN}global{RESET}" if r.source == "global" else f"{YELLOW}workspace{RESET}"
            tag  = f"{GREEN}[ALWAYS_ON]{RESET}" if r.trigger == "always_on" else f"{GRAY}[lazy]{RESET}"
            kb   = max(1, r.size_bytes // 1024)
            lines.append(f"{tag} {src} {BOLD}{name}{RESET}  ({kb}kb)")
        for l in _box("RULES  (GEMINI.md / AGENTS.md / .agents/rules/)", lines, color=GREEN):
            _p(l)

    def _render_skills(self, skills: List[SkillInfo]):
        if not skills:
            return
        top = skills[:15]
        rest = max(0, len(skills) - 15)
        lines = []
        for sk in top:
            bar_len = int(sk.score * 14)
            bar = f"{GREEN}{'#' * bar_len}{GRAY}{'.' * (14 - bar_len)}{RESET}"
            src_color = CYAN if sk.source == "global" else MAGENTA if sk.source == "plugin" else YELLOW
            src = f"{src_color}[{sk.source[:6]}]{RESET}"
            lines.append(f"{src} {bar} {sk.score:.2f}  {BOLD}{sk.name[:30]}{RESET}")
        if rest:
            lines.append(f"{GRAY}... and {rest} more skills available{RESET}")
        for l in _box(f"SKILLS  (progressive disclosure — {len(skills)} total, top 15 shown)", lines, color=CYAN):
            _p(l)

    def _render_mcp(self, servers: List[McpServerInfo]):
        if not servers:
            return
        lines = []
        for s in servers:
            sc = GREEN if s.status in ("running", "ready") else YELLOW if s.status in ("lazy", "configured") else RED
            tag = f"{sc}[{s.status.upper()[:10]}]{RESET}"
            cmd = Path(s.command).name[:18]
            lines.append(f"{tag} {BOLD}{s.name:<22}{RESET}  cmd={cmd}")
        for l in _box("MCP SERVERS", lines, color=YELLOW):
            _p(l)

    def _render_plugins(self, plugins: List[PluginInfo]):
        if not plugins:
            return
        lines = []
        for p in plugins:
            hooks = f"  {GREEN}+hooks{RESET}" if p.has_hooks else ""
            lines.append(f"{MAGENTA}[plugin]{RESET} {BOLD}{p.name:<32}{RESET}  skills={p.skills_count}{hooks}")
        for l in _box("PLUGINS", lines, color=MAGENTA):
            _p(l)

    def _render_hooks(self, hooks_path: Optional[str]):
        status = f"{GREEN}FOUND{RESET} -> {hooks_path}" if hooks_path else f"{GRAY}not configured{RESET}"
        for l in _box("HOOKS  (lifecycle events)", [status], color=YELLOW):
            _p(l)

    def _render_internal_harness(self):
        lines = []
        try:
            from vazus_core.engine.subagent_framework import global_hook_registry
            n_start    = len(global_hook_registry._on_start_hooks)
            n_step     = len(global_hook_registry._on_step_hooks)
            n_verify   = len(global_hook_registry._on_verify_hooks)
            n_complete = len(global_hook_registry._on_complete_hooks)
            lines.append(f"{GREEN}on_start{RESET}:    {n_start} hooks  (HarnessPolicy + AutoSkillSelector + AGY-HUD)")
            lines.append(f"{GREEN}on_step{RESET}:     {n_step} hooks")
            lines.append(f"{GREEN}on_verify{RESET}:   {n_verify} hooks  (SecurityAPIQuota gate)")
            lines.append(f"{GREEN}on_complete{RESET}: {n_complete} hooks  (DB logger + AutoImprover Reflexion loop)")
        except Exception as e:
            lines.append(f"{RED}Could not load SubagentFramework: {e}{RESET}")

        # AutoImprover live stats
        try:
            from vazus_core.memory.auto_improver import get_auto_improver
            imp = get_auto_improver()
            top = imp.skill_tracker.get_top_skills(3)
            if top:
                top_str = "  ".join(f"{s['name']}={s['score']:.2f}" for s in top)
                lines.append(f"{CYAN}AutoImprover EMA{RESET}: top skills -> {top_str}")
        except Exception as exc:
            logger.debug("Failed retrieving AutoImprover stats for HUD: %s", exc)

        for l in _box("VAZUS INTERNAL HARNESS  (SubagentFramework hooks)", lines, color=BLUE):
            _p(l)


# ─────────────────────────────────────────────────────────
# Compact on_start hook (non-blocking, ~50ms)
# ─────────────────────────────────────────────────────────

def render_compact_hud():
    """
    Lightweight variant: prints 2 lines to terminal — skills top-5 + MCP status.
    Called automatically as SubagentFramework on_start hook.
    """
    try:
        scanner = CustomizationScanner()
        skills = scanner._scan_skills()
        mcp    = scanner._scan_mcp()

        if skills:
            top = skills[:5]
            names = "  ".join(f"{BOLD}{s.name[:20]}{RESET}({s.score:.2f})" for s in top)
            _p(f"{CYAN}[AGY-HUD Skills]{RESET} {names}")

        if mcp:
            parts = []
            for s in mcp:
                sc = GREEN if s.status in ("running", "ready") else YELLOW
                parts.append(f"{sc}{s.name}{RESET}:{s.status}")
            _p(f"{CYAN}[AGY-HUD MCP]{RESET} " + "  ".join(parts))
    except Exception as exc:
        logger.debug("Compact HUD rendering error: %s", exc)


# ─────────────────────────────────────────────────────────
# Register into SubagentFramework on_start
# ─────────────────────────────────────────────────────────

def _register_hud_hook():
    try:
        from vazus_core.engine.subagent_framework import global_hook_registry, SubagentContext

        def _hud_on_start(ctx: SubagentContext):
            render_compact_hud()

        _hud_on_start.__name__ = "_hud_on_start"  # named for dedup check
        names = [getattr(h, "__name__", "") for h in global_hook_registry._on_start_hooks]
        if "_hud_on_start" not in names:
            global_hook_registry.register_on_start(_hud_on_start)
    except Exception as exc:
        logger.debug("Failed registering HUD on_start hook: %s", exc)


_register_hud_hook()


# ─────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    _vt100()
    hud = CustomizationsHUD()

    if "--watch" in sys.argv:
        hud.watch(interval=10)
    elif "--skills" in sys.argv:
        hud.render_skills_only()
    elif "--mcp" in sys.argv:
        hud.render_mcp_only()
    else:
        hud.render()
