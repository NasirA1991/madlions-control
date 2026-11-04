"""Application identity and filesystem locations."""

from __future__ import annotations

import os
from pathlib import Path

VERSION = "0.1.1"
APP_ID = "io.github.madlionscontrol.MadlionsControl"
APP_NAME = "Madlions Control"
APP_SLUG = "madlions-control"
APP_SUMMARY = "Native configuration for MADLIONS magnetic-switch keyboards"
PROJECT_URL = "https://github.com/NasirA1991/madlions-control"
ISSUES_URL = f"{PROJECT_URL}/issues"
AUR_URL = "https://aur.archlinux.org/packages/madlions-control"

VID = 0x373B
VENDOR_NAME = "Shenzhen Yizhita Technology Co., Ltd."


def _xdg(env: str, fallback: Path) -> Path:
    raw = os.environ.get(env)
    return Path(raw) if raw else fallback


def data_dir() -> Path:
    """Read-only application data (profiles presets, icons)."""
    env = os.environ.get("MADLIONS_CONTROL_DATA")
    if env:
        return Path(env)
    local = Path(__file__).resolve().parent.parent / "data"
    if local.is_dir():
        return local
    return Path("/usr/share/madlions-control")


def config_dir() -> Path:
    return _xdg("XDG_CONFIG_HOME", Path.home() / ".config") / APP_SLUG


def profiles_dir() -> Path:
    env = os.environ.get("MADLIONS_CONTROL_PROFILES")
    if env:
        return Path(env)
    return _xdg("XDG_DATA_HOME", Path.home() / ".local" / "share") / APP_SLUG / "profiles"


def backups_dir() -> Path:
    return profiles_dir() / "backups"


def settings_path() -> Path:
    return config_dir() / "settings.json"


def is_flatpak() -> bool:
    return bool(os.environ.get("FLATPAK_ID")) or Path("/.flatpak-info").exists()
