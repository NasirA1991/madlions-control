"""A simulated MAD68 HE RGB for previews, screenshots and UI development."""

from __future__ import annotations

import math
import random
import time
from dataclasses import replace

from . import boards, keycodes, layout
from .device import (
    AdvancedKey,
    AdvancedMode,
    BoxLight,
    DeadBand,
    DeviceInfo,
    Dks,
    DksAction,
    Features,
    LightInfo,
    RapidTrigger,
    TapDance,
    clamp_travel,
)
from .lighting import RGB

_RANDOM = random.Random(68)


def _keycode_for_key(key: layout.KeySpec) -> int:
    label = key.label
    if label == "Esc":
        return 0x29
    if label == "Backspace":
        return 0x2A
    if label == "Tab":
        return 0x2B
    if label == "Caps":
        return 0x39
    if label == "Enter":
        return 0x28
    if label == "Space":
        return 0x2C
    if label in ("Shift",):
        return 0xE1 if key.col < 6 else 0xE5
    if label == "Ctrl":
        return 0xE0 if key.col < 6 else 0xE4
    if label == "Alt":
        return 0xE2 if key.col < 6 else 0xE6
    if label == "Win":
        return 0xE3
    if label == "Fn":
        return 0x5221
    if label in ("↑",):
        return 0x52
    if label in ("↓",):
        return 0x51
    if label in ("←",):
        return 0x50
    if label in ("→",):
        return 0x4F
    if len(label) == 1 and label.isalpha():
        return 0x04 + ord(label.upper()) - ord("A")
    if len(label) == 1 and label.isdigit():
        return 0x1E + "1234567890".index(label)
    mapping = {
        "-": 0x2D, "=": 0x2E, "[": 0x2F, "]": 0x30, "\\": 0x31,
        ";": 0x33, "'": 0x34, "`": 0x35, ",": 0x36, ".": 0x37, "/": 0x38,
        "Ins": 0x49, "Del": 0x4C, "PgUp": 0x4B, "PgDn": 0x4E,
        "End": 0x4D, "Menu": 0x65,
    }
    return mapping.get(label, 0)


def _default_keymap(board: boards.BoardSpec) -> bytes:
    data = bytearray(board.keymap_size)
    for key in layout.keys_for(board):
        code = _keycode_for_key(key)
        cell = ((0 * board.rows + key.row) * board.cols + key.col) * 2
        data[cell:cell + 2] = code.to_bytes(2, "big")
    return bytes(data)


def _default_colors(board: boards.BoardSpec) -> list[RGB]:
    keys = layout.keys_for(board)
    colors = [(8, 8, 12)] * board.total_keys
    for index, key in enumerate(keys):
        t = index / max(1, len(keys) - 1)
        colors[key.row * board.cols + key.col] = (
            round(255 * (0.85 - 0.55 * t)),
            round(70 + 80 * math.sin(t * math.pi)),
            round(110 + 110 * t),
        )
    return colors


