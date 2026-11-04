"""Named profiles that can be saved, compared and applied.

Applying a profile never commits to flash: actuation and rapid-trigger values
are sent with the vendor's volatile "normal" write mode.  Only the explicit
:meth:`save_to_keyboard` action persists them.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from . import config
from .device import (
    CMD_DYNAMIC_KEYMAP_SET_BUFFER,
    AdvancedKey,
    AdvancedMode,
    BoxLight,
    DeadBand,
    Features,
    LightInfo,
    MadlionsDevice,
    RapidTrigger,
)
from .lighting import RGB
from .state import KeyboardState

PROFILE_VERSION = 2
_KEYS_SEPARATOR = ","


def _rc(text: str) -> tuple[int, int]:
    row, col = text.split(_KEYS_SEPARATOR)
    return int(row), int(col)


def _key(row: int, col: int) -> str:
    return f"{row}{_KEYS_SEPARATOR}{col}"


def _most_common(values: Iterable) -> object:
    counts: dict[object, int] = {}
    for value in values:
        key = value
        if isinstance(value, list):
            key = tuple(value)
        counts[key] = counts.get(key, 0) + 1
    return max(counts.items(), key=lambda item: item[1])[0]


def fit_colors(colors: list, src_cols: int, rows: int, cols: int) -> list[RGB]:
    """Re-lay a flat per-key colour list onto another matrix width."""
    clean = [tuple(int(v) for v in color[:3]) for color in colors if color]
    src_rows = 5
    src_cols = src_cols or (len(clean) // src_rows if len(clean) % src_rows == 0 else cols)
    out: list[RGB] = []
    for row in range(rows):
        for col in range(cols):
            if row < src_rows and col < src_cols:
                index = row * src_cols + col
                out.append(clean[index] if index < len(clean) else (0, 0, 0))
            else:
                out.append((0, 0, 0))
    return out[:rows * cols]


@dataclass
class Profile:
    name: str
    description: str = ""
    created: float = field(default_factory=time.time)
    version: int = PROFILE_VERSION

    actuation_default: float = 1.50
    actuation_overrides: dict[str, float] = field(default_factory=dict)
    rt_default: RapidTrigger = field(default_factory=RapidTrigger)
    rt_overrides: dict[str, RapidTrigger] = field(default_factory=dict)

    light: LightInfo | None = None
    colors: list[RGB] | None = None
    colors_cols: int = 15
    features: Features | None = None
    dead_band: DeadBand | None = None
    game_mode: int | None = None
    bottom_optimize: int | None = None
    box_light: BoxLight | None = None
    keymap_hex: str | None = None
    advanced_keys: list[dict] | None = None

    # -- value lookups -----------------------------------------------------
    def actuation_for(self, row: int, col: int) -> float:
        return self.actuation_overrides.get(_key(row, col), self.actuation_default)

    def rt_for(self, row: int, col: int) -> RapidTrigger:
        return self.rt_overrides.get(_key(row, col), self.rt_default)

    # -- serialisation -----------------------------------------------------
    def to_json(self) -> dict:
        out: dict = {
            "profile_version": self.version,
            "name": self.name,
            "description": self.description,
            "created": self.created,
            "actuation": {
                "default_mm": round(self.actuation_default, 2),
                "overrides": {k: round(v, 2) for k, v in sorted(self.actuation_overrides.items())},
            },
            "rapid_trigger": {
                "default": self.rt_default.to_json(),
                "overrides": {
                    key: value.to_json() for key, value in sorted(self.rt_overrides.items())
                },
            },
        }
        if self.light is not None:
            out["light"] = self.light.to_json()
        if self.colors is not None:
            out["colors"] = [list(color) for color in self.colors]
            out["colors_cols"] = self.colors_cols
        if self.features is not None:
            out["features"] = self.features.to_json()
        if self.dead_band is not None:
            out["dead_band"] = self.dead_band.to_json()
        if self.game_mode is not None:
            out["game_mode"] = self.game_mode
        if self.bottom_optimize is not None:
            out["bottom_optimize"] = self.bottom_optimize
        if self.box_light is not None:
            out["box_light"] = self.box_light.__dict__
        if self.keymap_hex:
            out["keymap_hex"] = self.keymap_hex
        if self.advanced_keys is not None:
            out["advanced_keys"] = self.advanced_keys
        return out

    @classmethod
    def from_json(cls, data: dict) -> "Profile":
        if int(data.get("profile_version", 0)) not in (1, PROFILE_VERSION):
            raise ValueError(f"unsupported profile version {data.get('profile_version')}")
        actuation = data.get("actuation", {})
        rt = data.get("rapid_trigger", {})
        light = data.get("light")
        features = data.get("features")
        dead_band = data.get("dead_band")
        box_light = data.get("box_light")
        return cls(
            name=str(data.get("name") or "Unnamed"),
            description=str(data.get("description") or ""),
            created=float(data.get("created") or time.time()),
            version=PROFILE_VERSION,
            actuation_default=float(actuation.get("default_mm", 1.5)),
            actuation_overrides={
                k: float(v) for k, v in (actuation.get("overrides") or {}).items()
            },
            rt_default=RapidTrigger(
                enabled=bool((rt.get("default") or {}).get("enabled", False)),
                press_mm=float((rt.get("default") or {}).get("press_mm", 0.5)),
                release_mm=float((rt.get("default") or {}).get("release_mm", 0.5)),
            ),
            rt_overrides={
                key: RapidTrigger(
                    enabled=bool(value.get("enabled", False)),
                    press_mm=float(value.get("press_mm", 0.5)),
                    release_mm=float(value.get("release_mm", 0.5)),
                )
                for key, value in (rt.get("overrides") or {}).items()
            },
            light=LightInfo(
                effect=int(light.get("effect", 0)),
                speed=int(light.get("speed", 0)),
                r=int(light.get("r", 0)),
                g=int(light.get("g", 0)),
                b=int(light.get("b", 0)),
                brightness=int(light.get("brightness", 0)),
            ) if light else None,
            colors=[tuple(int(v) for v in color[:3]) for color in data["colors"]]  # type: ignore[misc]
            if data.get("colors") else None,
            colors_cols=int(data.get("colors_cols") or 15),
            features=Features(
                rgb_area=int(features.get("rgb_area", 0)),
                wasd_swap=int(features.get("wasd_swap", 0)),
                mac_mode=int(features.get("mac_mode", 0)),
                win_lock=int(features.get("win_lock", 0)),
                nkro=int(features.get("nkro", 1)),
            ) if features else None,
            dead_band=DeadBand(
                top_mm=float(dead_band.get("top_mm", 0)),
                bottom_mm=float(dead_band.get("bottom_mm", 0)),
            ) if dead_band else None,
            game_mode=data.get("game_mode"),
            bottom_optimize=data.get("bottom_optimize"),
            box_light=BoxLight(
                mode=int(box_light.get("mode", 0)),
                colorful=int(box_light.get("colorful", 0)),
                brightness=int(box_light.get("brightness", 0)),
                speed=int(box_light.get("speed", 0)),
            ) if box_light else None,
            keymap_hex=data.get("keymap_hex"),
            advanced_keys=data.get("advanced_keys"),
        )

    def save(self, directory: Path | None = None) -> Path:
        directory = directory or config.profiles_dir()
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{safe_filename(self.name)}.json"
        path.write_text(json.dumps(self.to_json(), indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: Path) -> "Profile":
        return cls.from_json(json.loads(Path(path).read_text(encoding="utf-8-sig")))

    @classmethod
    def capture(cls, state: KeyboardState, name: str, description: str = "") -> "Profile":
        board = state.board
        actuation = list(state.actuation)
        triggers = list(state.rapid_trigger)
        act_default = 1.50
        rt_default = RapidTrigger(False, 0.50, 0.50)
        if actuation:
            common = _most_common([round(v, 2) for v in actuation])
            act_default = float(common)
        if triggers:
            common = _most_common([tuple(rt.to_json().values()) for rt in triggers])
            rt_default = RapidTrigger(
                enabled=bool(common[0]), press_mm=float(common[1]), release_mm=float(common[2])
            )
        act_overrides: dict[str, float] = {}
        rt_overrides: dict[str, RapidTrigger] = {}
        for index, (value, rt) in enumerate(zip(actuation, triggers)):
            row, col = divmod(index, board.cols)
            if abs(value - act_default) > 0.001:
                act_overrides[_key(row, col)] = round(value, 2)
            if rt != rt_default:
                rt_overrides[_key(row, col)] = rt
        return cls(
            name=name,
            description=description,
            actuation_default=act_default,
            actuation_overrides=act_overrides,
            rt_default=rt_default,
            rt_overrides=rt_overrides,
            light=state.light,
            colors=list(state.colors) if state.colors else None,
            colors_cols=board.cols,
            features=state.features,
            dead_band=state.dead_band,
            game_mode=state.game_mode,
            bottom_optimize=state.bottom_optimize,
            box_light=state.box_light,
            keymap_hex=state.keymap.hex() if state.keymap else None,
            advanced_keys=[key.to_json() for key in state.advanced_keys]
            if state.advanced_keys is not None else None,
        )

    # -- applying ----------------------------------------------------------
    def apply(
        self,
        device: MadlionsDevice,
        state: KeyboardState,
        *,
        include_keymap: bool = False,
        include_advanced: bool = False,
    ) -> list[str]:
        """Write the differences that matter.  Returns human-readable actions."""
        board = state.board
        actions: list[str] = []

        target_act = [self.actuation_for(row, col)
                      for row in range(board.rows) for col in range(board.cols)]
        target_rt = [self.rt_for(row, col)
                     for row in range(board.rows) for col in range(board.cols)]
        if any(abs(a - b) > 0.001 for a, b in zip(target_act, state.actuation)) or not state.actuation:
            device.write_actuation(target_act)
            actions.append("actuation points")

        if any(a != b for a, b in zip(target_rt, state.rapid_trigger)) or not state.rapid_trigger:
            device.write_rapid_trigger(target_rt)
            actions.append("rapid trigger")

        if self.light is not None:
            device.write_light(self.light)
            actions.append("lighting")

        if self.colors:
            colors = fit_colors(self.colors, self.colors_cols, board.rows, board.cols)
            device.write_all_key_colors(colors)
            actions.append("per-key colours")

        if self.features is not None:
            device.write_features(self.features)
            actions.append("keyboard switches")

        if self.dead_band is not None:
            device.write_dead_band(self.dead_band)
            actions.append("dead band")

        if self.game_mode is not None:
            device.write_game_mode(self.game_mode)
            actions.append("game mode")

        if self.bottom_optimize is not None:
            device.write_bottom_optimize(self.bottom_optimize)
            actions.append("bottom-out optimisation")

        if self.box_light is not None:
            device.write_box_light(self.box_light)
            actions.append("side light")

        if include_keymap and self.keymap_hex:
            keymap = bytes.fromhex(self.keymap_hex)
            if len(keymap) == board.keymap_size:
                device.write_buffer(CMD_DYNAMIC_KEYMAP_SET_BUFFER, keymap)
                actions.append("keymap")

        if include_advanced and self.advanced_keys:
            for entry in self.advanced_keys:
                try:
                    key1 = entry.get("key1") or [
                        entry.get("key1_row", 0), entry.get("key1_col", 0)
                    ]
                    key2 = entry.get("key2") or [
                        entry.get("key2_row", 0), entry.get("key2_col", 0)
                    ]
                    device.write_advanced_key(AdvancedKey(
                        index=int(entry["index"]),
                        mode=AdvancedMode[entry.get("mode", "NONE")],
                        key_id=int(entry.get("key_id", 0)),
                        rs_apc_lv=int(entry.get("rs_apc_lv", 0)),
                        gapc_sw=int(entry.get("gapc_sw", 0)),
                        rt_sw=int(entry.get("rt_sw", 0)),
                        key1_row=int(key1[0]),
                        key1_col=int(key1[1]),
                        key2_row=int(key2[0]),
                        key2_col=int(key2[1]),
                        layer=int(entry.get("layer", 0)),
                    ))
                except (KeyError, TypeError, ValueError, IndexError):
                    continue
            actions.append("advanced keys")
        return actions

    def save_to_keyboard(self, device: MadlionsDevice, state: KeyboardState) -> None:
        include_lighting = self.light is not None or self.colors is not None
        if include_lighting:
            device.save_lighting()
        device.commit()


def safe_filename(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in " -_." else "_" for ch in name).strip()
    return cleaned[:60] or "profile"


def list_profiles(directory: Path | None = None) -> list[Profile]:
    directory = directory or config.profiles_dir()
    profiles: list[Profile] = []
    if not directory.is_dir():
        return profiles
    for path in sorted(directory.glob("*.json")):
        if path.parent.name == "backups":
            continue
        try:
            profiles.append(Profile.load(path))
        except (OSError, ValueError, KeyError, TypeError):
            continue
    profiles.sort(key=lambda item: item.name.lower())
    return profiles


def ensure_default() -> None:
    directory = config.profiles_dir()
    if any(directory.glob("*.json")):
        return
    Profile.capture(
        KeyboardState(),
        "Default",
        "A starting point: 1.50 mm, no rapid trigger, custom lighting.",
    ).save(directory)


def auto_backup(state: KeyboardState, directory: Path | None = None) -> Path | None:
    if not state.connected or not state.actuation:
        return None
    directory = directory or config.backups_dir()
    directory.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = directory / f"backup-{stamp}.json"
    Profile.capture(state, f"backup-{stamp}", "Automatic snapshot").save(directory)
    backups = sorted(directory.glob("backup-*.json"))
    for old in backups[:-10]:
        try:
            old.unlink()
        except OSError:
            pass
    return path


def presets() -> list[Profile]:
    """Friendly starting points shown on the Profiles page."""
    rapid = Profile(
        name="Rapid fire",
        description="Short actuation and fast rapid trigger for competitive shooters.",
        actuation_default=0.50,
        rt_default=RapidTrigger(True, 0.10, 0.10),
        light=LightInfo(effect=2, speed=0, r=255, g=77, b=109, brightness=170),
    )
    balanced = Profile(
        name="Balanced",
        description="1.50 mm actuation, rapid trigger off — good for everything.",
        actuation_default=1.50,
        rt_default=RapidTrigger(False, 0.50, 0.50),
        light=LightInfo(effect=6, speed=128, r=255, g=77, b=109, brightness=150),
    )
    typing = Profile(
        name="Typing",
        description="Longer travel and no rapid trigger to avoid accidental presses.",
        actuation_default=2.00,
        rt_default=RapidTrigger(False, 0.50, 0.50),
        light=LightInfo(effect=2, speed=0, r=255, g=190, b=70, brightness=120),
    )
    return [rapid, balanced, typing]


def profile_summary(profile: Profile) -> str:
    pieces = [f"{profile.actuation_default:.2f} mm"]
    if profile.rt_default.enabled:
        pieces.append(
            f"RT {profile.rt_default.press_mm:.2f}/{profile.rt_default.release_mm:.2f} mm"
        )
    if profile.actuation_overrides or profile.rt_overrides:
        pieces.append(
            f"{len(set(profile.actuation_overrides) | set(profile.rt_overrides))} key overrides"
        )
    if profile.light:
        pieces.append(f"lighting #{profile.light.effect}")
    return " · ".join(pieces)


def parse_key_list(text: str) -> list[tuple[int, int]]:
    out = []
    for token in text.split():
        try:
            out.append(_rc(token))
        except (ValueError, IndexError):
            continue
    return out
