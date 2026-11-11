"""The keyboard state model shared between the worker and the UI."""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from . import boards, keycodes
from .device import (
    AdvancedKey,
    BoxLight,
    DeadBand,
    DeviceInfo,
    Features,
    LightInfo,
    MadlionsDevice,
    RapidTrigger,
    TapDance,
    Dks,
)
from .lighting import RGB

RGBList = list[tuple[int, int, int]]


def default_actuation(board: boards.BoardSpec) -> list[float]:
    return [1.50] * board.total_keys


@dataclass
class KeyboardState:
    info: DeviceInfo | None = None
    connected: bool = False
    loading: bool = False
    error: str = ""
    permission_error: bool = False
    warnings: list[str] = field(default_factory=list)

    actuation: list[float] = field(default_factory=list)
    rapid_trigger: list[RapidTrigger] = field(default_factory=list)
    light: LightInfo = field(default_factory=LightInfo)
    colors: list[RGB] = field(default_factory=list)
    features: Features = field(default_factory=Features)
    dead_band: DeadBand = field(default_factory=DeadBand)
    game_mode: int = 0
    bottom_optimize: int = 0
    box_light: BoxLight = field(default_factory=BoxLight)
    calibration: list[bool] = field(default_factory=list)
    layers: int = 4
    keymap: bytes | None = None
    macros: bytes | None = None
    macro_count: int = 0
    macro_size: int = 0
    advanced_keys: list[AdvancedKey] | None = None
    tap_dance: list[TapDance] | None = None
    dks: list[Dks] | None = None
    firmware_value: bytes = b""

    @property
    def board(self) -> boards.BoardSpec:
        return self.info.board if self.info else boards.DEFAULT_BOARD

    @property
    def total_keys(self) -> int:
        return self.board.total_keys

    @property
    def writable(self) -> bool:
        return bool(self.info and self.info.writable)

    @property
    def title(self) -> str:
        return self.info.title if self.info else "No keyboard"

    def filled(self) -> bool:
        return bool(self.actuation and len(self.actuation) == self.total_keys)

    def actuation_of(self, row: int, col: int) -> float:
        index = row * self.board.cols + col
        if 0 <= index < len(self.actuation):
            return self.actuation[index]
        return 1.50

    def rt_of(self, row: int, col: int) -> RapidTrigger:
        index = row * self.board.cols + col
        if 0 <= index < len(self.rapid_trigger):
            return self.rapid_trigger[index]
        return RapidTrigger()

    def layer_keycodes(self, layer: int) -> list[list[int]]:
        rows = self.board.rows
        cols = self.board.cols
        out = [[0] * cols for _ in range(rows)]
        if not self.keymap:
            return out
        for r in range(rows):
            for c in range(cols):
                offset = ((layer * rows + r) * cols + c) * 2
                out[r][c] = int.from_bytes(self.keymap[offset:offset + 2], "big")
        return out

    def keycode_at(self, layer: int, row: int, col: int) -> int:
        if not self.keymap:
            return 0
        offset = ((layer * self.board.rows + row) * self.board.cols + col) * 2
        return int.from_bytes(self.keymap[offset:offset + 2], "big")

    def with_keycode(self, layer: int, row: int, col: int, keycode: int) -> "KeyboardState":
        if not self.keymap:
            return self
        offset = ((layer * self.board.rows + row) * self.board.cols + col) * 2
        data = bytearray(self.keymap)
        data[offset:offset + 2] = keycode.to_bytes(2, "big")
        return replace(self, keymap=bytes(data))

    def with_actuation(self, changes: dict[tuple[int, int], float]) -> "KeyboardState":
        values = list(self.actuation)
        for (row, col), mm in changes.items():
            index = row * self.board.cols + col
            if 0 <= index < len(values):
                values[index] = round(mm, 2)
        return replace(self, actuation=values)

    def with_rt(self, changes: dict[tuple[int, int], RapidTrigger]) -> "KeyboardState":
        values = list(self.rapid_trigger)
        for (row, col), rt in changes.items():
            index = row * self.board.cols + col
            if 0 <= index < len(values):
                values[index] = rt
        return replace(self, rapid_trigger=values)

    def clone(self) -> "KeyboardState":
        return replace(
            self,
            actuation=list(self.actuation),
            rapid_trigger=list(self.rapid_trigger),
            colors=list(self.colors),
            calibration=list(self.calibration),
            warnings=list(self.warnings),
            advanced_keys=list(self.advanced_keys) if self.advanced_keys is not None else None,
            tap_dance=list(self.tap_dance) if self.tap_dance is not None else None,
            dks=list(self.dks) if self.dks is not None else None,
        )


