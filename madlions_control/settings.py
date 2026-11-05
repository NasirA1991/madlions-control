"""Small, human-readable application settings."""

from __future__ import annotations

import json
import math
import os
import tempfile
from dataclasses import asdict, dataclass, fields

from . import config

# Keep a corrupt or absurd settings file from preventing the window from
# opening.  These bounds are deliberately generous but finite.
MIN_WINDOW_WIDTH = 640
MAX_WINDOW_WIDTH = 8192
MIN_WINDOW_HEIGHT = 480
MAX_WINDOW_HEIGHT = 4320
VALID_THEMES = {"system", "dark", "light"}
VALID_PAGES = {
    "overview",
    "perkey",
    "lighting",
    "keymap",
    "macros",
    "advanced",
    "test",
    "profiles",
}


def _int_setting(value: object, default: int, lower: int, upper: int) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    if not math.isfinite(float(value)):
        return default
    return max(lower, min(upper, int(value)))


@dataclass
class AppSettings:
    theme: str = "system"
    last_page: str = "overview"
    window_width: int = 1180
    window_height: int = 780

    @classmethod
    def from_json(cls, data: object) -> "AppSettings":
        if not isinstance(data, dict):
            return cls()
        allowed = {field.name for field in fields(cls)}
        clean = {key: value for key, value in data.items() if key in allowed}

        theme = clean.get("theme")
        if not isinstance(theme, str) or theme not in VALID_THEMES:
            theme = cls.theme

        last_page = clean.get("last_page")
        if not isinstance(last_page, str) or last_page not in VALID_PAGES:
            last_page = cls.last_page

        return cls(
            theme=theme,
            last_page=last_page,
            window_width=_int_setting(
                clean.get("window_width"), cls.window_width,
                MIN_WINDOW_WIDTH, MAX_WINDOW_WIDTH,
            ),
            window_height=_int_setting(
                clean.get("window_height"), cls.window_height,
                MIN_WINDOW_HEIGHT, MAX_WINDOW_HEIGHT,
            ),
        )


def load() -> AppSettings:
    try:
        raw = json.loads(config.settings_path().read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            return AppSettings.from_json(raw)
    except (OSError, ValueError, TypeError):
        pass
    return AppSettings()


def save(settings: AppSettings) -> None:
    try:
        config.config_dir().mkdir(parents=True, exist_ok=True)
        path = config.settings_path()
        fd, temporary = tempfile.mkstemp(prefix=".settings-", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(asdict(settings), handle, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        except Exception:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise
    except OSError:
        pass
