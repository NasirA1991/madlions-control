"""Named tuning profiles, full backups and presets.

Two concepts are kept deliberately separate:

* a **tuning profile** contains the safe, normally volatile settings: actuation,
  rapid trigger, lighting, switches and dead band;
* a **full backup** additionally contains the keymap, macros, advanced keys,
  hold/click and DKS bindings.  Applying those sections writes onboard memory
  immediately, so the UI asks for confirmation first.

Imported JSON is treated as untrusted input: it is size-limited, schema-checked
and range-checked before it can reach a device.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from . import config
from .device import (
    CMD_DYNAMIC_KEYMAP_SET_BUFFER,
    CMD_MACRO_SET_BUFFER,
    AdvancedKey,
    AdvancedMode,
    BoxLight,
    DeadBand,
    Dks,
    DksAction,
    Features,
    LightInfo,
    MadlionsDevice,
    RapidTrigger,
    TapDance,
)
from .lighting import RGB
from .state import KeyboardState

PROFILE_VERSION = 3
MAX_PROFILE_BYTES = 1 << 20
_KEYS_SEPARATOR = ","

TUNING_SECTIONS = (
    "actuation",
    "rapid_trigger",
    "lighting",
    "per-key_colours",
    "switches",
    "dead_band",
    "game_mode",
    "bottom_optimize",
    "side_light",
)
FULL_ONLY_SECTIONS = ("keymap", "macros", "advanced_keys", "hold_click", "dks")
ALL_SECTIONS = TUNING_SECTIONS + FULL_ONLY_SECTIONS
PERSISTENT_SECTIONS = frozenset(FULL_ONLY_SECTIONS)


class ProfileValidationError(ValueError):
    """An imported profile is malformed or outside the supported ranges."""


def _rc(text: str) -> tuple[int, int]:
    row, col = text.split(_KEYS_SEPARATOR)
    return int(row), int(col)


def _key(row: int, col: int) -> str:
    return f"{row}{_KEYS_SEPARATOR}{col}"


def _most_common(values: Iterable) -> object:
    counts: dict[object, int] = {}
    for value in values:
        key = tuple(value) if isinstance(value, list) else value
        counts[key] = counts.get(key, 0) + 1
    return max(counts.items(), key=lambda item: item[1])[0]


def _reject_constant(value: str) -> None:
    raise ProfileValidationError(f"non-finite number {value!r} is not allowed")


def _mapping(value: Any, name: str) -> dict:
    if not isinstance(value, dict):
        raise ProfileValidationError(f"{name} must be an object")
    return value


def _sequence(value: Any, name: str, maximum: int) -> list:
    if not isinstance(value, list):
        raise ProfileValidationError(f"{name} must be a list")
    if len(value) > maximum:
        raise ProfileValidationError(f"{name} has too many entries")
    return value


def _number(value: Any, name: str, lower: float, upper: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProfileValidationError(f"{name} must be a number")
    if not math.isfinite(float(value)):
        raise ProfileValidationError(f"{name} must be finite")
    if not lower <= float(value) <= upper:
        raise ProfileValidationError(f"{name} must be between {lower:g} and {upper:g}")
    return float(value)


def _integer(value: Any, name: str, lower: int, upper: int) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProfileValidationError(f"{name} must be an integer")
    if isinstance(value, float) and not value.is_integer():
        raise ProfileValidationError(f"{name} must be an integer")
    number = int(value)
    if not lower <= number <= upper:
        raise ProfileValidationError(f"{name} must be between {lower} and {upper}")
    return number


def _flag(value: Any, name: str) -> int:
    return _integer(value, name, 0, 1)


def _rgb(value: Any, name: str) -> RGB:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ProfileValidationError(f"{name} must be an RGB triple")
    return tuple(_integer(component, name, 0, 255) for component in value)  # type: ignore[return-value]


def _coord(entry: dict, prefix: str, name: str, *, allow_unused: bool = False) -> tuple[int, int]:
    nested = entry.get(prefix)
    if nested is not None:
        if not isinstance(nested, (list, tuple)) or len(nested) != 2:
            raise ProfileValidationError(f"{name}.{prefix} must be [row, column]")
        row, col = nested
    else:
        row = entry.get(f"{prefix}_row", 0)
        col = entry.get(f"{prefix}_col", 0)
    if allow_unused and row in (255, None) and col in (255, None):
        return 0, 0
    return _integer(row, f"{name}.{prefix}_row", 0, 4), _integer(
        col, f"{name}.{prefix}_col", 0, 31
    )


def _hex_bytes(value: Any, name: str, maximum: int) -> str:
    if not isinstance(value, str) or len(value) % 2:
        raise ProfileValidationError(f"{name} must be a hexadecimal string")
    if len(value) > maximum * 2:
        raise ProfileValidationError(f"{name} is too large")
    try:
        bytes.fromhex(value)
    except ValueError as exc:
        raise ProfileValidationError(f"{name} is not valid hexadecimal") from exc
    return value.lower()


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


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
    kind: str = "tuning"
    captured_sections: list[str] = field(default_factory=list)

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
    macros_hex: str | None = None
    advanced_keys: list[dict] | None = None
    tap_dance: list[dict] | None = None
    dks: list[dict] | None = None

    # -- value lookups -----------------------------------------------------
    def actuation_for(self, row: int, col: int) -> float:
        return self.actuation_overrides.get(_key(row, col), self.actuation_default)

    def rt_for(self, row: int, col: int) -> RapidTrigger:
        return self.rt_overrides.get(_key(row, col), self.rt_default)

    @property
    def is_full(self) -> bool:
        return self.kind == "full" or bool(
            set(self.captured_sections) & PERSISTENT_SECTIONS
        )

    @property
    def has_persistent_sections(self) -> bool:
        return bool(set(self.captured_sections) & PERSISTENT_SECTIONS)

    # -- serialisation -----------------------------------------------------
    def to_json(self) -> dict:
        out: dict = {
            "profile_version": self.version,
            "name": self.name,
            "description": self.description,
            "created": self.created,
            "kind": self.kind,
            "captured_sections": list(self.captured_sections),
            "actuation": {
                "default_mm": round(self.actuation_default, 2),
                "overrides": {
                    key: round(value, 2)
                    for key, value in sorted(self.actuation_overrides.items())
                },
            },
            "rapid_trigger": {
                "default": self.rt_default.to_json(),
                "overrides": {
                    key: value.to_json()
                    for key, value in sorted(self.rt_overrides.items())
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
        if self.macros_hex:
            out["macros_hex"] = self.macros_hex
        if self.advanced_keys is not None:
            out["advanced_keys"] = self.advanced_keys
        if self.tap_dance is not None:
            out["tap_dance"] = self.tap_dance
        if self.dks is not None:
            out["dks"] = self.dks
        return out

    @classmethod
    def from_json(cls, data: dict) -> "Profile":
        data = _mapping(data, "profile")
        version = _integer(data.get("profile_version", 0), "profile_version", 1, PROFILE_VERSION)
        name = str(data.get("name") or "Unnamed").strip()
        if not name or len(name) > 80:
            raise ProfileValidationError("name must contain 1–80 characters")
        description = str(data.get("description") or "")
        if len(description) > 500:
            raise ProfileValidationError("description is too long")
        created = _number(data.get("created", time.time()), "created", 0, 10**11)

        actuation = _mapping(data.get("actuation") or {}, "actuation")
        act_default = _number(actuation.get("default_mm", 1.5), "actuation.default_mm",
                              0.05, 3.40)
        act_overrides_raw = _mapping(actuation.get("overrides") or {}, "actuation.overrides")
        if len(act_overrides_raw) > 128:
            raise ProfileValidationError("too many actuation overrides")
        act_overrides: dict[str, float] = {}
        for key, value in act_overrides_raw.items():
            row, col = _rc(str(key))
            if not (0 <= row <= 4 and 0 <= col <= 31):
                raise ProfileValidationError(f"invalid actuation coordinate {key!r}")
            act_overrides[_key(row, col)] = _number(
                value, f"actuation.overrides.{key}", 0.05, 3.40
            )

        rt = _mapping(data.get("rapid_trigger") or {}, "rapid_trigger")
        rt_default_raw = _mapping(rt.get("default") or {}, "rapid_trigger.default")
        rt_default = RapidTrigger(
            enabled=bool(rt_default_raw.get("enabled", False)),
            press_mm=_number(rt_default_raw.get("press_mm", 0.5),
                             "rapid_trigger.default.press_mm", 0.01, 3.40),
            release_mm=_number(rt_default_raw.get("release_mm", 0.5),
                               "rapid_trigger.default.release_mm", 0.01, 3.40),
        )
        rt_overrides_raw = _mapping(rt.get("overrides") or {}, "rapid_trigger.overrides")
        if len(rt_overrides_raw) > 128:
            raise ProfileValidationError("too many rapid-trigger overrides")
        rt_overrides: dict[str, RapidTrigger] = {}
        for key, value in rt_overrides_raw.items():
            row, col = _rc(str(key))
            if not (0 <= row <= 4 and 0 <= col <= 31):
                raise ProfileValidationError(f"invalid rapid-trigger coordinate {key!r}")
            value = _mapping(value, f"rapid_trigger.overrides.{key}")
            rt_overrides[_key(row, col)] = RapidTrigger(
                enabled=bool(value.get("enabled", False)),
                press_mm=_number(value.get("press_mm", 0.5),
                                 f"rapid_trigger.overrides.{key}.press_mm", 0.01, 3.40),
                release_mm=_number(value.get("release_mm", 0.5),
                                   f"rapid_trigger.overrides.{key}.release_mm", 0.01, 3.40),
            )

        light = data.get("light")
        light_info = None
        if light is not None:
            light = _mapping(light, "light")
            light_info = LightInfo(
                effect=_integer(light.get("effect", 0), "light.effect", 0, 255),
                speed=_integer(light.get("speed", 0), "light.speed", 0, 255),
                r=_integer(light.get("r", 0), "light.r", 0, 255),
                g=_integer(light.get("g", 0), "light.g", 0, 255),
                b=_integer(light.get("b", 0), "light.b", 0, 255),
                brightness=_integer(light.get("brightness", 0), "light.brightness", 0, 210),
            )

        colors = None
        colors_cols = _integer(data.get("colors_cols", 15), "colors_cols", 1, 32)
        if data.get("colors") is not None:
            raw_colors = _sequence(data["colors"], "colors", 512)
            colors = [_rgb(color, "colors") for color in raw_colors]
            if not colors:
                colors = None

        features = None
        if data.get("features") is not None:
            raw = _mapping(data["features"], "features")
            features = Features(
                rgb_area=_flag(raw.get("rgb_area", 0), "features.rgb_area"),
                wasd_swap=_flag(raw.get("wasd_swap", 0), "features.wasd_swap"),
                mac_mode=_flag(raw.get("mac_mode", 0), "features.mac_mode"),
                win_lock=_flag(raw.get("win_lock", 0), "features.win_lock"),
                nkro=_flag(raw.get("nkro", 1), "features.nkro"),
            )

        dead_band = None
        if data.get("dead_band") is not None:
            raw = _mapping(data["dead_band"], "dead_band")
            dead_band = DeadBand(
                top_mm=_number(raw.get("top_mm", 0), "dead_band.top_mm", 0, 0.5),
                bottom_mm=_number(raw.get("bottom_mm", 0), "dead_band.bottom_mm", 0, 0.5),
            )

        game_mode = None if data.get("game_mode") is None else _integer(
            data["game_mode"], "game_mode", 0, 255
        )
        bottom_optimize = None if data.get("bottom_optimize") is None else _integer(
            data["bottom_optimize"], "bottom_optimize", 0, 255
        )

        box_light = None
        if data.get("box_light") is not None:
            raw = _mapping(data["box_light"], "box_light")
            box_light = BoxLight(
                mode=_integer(raw.get("mode", 0), "box_light.mode", 0, 255),
                colorful=_flag(raw.get("colorful", 0), "box_light.colorful"),
                brightness=_integer(raw.get("brightness", 0), "box_light.brightness", 0, 255),
                speed=_integer(raw.get("speed", 0), "box_light.speed", 0, 255),
            )

        keymap_hex = data.get("keymap_hex")
        if keymap_hex:
            keymap_hex = _hex_bytes(keymap_hex, "keymap_hex", 2048)

        macros_hex = data.get("macros_hex")
        if macros_hex:
            macros_hex = _hex_bytes(macros_hex, "macros_hex", 65536)

        advanced_keys = None
        if data.get("advanced_keys") is not None:
            raw_entries = _sequence(data["advanced_keys"], "advanced_keys", 32)
            advanced_keys = []
            for index, entry in enumerate(raw_entries):
                entry = _mapping(entry, f"advanced_keys[{index}]")
                mode_name = str(entry.get("mode", "NONE"))
                if mode_name not in AdvancedMode.__members__:
                    raise ProfileValidationError(f"advanced_keys[{index}].mode is invalid")
                unused = mode_name == "NONE"
                key1 = _coord(entry, "key1", f"advanced_keys[{index}]",
                              allow_unused=unused)
                key2 = _coord(entry, "key2", f"advanced_keys[{index}]",
                              allow_unused=unused)
                advanced_keys.append({
                    "index": _integer(entry.get("index", index), "advanced_keys.index", 0, 31),
                    "mode": mode_name,
                    "key_id": _integer(entry.get("key_id", 0), "advanced_keys.key_id", 0, 255),
                    "rs_apc_lv": _integer(entry.get("rs_apc_lv", 0),
                                          "advanced_keys.rs_apc_lv", 0, 0xFFFF),
                    "gapc_sw": _flag(entry.get("gapc_sw", 0), "advanced_keys.gapc_sw"),
                    "rt_sw": _flag(entry.get("rt_sw", 0), "advanced_keys.rt_sw"),
                    "key1": list(key1),
                    "key2": list(key2),
                    "layer": _integer(entry.get("layer", 0), "advanced_keys.layer", 0, 3),
                })

        tap_dance = None
        if data.get("tap_dance") is not None:
            raw_entries = _sequence(data["tap_dance"], "tap_dance", 32)
            tap_dance = []
            for entry in raw_entries:
                entry = _mapping(entry, "tap_dance entry")
                tap_dance.append({
                    "index": _integer(entry.get("index", 0), "tap_dance.index", 0, 31),
                    "tap": _integer(entry.get("tap", 0), "tap_dance.tap", 0, 0xFFFF),
                    "hold": _integer(entry.get("hold", 0), "tap_dance.hold", 0, 0xFFFF),
                    "timer_ms": _integer(entry.get("timer_ms", 200),
                                         "tap_dance.timer_ms", 0, 5000),
                })

        dks = None
        if data.get("dks") is not None:
            raw_entries = _sequence(data["dks"], "dks", 32)
            dks = []
            for entry in raw_entries:
                entry = _mapping(entry, "dks entry")
                actions = _sequence(entry.get("actions") or [], "dks.actions", 4)
                normalized = []
                for action in actions:
                    action = _mapping(action, "dks action")
                    normalized.append({
                        "status": _integer(action.get("status", 0), "dks.status", 0, 0x3FF),
                        "keycode": _integer(action.get("keycode", 0),
                                            "dks.keycode", 0, 0xFFFF),
                    })
                dks.append({
                    "index": _integer(entry.get("index", 0), "dks.index", 0, 31),
                    "actions": normalized,
                })

        captured = data.get("captured_sections")
        if captured is not None:
            captured = _sequence(captured, "captured_sections", len(ALL_SECTIONS))
            for section in captured:
                if section not in ALL_SECTIONS:
                    raise ProfileValidationError(f"unknown section {section!r}")
            captured_sections = list(dict.fromkeys(str(section) for section in captured))
        else:
            captured_sections = ["actuation", "rapid_trigger"]
            if light_info is not None:
                captured_sections.append("lighting")
            if colors:
                captured_sections.append("per-key_colours")
            if features is not None:
                captured_sections.append("switches")
            if dead_band is not None:
                captured_sections.append("dead_band")
            if game_mode is not None:
                captured_sections.append("game_mode")
            if bottom_optimize is not None:
                captured_sections.append("bottom_optimize")
            if box_light is not None:
                captured_sections.append("side_light")
            if keymap_hex:
                captured_sections.append("keymap")
            if macros_hex:
                captured_sections.append("macros")
            if advanced_keys:
                captured_sections.append("advanced_keys")
            if tap_dance:
                captured_sections.append("hold_click")
            if dks:
                captured_sections.append("dks")

        kind = data.get("kind")
        if kind is None:
            kind = "full" if set(captured_sections) & PERSISTENT_SECTIONS else "tuning"
        if kind not in ("tuning", "full"):
            raise ProfileValidationError("kind must be 'tuning' or 'full'")

        return cls(
            name=name,
            description=description,
            created=created,
            version=PROFILE_VERSION,
            kind=kind,
            captured_sections=captured_sections,
            actuation_default=act_default,
            actuation_overrides=act_overrides,
            rt_default=rt_default,
            rt_overrides=rt_overrides,
            light=light_info,
            colors=colors,
            colors_cols=colors_cols,
            features=features,
            dead_band=dead_band,
            game_mode=game_mode,
            bottom_optimize=bottom_optimize,
            box_light=box_light,
            keymap_hex=keymap_hex,
            macros_hex=macros_hex,
            advanced_keys=advanced_keys,
            tap_dance=tap_dance,
            dks=dks,
        )

    def save(self, directory: Path | None = None) -> Path:
        directory = directory or config.profiles_dir()
        directory.mkdir(parents=True, exist_ok=True)
        base = safe_filename(self.name)
        path = directory / f"{base}.json"
        if path.exists():
            try:
                existing_name = json.loads(path.read_text(encoding="utf-8-sig")).get("name")
            except (OSError, ValueError):
                existing_name = None
            if existing_name != self.name:
                suffix = hashlib.sha1(self.name.encode("utf-8")).hexdigest()[:8]
                path = directory / f"{base}-{suffix}.json"
        _atomic_write(path, json.dumps(self.to_json(), indent=2))
        return path

    @classmethod
    def load(cls, path: Path) -> "Profile":
        path = Path(path)
        try:
            if path.stat().st_size > MAX_PROFILE_BYTES:
                raise ProfileValidationError("profile is larger than 1 MiB")
            text = path.read_text(encoding="utf-8-sig")
        except OSError as exc:
            raise ProfileValidationError(f"could not read {path.name}: {exc}") from exc
        try:
            data = json.loads(text, parse_constant=_reject_constant)
        except (ValueError, TypeError) as exc:
            if isinstance(exc, ProfileValidationError):
                raise
            raise ProfileValidationError(f"{path.name} is not valid JSON") from exc
        return cls.from_json(data)

    @classmethod
    def capture(
        cls, state: KeyboardState, name: str, description: str = "", *,
        full: bool = False,
    ) -> "Profile":
        board = state.board
        actuation = list(state.actuation)
        triggers = list(state.rapid_trigger)
        act_default = 1.50
        rt_default = RapidTrigger(False, 0.50, 0.50)
        if actuation:
            act_default = float(_most_common([round(value, 2) for value in actuation]))
        if triggers:
            common = _most_common([tuple(rt.to_json().values()) for rt in triggers])
            rt_default = RapidTrigger(
                enabled=bool(common[0]), press_mm=float(common[1]),
                release_mm=float(common[2])
            )
        act_overrides: dict[str, float] = {}
        rt_overrides: dict[str, RapidTrigger] = {}
        for index, (value, rt) in enumerate(zip(actuation, triggers)):
            row, col = divmod(index, board.cols)
            if abs(value - act_default) > 0.001:
                act_overrides[_key(row, col)] = round(value, 2)
            if rt != rt_default:
                rt_overrides[_key(row, col)] = rt
        profile = cls(
            name=name,
            description=description,
            kind="full" if full else "tuning",
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
        )
        if full:
            profile.keymap_hex = state.keymap.hex() if state.keymap else None
            profile.macros_hex = state.macros.hex() if state.macros else None
            if state.advanced_keys is not None:
                entries = []
                for key in state.advanced_keys:
                    entry = key.to_json()
                    if not key.active:
                        entry["key1"] = [0, 0]
                        entry["key2"] = [0, 0]
                        entry["key_id"] = 0
                    entries.append(entry)
                profile.advanced_keys = entries
            else:
                profile.advanced_keys = None
            profile.tap_dance = (
                [{"index": tap.index, "tap": tap.tap, "hold": tap.hold,
                  "timer_ms": tap.timer_ms} for tap in state.tap_dance]
                if state.tap_dance is not None else None
            )
            profile.dks = (
                [{"index": dks.index,
                  "actions": [{"status": action.status, "keycode": action.keycode}
                              for action in dks.actions]}
                 for dks in state.dks]
                if state.dks is not None else None
            )
        profile.captured_sections = _sections_of(profile)
        return profile

    @classmethod
    def capture_device(
        cls, device: MadlionsDevice, name: str, description: str = "", *,
        full: bool = False,
    ) -> "Profile":
        from . import state as state_mod

        state = state_mod.load_basic(device)
        state = state_mod.load_colors(device, state, strict=full)
        if full:
            state = state_mod.load_keymap(device, state)
            state = state_mod.load_macros(device, state)
            state = state_mod.load_advanced(device, state)
            if state.colors is None:
                raise ProfileValidationError(
                    "the keyboard returned no per-key colour data"
                )
        return cls.capture(state, name, description, full=full)

    # -- applying ----------------------------------------------------------
    def apply(
        self,
        device: MadlionsDevice,
        state: KeyboardState,
        *,
        include_keymap: bool = False,
        include_macros: bool = False,
        include_advanced: bool = False,
    ) -> list[str]:
        """Write the selected sections.  Persistent sections need explicit opt-in."""
        board = state.board
        actions: list[str] = []

        # Validate every persistent section before writing anything, so a
        # backup from another layout cannot leave a half-applied profile.
        if include_keymap and self.keymap_hex:
            keymap = bytes.fromhex(self.keymap_hex)
            if len(keymap) != board.keymap_size:
                raise ProfileValidationError(
                    f"this keymap is {len(keymap)} bytes; {board.name} expects "
                    f"{board.keymap_size}"
                )
        macros = None
        if include_macros and self.macros_hex:
            macros = bytes.fromhex(self.macros_hex)
            device_size = device.read_macro_buffer_size()
            if device_size and len(macros) != device_size:
                raise ProfileValidationError(
                    f"this macro buffer is {len(macros)} bytes; the keyboard expects "
                    f"{device_size}"
                )
        if include_advanced and self.advanced_keys is not None:
            for entry in self.advanced_keys:
                key1 = entry.get("key1") or [
                    entry.get("key1_row", 0), entry.get("key1_col", 0)
                ]
                key2 = entry.get("key2") or [
                    entry.get("key2_row", 0), entry.get("key2_col", 0)
                ]
                if not (0 <= int(key1[0]) < board.rows
                        and 0 <= int(key1[1]) < board.cols
                        and 0 <= int(key2[0]) < board.rows
                        and 0 <= int(key2[1]) < board.cols):
                    raise ProfileValidationError(
                        f"advanced key {entry.get('index')} uses a coordinate outside "
                        f"the {board.rows}x{board.cols} matrix"
                    )

        target_act = [self.actuation_for(row, col)
                      for row in range(board.rows) for col in range(board.cols)]
        target_rt = [self.rt_for(row, col)
                     for row in range(board.rows) for col in range(board.cols)]
        if any(abs(a - b) > 0.001 for a, b in zip(target_act, state.actuation)) or not state.actuation:
            device.write_actuation(target_act)
            actions.append(f"{len(target_act)} actuation values")

        if any(a != b for a, b in zip(target_rt, state.rapid_trigger)) or not state.rapid_trigger:
            device.write_rapid_trigger(target_rt)
            actions.append(f"{len(target_rt)} rapid-trigger values")

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

        if self.box_light is not None and board.side_light:
            device.write_box_light(self.box_light)
            actions.append("side light")

        if include_keymap and self.keymap_hex:
            device.write_buffer(CMD_DYNAMIC_KEYMAP_SET_BUFFER, keymap)
            actions.append("keymap (persistent)")

        if include_macros and macros is not None:
            device.write_macros(macros)
            actions.append("macros (persistent)")

        if include_advanced and self.advanced_keys is not None:
            for entry in self.advanced_keys:
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
            actions.append(f"{len(self.advanced_keys)} advanced-key slots (persistent)")

        if include_advanced and self.tap_dance is not None:
            for entry in self.tap_dance:
                device.write_tap_dance(TapDance(
                    index=int(entry["index"]),
                    tap=int(entry.get("tap", 0)),
                    hold=int(entry.get("hold", 0)),
                    timer_ms=int(entry.get("timer_ms", 200)),
                ))
            actions.append(f"{len(self.tap_dance)} hold/click slots (persistent)")

        if include_advanced and self.dks is not None:
            for entry in self.dks:
                actions_raw = entry.get("actions") or []
                dks_actions = tuple(
                    DksAction(status=int(action.get("status", 0)),
                              keycode=int(action.get("keycode", 0)))
                    for action in actions_raw[:4]
                )
                while len(dks_actions) < 4:
                    dks_actions += (DksAction(),)  # type: ignore[assignment]
                device.write_dks(Dks(index=int(entry["index"]), actions=dks_actions))
            actions.append(f"{len(self.dks)} DKS slots (persistent)")
        return actions

    def save_to_keyboard(self, device: MadlionsDevice, state: KeyboardState) -> None:
        include_lighting = self.light is not None or self.colors is not None
        if include_lighting:
            device.save_lighting()
        device.commit()


def _sections_of(profile: Profile) -> list[str]:
    sections = ["actuation", "rapid_trigger"]
    if profile.light is not None:
        sections.append("lighting")
    if profile.colors:
        sections.append("per-key_colours")
    if profile.features is not None:
        sections.append("switches")
    if profile.dead_band is not None:
        sections.append("dead_band")
    if profile.game_mode is not None:
        sections.append("game_mode")
    if profile.bottom_optimize is not None:
        sections.append("bottom_optimize")
    if profile.box_light is not None:
        sections.append("side_light")
    if profile.keymap_hex:
        sections.append("keymap")
    if profile.macros_hex:
        sections.append("macros")
    if profile.advanced_keys is not None:
        sections.append("advanced_keys")
    if profile.tap_dance is not None:
        sections.append("hold_click")
    if profile.dks is not None:
        sections.append("dks")
    return sections


def safe_filename(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in " -_." else "_" for ch in name).strip()
    return cleaned.lstrip(".")[:60] or "profile"


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


def list_backups(directory: Path | None = None) -> list[tuple[Path, Profile]]:
    directory = directory or config.backups_dir()
    entries: list[tuple[Path, Profile]] = []
    if not directory.is_dir():
        return entries
    for path in sorted(directory.glob("*.json"), reverse=True):
        try:
            entries.append((path, Profile.load(path)))
        except (OSError, ValueError):
            continue
    return entries


def ensure_default() -> None:
    directory = config.profiles_dir()
    if any(directory.glob("*.json")):
        return
    Profile.capture(
        KeyboardState(),
        "Default",
        "A starting point: 1.50 mm, no rapid trigger, custom lighting.",
    ).save(directory)


def auto_backup(
    state: KeyboardState,
    directory: Path | None = None,
    *,
    description: str = "Automatic tuning snapshot (not a full backup)",
) -> Path | None:
    """Save a tuning snapshot.  This is deliberately not a full backup."""
    if not state.connected or not state.actuation:
        return None
    directory = directory or config.backups_dir()
    directory.mkdir(parents=True, exist_ok=True)
    stamp = f"{time.strftime('%Y%m%d-%H%M%S')}-{time.time_ns() % 1_000_000:06d}"
    profile = Profile.capture(
        state, f"backup-{stamp}", description, full=False,
    )
    path = profile.save(directory)
    backups = sorted(directory.glob("backup-*.json"))
    for old in backups[:-10]:
        try:
            old.unlink()
        except OSError:
            pass
    return path


def full_backup(
    device: MadlionsDevice, directory: Path | None = None,
    name: str | None = None,
) -> tuple[Profile, Path]:
    """Read every section from the device and save a restorable full backup."""
    directory = directory or config.backups_dir()
    directory.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    profile = Profile.capture_device(
        device,
        name or f"Full backup {stamp}",
        "Complete keyboard backup: tuning, colours, keymap, macros and advanced keys.",
        full=True,
    )
    path = profile.save(directory)
    return profile, path


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
    for preset in (rapid, balanced, typing):
        preset.captured_sections = _sections_of(preset)
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
    if profile.is_full:
        pieces.append("full backup")
    return " · ".join(pieces)


def section_summary(profile: Profile) -> str:
    labels = {
        "actuation": "actuation",
        "rapid_trigger": "rapid trigger",
        "lighting": "lighting",
        "per-key_colours": "per-key colours",
        "switches": "switches",
        "dead_band": "dead band",
        "game_mode": "game mode",
        "bottom_optimize": "bottom-out optimisation",
        "side_light": "side light",
        "keymap": "keymap",
        "macros": "macros",
        "advanced_keys": "advanced keys",
        "hold_click": "hold/click",
        "dks": "DKS",
    }
    sections = profile.captured_sections or _sections_of(profile)
    return ", ".join(labels.get(section, section) for section in sections)


def parse_key_list(text: str) -> list[tuple[int, int]]:
    out = []
    for token in text.split():
        try:
            out.append(_rc(token))
        except (ValueError, IndexError):
            continue
    return out


def apply_preview(profile: Profile) -> str:
    """A short, honest description of what applying this profile will write."""
    lines: list[str] = []
    override_count = len(profile.actuation_overrides)
    lines.append(
        f"Actuation: {profile.actuation_default:.2f} mm default"
        + (f" + {override_count} key override(s)" if override_count else "")
    )
    rt_overrides = len(profile.rt_overrides)
    lines.append(
        "Rapid trigger: "
        + ("on" if profile.rt_default.enabled else "off")
        + f" at {profile.rt_default.press_mm:.2f}/{profile.rt_default.release_mm:.2f} mm"
        + (f" + {rt_overrides} key override(s)" if rt_overrides else "")
    )
    if profile.light is not None:
        lines.append("Lighting effect and colour")
    if profile.colors:
        lines.append(f"Per-key colours: {len(profile.colors)} entries")
    if profile.features is not None:
        lines.append("Keyboard switches")
    if profile.dead_band is not None:
        lines.append("Dead band")
    if profile.game_mode is not None:
        lines.append("Game mode")
    if profile.bottom_optimize is not None:
        lines.append("Bottom-out optimisation")
    if profile.box_light is not None:
        lines.append("Side light (where supported)")
    if profile.keymap_hex:
        lines.append(
            f"KEYMAP: {len(bytes.fromhex(profile.keymap_hex))} bytes — persistent"
        )
    if profile.macros_hex:
        lines.append(
            f"MACROS: {len(bytes.fromhex(profile.macros_hex))} bytes — persistent"
        )
    if profile.advanced_keys is not None:
        lines.append(
            f"ADVANCED KEYS: {len(profile.advanced_keys)} slots — persistent"
        )
    if profile.tap_dance is not None:
        lines.append(f"HOLD/CLICK: {len(profile.tap_dance)} slots — persistent")
    if profile.dks is not None:
        lines.append(f"DKS: {len(profile.dks)} slots — persistent")
    return "\n".join(lines)