def load_basic(device: MadlionsDevice, *, include_light: bool = True) -> KeyboardState:
    """Read everything the main pages need.  Optional sections degrade gracefully."""
    info = device.device_info()
    board = info.board
    state = KeyboardState(info=info, connected=True, layers=board.layers)
    state.calibration = device.populated_mask()
    state.actuation = device.read_actuation()
    state.rapid_trigger = device.read_rapid_trigger()
    try:
        state.layers = device.read_layer_count() or board.layers
    except Exception as exc:  # noqa: BLE001 - optional metadata
        state.warnings.append(f"layer count: {exc}")
        state.layers = board.layers
    if include_light:
        for name, reader in (
            ("light", device.read_light),
            ("features", device.read_features),
            ("dead band", device.read_dead_band),
            ("game mode", device.read_game_mode),
            ("bottom-out optimisation", device.read_bottom_optimize),
            ("side light", device.read_box_light),
        ):
            try:
                value = reader()
            except Exception as exc:  # noqa: BLE001 - optional section
                state.warnings.append(f"{name}: {exc}")
                continue
            if name == "light":
                state.light = value  # type: ignore[assignment]
            elif name == "features":
                state.features = value  # type: ignore[assignment]
            elif name == "dead band":
                state.dead_band = value  # type: ignore[assignment]
            elif name == "game mode":
                state.game_mode = int(value)  # type: ignore[arg-type]
            elif name == "bottom-out optimisation":
                state.bottom_optimize = int(value)  # type: ignore[arg-type]
            elif name == "side light":
                state.box_light = value  # type: ignore[assignment]
    try:
        state.firmware_value = device.read_firmware_value()
    except Exception:
        pass
    return state


def load_colors(
    device: MadlionsDevice, state: KeyboardState, *, strict: bool = False
) -> KeyboardState:
    try:
        return replace(state, colors=device.read_all_key_colors())
    except Exception as exc:  # noqa: BLE001
        if strict:
            raise
        return replace(state, warnings=state.warnings + [f"per-key colours: {exc}"])


def load_keymap(device: MadlionsDevice, state: KeyboardState) -> KeyboardState:
    keymap = device.read_keymap()
    return replace(state, keymap=keymap)


def load_macros(device: MadlionsDevice, state: KeyboardState) -> KeyboardState:
    count = device.read_macro_count()
    size = device.read_macro_buffer_size()
    macros = device.read_macros()
    return replace(state, macro_count=count, macro_size=size, macros=macros)


def load_advanced(device: MadlionsDevice, state: KeyboardState) -> KeyboardState:
    keys = [device.read_advanced_key(index) for index in range(16)]
    taps = [device.read_tap_dance(index) for index in range(8)]
    dks = [device.read_dks(index) for index in range(8)]
    return replace(state, advanced_keys=keys, tap_dance=taps, dks=dks)


def layer_summary(state: KeyboardState, layer: int) -> dict[str, int]:
    """Small counts for the keymap page header."""
    codes = [code for row in state.layer_keycodes(layer) for code in row]
    return {
        "total": len(codes),
        "custom": sum(1 for code in codes if code not in (0,)),
        "layers": len({code & 0x529F for code in codes if 0x5200 <= code <= 0x529F}),
    }


def key_label(state: KeyboardState, layer: int, row: int, col: int) -> str:
    return keycodes.label(state.keycode_at(layer, row, col))
