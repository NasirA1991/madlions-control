"""Small, human-readable application settings."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, fields

from . import config


@dataclass
class AppSettings:
    theme: str = "system"
    last_page: str = "overview"
    window_width: int = 1180
    window_height: int = 780

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