class DemoBackend:
    """The subset of the device API the application uses."""

    is_demo = True

    def __init__(self) -> None:
        from dataclasses import replace as _replace
        self.board = _replace(boards.DEFAULT_BOARD, side_light=True)
        self.protocol_version = 9
        self._info = DeviceInfo(
            board=self.board,
            title="MAD68 HE RGB",
            product_name="MAD68",
            serial="MAD HE",
            usb_id="373B:1058",
            hidraw="demo0",
            interface="1.1",
            protocol_version=9,
            firmware_verified=True,
            writable=True,
        )
        self._actuation = [1.50] * self.board.total_keys
        self._rt = [RapidTrigger(False, 0.50, 0.50) for _ in range(self.board.total_keys)]
        # A deliberately varied demo: a fast WASD cluster and a lighter
        # QERF ring make the heat maps and test page look like a real setup.
        for key in layout.keys_for(self.board):
            index = key.row * self.board.cols + key.col
            if key.label in ("W", "A", "S", "D"):
                self._actuation[index] = 0.75
                self._rt[index] = RapidTrigger(True, 0.10, 0.10)
            elif key.label in ("Q", "E", "R", "F"):
                self._actuation[index] = 1.05
                self._rt[index] = RapidTrigger(True, 0.20, 0.20)
            elif key.label in ("Shift", "Ctrl", "Alt", "Win"):
                self._actuation[index] = 1.80
            elif key.label in ("↑", "↓", "←", "→"):
                self._actuation[index] = 1.20
        self._rt[4 * self.board.cols + 6] = RapidTrigger(True, 0.15, 0.15)
        self._light = LightInfo(effect=6, speed=128, r=255, g=77, b=109, brightness=170)
        self._colors = _default_colors(self.board)
        self._features = Features(nkro=1)
        self._dead_band = DeadBand(0.05, 0.05)
        self._game_mode = 1
        self._bottom_optimize = 1
        self._box_light = BoxLight(2, 1, 130, 120)
        self._keymap = _default_keymap(self.board)
        self._colors_layer = True
        self._advanced = [AdvancedKey(index=i) for i in range(16)]
        self._taps = [TapDance(index=i) for i in range(8)]
        self._dks = [Dks(index=i) for i in range(8)]
        self._macros = bytes(512)
        self._started = time.monotonic()
        self._populated = self._build_populated()
        # A handful of keys animate so screenshots and the test page feel alive.
        self._wave_keys = [(2, 1), (2, 2), (2, 3), (2, 4), (3, 2), (3, 3),
                           (3, 4), (3, 5), (4, 6), (1, 1), (1, 2), (1, 3)]

    def _build_populated(self) -> list[bool]:
        mask = [False] * self.board.total_keys
        for key in layout.keys_for(self.board):
            mask[key.row * self.board.cols + key.col] = True
        return mask

    # -- identity ---------------------------------------------------------
    def device_info(self) -> DeviceInfo:
        return self._info

    def populated_mask(self) -> list[bool]:
        return list(self._populated)

    def read_protocol_version(self) -> int | None:
        return 9

    def read_layer_count(self) -> int:
        return 4

    def read_macro_count(self) -> int:
        return 16

    def read_macro_buffer_size(self) -> int:
        return len(self._macros)

    def read_firmware_value(self) -> bytes:
        return b"\x00\x09"

    def read_calibration_status(self) -> list[int]:
        return [1 if value else 0 for value in self._populated]

    # -- per-key ----------------------------------------------------------
    def read_actuation(self) -> list[float]:
        return list(self._actuation)

    def read_rapid_trigger(self) -> list[RapidTrigger]:
        return list(self._rt)

    def write_actuation(self, values, offset=0, *, flash=0):
        for index, value in enumerate(values):
            if offset + index < len(self._actuation):
                self._actuation[offset + index] = clamp_travel(value)
        self._colors_layer = True

    def write_rapid_trigger(self, values, offset=0, *, flash=0):
        for index, value in enumerate(values):
            if offset + index < len(self._rt):
                self._rt[offset + index] = value

    def write_one_actuation(self, row, col, mm):
        self._actuation[row * self.board.cols + col] = clamp_travel(mm)

    def write_one_rapid_trigger(self, row, col, rt):
        self._rt[row * self.board.cols + col] = rt

    # -- lighting ---------------------------------------------------------
    def read_light(self) -> LightInfo:
        return self._light

    def write_light(self, light):
        self._light = replace(light, brightness=min(light.brightness, 210))

    def read_all_key_colors(self) -> list[RGB]:
        return list(self._colors)

    def read_key_colors(self, row=0, col=0, count=None) -> list[RGB]:
        start = row * self.board.cols + col
        count = 9 if count is None else count
        return self._colors[start:start + count]

    def write_key_colors(self, row, col, colors):
        start = row * self.board.cols + col
        for index, color in enumerate(colors):
            if start + index < len(self._colors):
                self._colors[start + index] = tuple(int(c) for c in color)  # type: ignore[assignment]

    def write_all_key_colors(self, colors):
        for index, color in enumerate(colors[:self.board.total_keys]):
            self._colors[index] = tuple(int(c) for c in color)  # type: ignore[assignment]

    def save_lighting(self):
        pass

    def read_box_light(self) -> BoxLight:
        return self._box_light

    def write_box_light(self, box):
        self._box_light = box

    # -- global -----------------------------------------------------------
    def read_features(self) -> Features:
        return self._features

    def write_features(self, features):
        self._features = features

    def read_dead_band(self) -> DeadBand:
        return self._dead_band

    def write_dead_band(self, band):
        self._dead_band = band

    def read_game_mode(self) -> int:
        return self._game_mode

    def write_game_mode(self, mode):
        self._game_mode = mode

    def read_bottom_optimize(self) -> int:
        return self._bottom_optimize

    def write_bottom_optimize(self, value):
        self._bottom_optimize = value

    # -- keymap / macros ---------------------------------------------------
    def read_keymap(self) -> bytes:
        return self._keymap

    def read_keycode(self, layer, row, col) -> int:
        offset = ((layer * self.board.rows + row) * self.board.cols + col) * 2
        return int.from_bytes(self._keymap[offset:offset + 2], "big")

    def write_keycode(self, layer, row, col, keycode):
        offset = ((layer * self.board.rows + row) * self.board.cols + col) * 2
        data = bytearray(self._keymap)
        data[offset:offset + 2] = keycode.to_bytes(2, "big")
        self._keymap = bytes(data)

    def write_buffer(self, cmd, data):
        if cmd == 0x13:
            self._keymap = bytes(data[:self.board.keymap_size])

    def read_macros(self) -> bytes:
        return self._macros

    def write_macros(self, data):
        self._macros = bytes(data)

    # -- advanced ----------------------------------------------------------
    def read_advanced_key(self, index):
        return self._advanced[index]

    def write_advanced_key(self, key):
        self._advanced[key.index] = key

    def read_dks(self, index):
        return self._dks[index]

    def write_dks(self, dks):
        self._dks[dks.index] = dks

    def read_tap_dance(self, index):
        return self._taps[index]

    def write_tap_dance(self, tap):
        self._taps[tap.index] = tap

    # -- telemetry ---------------------------------------------------------
    def _phase(self) -> float:
        return time.monotonic() - self._started

    def read_travel(self) -> list[float]:
        t = self._phase()
        values = [0.0] * self.board.total_keys
        for index, (row, col) in enumerate(self._wave_keys):
            press = 0.5 + 0.5 * math.sin(t * 2.2 + index * 0.7)
            depth = press ** 3 * 3.1
            if press < 0.1:
                depth = 0.0
            values[row * self.board.cols + col] = round(depth, 2)
        # A soft random key press makes the live view less mechanical.
        tick = int(t * 1.7)
        rng = random.Random(tick)
        row, col = rng.choice(self._wave_keys)
        values[row * self.board.cols + col] = round(min(3.2, values[row * self.board.cols + col] + 1.1), 2)
        return values

    def read_adc(self) -> list[int]:
        travel = self.read_travel()
        return [int(3000 - value * 700) for value in travel]

    def read_one_travel(self, row, col) -> float:
        return self.read_travel()[row * self.board.cols + col]

    def read_one_adc(self, row, col) -> int:
        return self.read_adc()[row * self.board.cols + col]

    # -- persistence / diagnostics ----------------------------------------
    def commit(self):
        pass

    def read_report(self) -> dict:
        return {
            "board": self.board.name,
            "usb_id": "373B:1058",
            "product_name": "MAD68",
            "hidraw": "demo0",
            "protocol_version": 9,
            "writable": True,
            "demo": True,
        }

    def close(self):
        pass
