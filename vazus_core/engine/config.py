"""
vazus_core/config.py — Centralized Configuration & Path Normalization Engine.
Provides dynamic resolution using Path.home(), environment variable overrides,
and relative parent directory calculation.
All storage is consolidated in the canonical vazus.db at services/memory/vazus.db.
"""

import os
import sys
from pathlib import Path
from dataclasses import dataclass, field


def _get_default_workspace() -> Path:
    """Calculates workspace root dynamically relative to vazus_core location."""
    for parent in Path(__file__).resolve().parents:
        if (parent / ".git").exists() or (parent / "services").exists() or parent.name.lower() == "vazus":
            return parent
    return Path("C:/vazus")


@dataclass
class Settings:
    # 1. Base Directory Resolutions
    USER_HOME: Path = field(default_factory=Path.home)
    WORKSPACE_DIR: Path = field(
        default_factory=lambda: Path(
            os.getenv("VAZUS_WORKSPACE_DIR", str(_get_default_workspace()))
        ).resolve()
    )

    # 2. Antigravity CLI & Gemini Ecosystem Paths
    GEMINI_DIR: Path = field(
        default_factory=lambda: Path(
            os.getenv("VAZUS_GEMINI_DIR", str(Path.home() / ".gemini"))
        ).resolve()
    )
    GEMINI_CLI_DIR: Path = field(
        default_factory=lambda: Path(
            os.getenv("VAZUS_GEMINI_CLI_DIR", str(Path.home() / ".gemini" / "antigravity-cli"))
        ).resolve()
    )
    GEMINI_SKILLS_DIR: Path = field(
        default_factory=lambda: Path(
            os.getenv("VAZUS_GEMINI_SKILLS_DIR", str(Path.home() / ".gemini" / "config" / "skills"))
        ).resolve()
    )
    CLI_SUMMARIES_DB: Path = field(
        default_factory=lambda: Path(
            os.getenv("VAZUS_CLI_SUMMARIES_DB", str(Path.home() / ".gemini" / "antigravity-cli" / "conversation_summaries.db"))
        ).resolve()
    )
    CLI_CONVERSATIONS_DIR: Path = field(
        default_factory=lambda: Path(
            os.getenv("VAZUS_CLI_CONVERSATIONS_DIR", str(Path.home() / ".gemini" / "antigravity-cli" / "conversations"))
        ).resolve()
    )
    CLI_SETTINGS_FILE: Path = field(
        default_factory=lambda: Path(
            os.getenv("VAZUS_CLI_SETTINGS_FILE", str(Path.home() / ".gemini" / "antigravity-cli" / "settings.json"))
        ).resolve()
    )

    # 3. Hermes Agent Skill Integration
    HERMES_SKILLS_DIR: Path = field(
        default_factory=lambda: Path(
            os.getenv("VAZUS_HERMES_SKILLS_DIR", str(Path.home() / "AppData" / "Local" / "hermes" / "hermes-agent" / "skills"))
        ).resolve()
    )
    HERMES_CONFIG_FILE: Path = field(
        default_factory=lambda: Path(
            os.getenv("VAZUS_HERMES_CONFIG_FILE", str(Path.home() / "AppData" / "Local" / "hermes" / "config.yaml"))
        ).resolve()
    )

    # 4. vazus OS Storage & Memory Databases
    VAZUS_DB_PATH: Path = field(
        default_factory=lambda: Path(
            os.getenv("VAZUS_DB_PATH", str(_get_default_workspace() / "services" / "memory" / "vazus.db"))
        ).resolve()
    )
    WIKI_DIR: Path = field(
        default_factory=lambda: Path(
            os.getenv("VAZUS_WIKI_DIR", str(_get_default_workspace() / "services" / "memory" / "semantic" / "wiki"))
        ).resolve()
    )
    DAEMON_STATE_FILE: Path = field(
        default_factory=lambda: Path(
            os.getenv("VAZUS_DAEMON_STATE_FILE", str(Path.home() / ".gemini" / "antigravity-cli" / "daemon_state.json"))
        ).resolve()
    )
    DAEMON_PID_FILE: Path = field(
        default_factory=lambda: Path(
            os.getenv("VAZUS_DAEMON_PID_FILE", str(_get_default_workspace() / "vazus.pid"))
        ).resolve()
    )

    # 5. LLM Models & Vector Config
    MODEL_FAST: str = os.getenv("VAZUS_MODEL_FAST", "gemini-3.5-flash")
    MODEL_PRO: str = os.getenv("VAZUS_MODEL_PRO", "gemini-3.5-pro")
    EMBEDDING_DIM: int = 768


settings = Settings()
