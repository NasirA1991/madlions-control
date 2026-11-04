"""Small, human-readable application settings."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields

from . import config


@dataclass
class AppSettings:
    theme: str = "system"
    last_page: str = "overview"
    window_width: int = 1180
    window_height: int = 780
    default_profile: str = ""
    advanced_writes: bool = False

    @classmethod
    def from_json(cls, data: dict) -> "AppSettings":
        allowed = {field.name for field in fields(cls)}
        clean = {key: value for key, value in data.items() if key in allowed}
        return cls(**clean)


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
        config.settings_path().write_text(
            json.dumps(asdict(settings), indent=2), encoding="utf-8"
        )
    except OSError:
        pass
