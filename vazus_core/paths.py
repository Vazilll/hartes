"""
vazus_core.paths
================
Single Source of Truth (SSOT) for filesystem topology and cross-platform path resolution.
Guarantees seamless execution on Windows (/home/tarhes/Проекты/vazus), Linux (/app or /vazus), and Docker containers.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional, Union

# Root determination: VAZUS_ROOT env var -> fallback to repository root dynamically
_ENV_ROOT = os.environ.get("VAZUS_ROOT")
if _ENV_ROOT:
    VAZUS_ROOT = Path(_ENV_ROOT).resolve()
else:
    # vazus_core/paths.py is at <ROOT>/vazus_core/paths.py
    VAZUS_ROOT = Path(__file__).resolve().parent.parent

# Core directory hierarchy
SERVICES_DIR = VAZUS_ROOT / "services"
MEMORY_DIR = SERVICES_DIR / "memory"
WIKI_DIR = MEMORY_DIR / "semantic" / "wiki"
DATA_DIR = VAZUS_ROOT / "data"
LOGS_DIR = DATA_DIR / "logs"
CACHE_DIR = DATA_DIR / "cache"
MODELS_DIR = DATA_DIR / "models"
SKILLS_DIR = VAZUS_ROOT / "skills"
PROJECTS_DIR = VAZUS_ROOT / "projects"
TOOLS_DIR = VAZUS_ROOT / "tools"
SCRATCH_DIR = VAZUS_ROOT / "scratch"

# Canonical database path (respects VAZUS_DB_PATH if set)
_ENV_DB = os.environ.get("VAZUS_DB_PATH")
if _ENV_DB and _ENV_DB != ":memory:":
    DEFAULT_DB_PATH = Path(_ENV_DB).resolve()
elif _ENV_DB == ":memory:":
    DEFAULT_DB_PATH = Path(":memory:")
else:
    DEFAULT_DB_PATH = MEMORY_DIR / "vazus.db"

# Active Python interpreter
PYTHON_EXE = Path(sys.executable)

# Pre-invocation HUD & telemetry
HUD_SESSION_LOG = LOGS_DIR / "hud_session.jsonl"
STOP_HOOK_STATE_FILE = VAZUS_ROOT / ".stop_hook_state.json"
TEST_LOCK_FILE = VAZUS_ROOT / ".vazus_test.lock"

# Standard Skill Search Paths (cross-platform)
def get_skill_search_dirs() -> list[Path]:
    dirs = [SKILLS_DIR]
    if sys.platform == "win32":
        local_app = os.environ.get("LOCALAPPDATA")
        if local_app:
            dirs.append(Path(local_app) / "hermes" / "hermes-agent" / "skills")
        user_profile = os.environ.get("USERPROFILE")
        if user_profile:
            dirs.append(Path(user_profile) / ".gemini" / "antigravity" / "builtin" / "skills")
    home = Path.home()
    dirs.append(home / ".gemini" / "config" / "skills")
    dirs.append(home / ".local" / "share" / "hermes" / "hermes-agent" / "skills")
    dirs.append(home / ".gemini" / "antigravity" / "builtin" / "skills")
    result: list[Path] = []
    for d in dirs:
        try:
            if d.is_dir():
                result.append(d)
        except (PermissionError, OSError):
            continue
    return result


def get_sqlite_ro_uri(db_path: Optional[Union[str, Path]] = None) -> str:
    """Returns standard URI for read-only SQLite access across Windows and Linux."""
    target = Path(db_path) if db_path else DEFAULT_DB_PATH
    if str(target) == ":memory:":
        return ":memory:"
    # Use as_posix() so Windows forward-slashes work cleanly with sqlite3 URI
    posix_path = target.as_posix()
    return f"file:{posix_path}?mode=ro"


def resolve_within_root(relative_or_subpath: Union[str, Path]) -> Path:
    """Safely resolves path within VAZUS_ROOT."""
    p = Path(relative_or_subpath)
    if p.is_absolute():
        return p.resolve()
    return (VAZUS_ROOT / p).resolve()
