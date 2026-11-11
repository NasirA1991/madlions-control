"""High-level access to a MADLIONS magnetic-switch keyboard.

Every write goes through :meth:`MadlionsDevice._guard`, so a read-only session
or a board whose firmware has not been verified cannot be written to by
accident.  The packet layouts are documented in ``docs/PROTOCOL.md``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, replace
from enum import IntEnum
from typing import Callable, Iterator

from . import boards, layout
from .config import VID
from .transport import (
    REPORT_SIZE,
    DeviceError,
    DeviceNotFound,
    HidInfo,
    HidrawTransport,
    PermissionDenied,
    ProtocolError,
    UnsupportedDevice,
    discover,
    find_supported,
)

# --- VIA command IDs --------------------------------------------------------
CMD_GET_PROTOCOL_VERSION = 0x01
CMD_GET_KEYBOARD_VALUE = 0x02
CMD_SET_KEYBOARD_VALUE = 0x03
CMD_DYNAMIC_KEYMAP_GET_KEYCODE = 0x04
CMD_DYNAMIC_KEYMAP_SET_KEYCODE = 0x05
CMD_DYNAMIC_KEYMAP_GET_LAYER_COUNT = 0x11
CMD_DYNAMIC_KEYMAP_GET_BUFFER = 0x12
CMD_DYNAMIC_KEYMAP_SET_BUFFER = 0x13
CMD_MACRO_GET_COUNT = 0x0C
CMD_MACRO_GET_BUFFER_SIZE = 0x0D
CMD_MACRO_GET_BUFFER = 0x0E
CMD_MACRO_SET_BUFFER = 0x0F
CMD_CUSTOM_SET_VALUE = 0x07
CMD_CUSTOM_GET_VALUE = 0x08
CMD_VIAL_PREFIX = 0xFE

CUSTOM_CHANNEL = 0x96

# --- vendor sub-commands ----------------------------------------------------
V_TAP_DANCE_GET = 0x01
V_TAP_DANCE_SET = 0x02
V_ONE_ACTUATION = 0x03
V_ONE_RT = 0x07
V_DEAD_BAND = 0x0B
V_BULK_ACTUATION = 0x0D
V_BULK_RT = 0x0E
V_DKS = 0x0F
V_FEATURE = 0x11
V_SAVE_LAMPLIGHT = 0x12
V_DATA_REPORTING = 0x14
V_ADC_SINGLE = 0x09
V_TRIP_SINGLE = 0x0A
V_ADC_BUFFER = 0x16
V_TRIP_BUFFER = 0x17
V_GAME_MODE = 0x1E
V_BOTTOM_OPTIMIZE = 0x1D
V_CALIBRATION_STATUS = 0x1F
V_ADVANCED_KEY = 0x20
V_BOX_LIGHT = 0x21
V_LIGHT_INFO = 0x41
V_SET_KEY_COLOR = 0x42
V_GET_KEY_COLOR = 0x45

SUB_GET = 0x01
SUB_SET = 0x03

FLASH_NORMAL = 0x00
FLASH_ERASE_AND_WRITE = 0x03


def _require_len(reply: bytes, minimum: int, what: str) -> None:
    if len(reply) < minimum:
        raise ProtocolError(
            f"{what} returned a short reply ({len(reply)} bytes, expected at least {minimum})"
        )

REPORT = REPORT_SIZE
KEYCODE_SIZE = 2
MAX_BUFFER_CHUNK = REPORT - 1 - 3
MAX_ACTUATION_READ = (REPORT - 8) // 2       # 12
MAX_ACTUATION_WRITE = (REPORT - 9) // 2      # 11
MAX_RT_READ = (REPORT - 8) // 5              # 4
MAX_RT_WRITE = (REPORT - 9) // 5             # 4
MAX_TELEMETRY_READ = (REPORT - 8) // 2       # 12
MAX_COLORS = (REPORT - 5) // 3               # 9
BRIGHTNESS_MAX = 210
TRAVEL_MIN_MM = 0.05
TRAVEL_MAX_MM = 3.40
DEFAULT_ACTUATION_MM = 1.50
DEFAULT_RT_MM = 0.50


class WriteBlocked(DeviceError):
    """A mutating operation was attempted on a protected session."""


class AdvancedMode(IntEnum):
    NONE = 0x00
    RS = 0x01
    SOCD = 0x02
    SOCD_KEY1 = 0x03
    SOCD_KEY2 = 0x04
    SOCD_BALANCE = 0x05
    OKS = 0x06


@dataclass(frozen=True)
class RapidTrigger:
    enabled: bool = False
    press_mm: float = DEFAULT_RT_MM
    release_mm: float = DEFAULT_RT_MM

    def to_json(self) -> dict:
        return {
            "enabled": self.enabled,
            "press_mm": round(self.press_mm, 2),
            "release_mm": round(self.release_mm, 2),
        }


@dataclass(frozen=True)
class LightInfo:
    effect: int = 0
    speed: int = 0
    r: int = 0
    g: int = 0
    b: int = 0
    brightness: int = 0

    @property
    def hex(self) -> str:
        return f"#{self.r:02x}{self.g:02x}{self.b:02x}"

    @property
    def rgb(self) -> tuple[int, int, int]:
        return self.r, self.g, self.b

    def to_json(self) -> dict:
        return {
            "effect": self.effect,
            "speed": self.speed,
            "r": self.r,
            "g": self.g,
            "b": self.b,
            "brightness": self.brightness,
        }


@dataclass(frozen=True)
class Features:
    rgb_area: int = 0
    wasd_swap: int = 0
    mac_mode: int = 0
    win_lock: int = 0
    nkro: int = 1

    def to_json(self) -> dict:
        return {
            "rgb_area": self.rgb_area,
            "wasd_swap": self.wasd_swap,
            "mac_mode": self.mac_mode,
            "win_lock": self.win_lock,
            "nkro": self.nkro,
        }


@dataclass(frozen=True)
class DeadBand:
    top_mm: float = 0.0
    bottom_mm: float = 0.0

    def to_json(self) -> dict:
        return {"top_mm": round(self.top_mm, 2), "bottom_mm": round(self.bottom_mm, 2)}


@dataclass(frozen=True)
class BoxLight:
    mode: int = 0
    colorful: int = 0
    brightness: int = 0
    speed: int = 0


@dataclass(frozen=True)
class AdvancedKey:
    index: int
    mode: AdvancedMode = AdvancedMode.NONE
    key_id: int = 0
    rs_apc_lv: int = 0
    gapc_sw: int = 0
    rt_sw: int = 0
    key1_row: int = 0
    key1_col: int = 0
    key2_row: int = 0
    key2_col: int = 0
    layer: int = 0

    @property
    def active(self) -> bool:
        return self.mode != AdvancedMode.NONE

    def to_json(self) -> dict:
        return {
            "index": self.index,
            "mode": self.mode.name,
            "key_id": self.key_id,
            "rs_apc_lv": self.rs_apc_lv,
            "gapc_sw": self.gapc_sw,
            "rt_sw": self.rt_sw,
            "key1": [self.key1_row, self.key1_col],
            "key2": [self.key2_row, self.key2_col],
            "layer": self.layer,
        }


@dataclass(frozen=True)
class DksAction:
    status: int = 0
    keycode: int = 0

    def to_bytes(self) -> bytes:
        return self.status.to_bytes(2, "big") + self.keycode.to_bytes(2, "big")

    @classmethod
    def from_bytes(cls, data: bytes) -> "DksAction":
        return cls(int.from_bytes(data[0:2], "big"), int.from_bytes(data[2:4], "big"))


@dataclass(frozen=True)
class Dks:
    index: int
    actions: tuple[DksAction, DksAction, DksAction, DksAction] = field(
        default_factory=lambda: (DksAction(), DksAction(), DksAction(), DksAction())
    )

    def to_bytes(self) -> bytes:
        return b"".join(action.to_bytes() for action in self.actions)


@dataclass(frozen=True)
class TapDance:
    index: int
    tap: int = 0
    hold: int = 0
    timer_ms: int = 200

    @property
    def active(self) -> bool:
        return bool(self.tap or self.hold)


@dataclass(frozen=True)
class DeviceInfo:
    board: boards.BoardSpec
    title: str
    product_name: str
    serial: str
    usb_id: str
    hidraw: str
    interface: str
    protocol_version: int | None
    firmware_verified: bool
    writable: bool
    read_only_reason: str = ""

    @property
    def protocol_label(self) -> str:
        return "unknown" if self.protocol_version is None else str(self.protocol_version)


def travel_to_raw(mm: float) -> int:
    return max(0, min(0xFFFF, round(mm / 0.01)))


def travel_from_raw(raw: int) -> float:
    return round(raw * 0.01, 2)


def clamp_travel(mm: float) -> float:
    return max(TRAVEL_MIN_MM, min(TRAVEL_MAX_MM, round(mm, 2)))


def _travel_bytes(mm: float) -> bytes:
    return travel_to_raw(mm).to_bytes(2, "big")


def build_report(cmd: int, payload: bytes = b"") -> bytes:
    if len(payload) > REPORT - 1:
        raise ValueError("payload too large for one report")
    return bytes([cmd]) + payload + bytes(REPORT - 1 - len(payload))


def _strip_id(raw: bytes) -> bytes:
    """Normalise a reply that may include a leading report-ID byte."""
    if len(raw) > REPORT and raw[0] == 0:
        return raw[1:1 + REPORT]
    return raw[:REPORT]


class MadlionsDevice:
    """A connected keyboard session.  Not thread-safe; one owner at a time."""

    def __init__(
        self,
        info: HidInfo,
        transport: HidrawTransport,
        *,
        read_only: bool = False,
        allow_unverified: bool = False,
    ) -> None:
        self.info = info
        self.transport = transport
        self.read_only = read_only
        self.allow_unverified = allow_unverified
        self.protocol_version: int | None = None
        self.board = info.board
        self._firmware_verified = False
        self._writable = False
        self._read_only_reason = ""

    # -- lifecycle -------------------------------------------------------
    @classmethod
    def open(
        cls,
        info: HidInfo | None = None,
        *,
        read_only: bool = False,
        allow_unverified: bool = False,
        debug: bool = False,
    ) -> "MadlionsDevice":
        if info is None:
            info = find_supported()
        if not info.supported:
            raise UnsupportedDevice(info.reason or "this HID collection is unsupported")
        transport = HidrawTransport(info, debug=debug)
        transport.open()
        device = cls(info, transport, read_only=read_only, allow_unverified=allow_unverified)
        try:
            device._probe()
        except Exception:
            transport.close()
            raise
        return device

    def close(self) -> None:
        self.transport.close()

    def __enter__(self) -> "MadlionsDevice":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    def _probe(self) -> None:
        try:
            reply = self._ask(
                build_report(CMD_GET_PROTOCOL_VERSION),
                0x01,
                attempts=2,
            )
            if len(reply) >= 3:
                self.protocol_version = int.from_bytes(reply[1:3], "big")
            else:
                self.protocol_version = reply[1] if len(reply) > 1 else None
        except ProtocolError:
            self.protocol_version = None
        self._firmware_verified = self.protocol_version == boards.KNOWN_PROTOCOL_VERSION
        reasons: list[str] = []
        if not self.read_only and not self.info.board.verified and not self.allow_unverified:
            reasons.append(
                f"{self.info.board.name} has not been verified with this application"
            )
        if not self.read_only and not self._firmware_verified:
            got = "no answer" if self.protocol_version is None else str(self.protocol_version)
            reasons.append(
                f"firmware protocol {got} is not the verified version "
                f"{boards.KNOWN_PROTOCOL_VERSION}"
            )
        if self.read_only:
            reasons.append("the session was opened read-only")
        self._writable = not reasons
        self._read_only_reason = "; ".join(reasons)

    # -- guard -----------------------------------------------------------
    @property
    def writable(self) -> bool:
        return self._writable

    def _guard(self, what: str) -> None:
        if not self._writable:
            raise WriteBlocked(
                f"{what} was refused: {self._read_only_reason or 'the session is read-only'}. "
                f"Reading is always available."
            )

    # -- request plumbing -------------------------------------------------
    def _ask(
        self,
        report: bytes,
        cmd: int,
        vendor: bytes | None = None,
        *,
        timeout: float | None = None,
        attempts: int = 1,
        drain: bool = True,
    ) -> bytes:
        def matches(raw: bytes) -> bool:
            data = _strip_id(raw)
            if not data or data[0] != cmd:
                return False
            if vendor is None:
                return True
            return data[1:1 + len(vendor)] == vendor

        raw = self.transport.request(
            report, match=matches, timeout=timeout, attempts=attempts, drain=drain
        )
        return _strip_id(raw)

    def _ask_vendor(
        self,
        cmd: int,
        sub: int,
        payload: bytes = b"",
        *,
        timeout: float | None = None,
        attempts: int = 1,
    ) -> bytes:
        return self._ask(
            build_report(cmd, bytes([CUSTOM_CHANNEL, sub]) + payload),
            cmd,
            bytes([CUSTOM_CHANNEL, sub]),
            timeout=timeout,
            attempts=attempts,
        )

    def _ask_custom(self, cmd: int, sub: int, payload: bytes = b"") -> bytes:
        return self._ask(
            build_report(cmd, bytes([sub]) + payload),
            cmd,
            bytes([sub]),
        )

    def _bulk_request(self, sub: int, offset: int, count: int) -> bytes:
        payload = bytearray(REPORT - 1)
        payload[0] = CUSTOM_CHANNEL
        payload[1] = sub
        payload[4] = (offset >> 8) & 0xFF
        payload[5] = offset & 0xFF
        payload[6] = count & 0xFF
        return build_report(CMD_GET_KEYBOARD_VALUE, bytes(payload))

    def _bulk_reply_data(
        self, reply: bytes, offset: int, count: int, entry_size: int, what: str
    ) -> bytes:
        """Validate a bulk reply's header and exact payload length."""
        if len(reply) < 8:
            raise ProtocolError(f"{what} returned a short reply")
        echoed_offset = int.from_bytes(reply[5:7], "big")
        echoed_count = reply[7]
        if echoed_offset != offset or echoed_count != count:
            raise ProtocolError(
                f"{what} replied for offset {echoed_offset}, count {echoed_count}; "
                f"expected offset {offset}, count {count}"
            )
        span = count * entry_size
        data = reply[8:8 + span]
        if len(data) != span:
            raise ProtocolError(
                f"{what} returned {len(data)} payload bytes, expected {span}"
            )
        return data

    def read_buffer(self, cmd: int, size: int, base: int = 0) -> bytes:
        data = bytearray()
        while len(data) < size:
            want = min(MAX_BUFFER_CHUNK, size - len(data))
            offset = base + len(data)
            report = build_report(
                cmd,
                offset.to_bytes(2, "big") + bytes([want]),
            )
            reply = self._ask(report, cmd)
            if len(reply) < 4:
                raise ProtocolError(f"{cmd:#04x} returned a short buffer reply")
            echoed_offset = int.from_bytes(reply[1:3], "big")
            chunk_size = reply[3]
            if echoed_offset != offset:
                raise ProtocolError(
                    f"{cmd:#04x} replied for offset {echoed_offset:#06x}, "
                    f"expected {offset:#06x}"
                )
            if chunk_size == 0 or len(reply) < 4 + chunk_size:
                raise ProtocolError(
                    f"{cmd:#04x} returned no usable data at {offset:#06x}"
                )
            chunk = reply[4:4 + chunk_size]
            if len(chunk) < want:
                raise ProtocolError(
                    f"{cmd:#04x} returned {len(chunk)} bytes at {offset:#06x}, "
                    f"expected {want}"
                )
            data += chunk[:want]
        return bytes(data[:size])

    def write_buffer(self, cmd: int, data: bytes, base: int = 0) -> None:
        self._guard("writing an onboard buffer")
        for offset in range(0, len(data), MAX_BUFFER_CHUNK):
            chunk = data[offset:offset + MAX_BUFFER_CHUNK]
            report = build_report(
                cmd,
                (base + offset).to_bytes(2, "big") + bytes([len(chunk)]) + chunk,
            )
            self._ask(report, cmd)

    # -- identity ---------------------------------------------------------
    def read_layer_count(self) -> int:
        reply = self._ask(build_report(CMD_DYNAMIC_KEYMAP_GET_LAYER_COUNT), 0x11)
        _require_len(reply, 2, "layer count")
        return reply[1]

    def read_protocol_version(self) -> int | None:
        return self.protocol_version

    def read_firmware_value(self) -> bytes:
        try:
            reply = self._ask(build_report(CMD_GET_KEYBOARD_VALUE, bytes([0x04])), 0x02)
            return reply[1:]
        except ProtocolError:
            return b""

    def read_macro_count(self) -> int:
        reply = self._ask(build_report(CMD_MACRO_GET_COUNT), 0x0C)
        _require_len(reply, 2, "macro count")
        return reply[1]

    def read_macro_buffer_size(self) -> int:
        reply = self._ask(build_report(CMD_MACRO_GET_BUFFER_SIZE), 0x0D)
        _require_len(reply, 3, "macro buffer size")
        return int.from_bytes(reply[1:3], "big")

    def read_calibration_status(self, count: int | None = None) -> list[int]:
        total = self.board.total_keys if count is None else count
        out: list[int] = []
        per_packet = REPORT - 8
        while len(out) < total:
            want = min(per_packet, total - len(out))
            reply = self._ask(
                self._bulk_request(V_CALIBRATION_STATUS, len(out), want),
                CMD_GET_KEYBOARD_VALUE,
                bytes([CUSTOM_CHANNEL, V_CALIBRATION_STATUS]),
            )
            out.extend(self._bulk_reply_data(
                reply, len(out), want, 1, "calibration status"
            ))
        return out[:total]

    def populated_mask(self) -> list[bool]:
        """Cells that physically exist on this board.

        Firmware returns an all-zero calibration mask on some healthy boards;
        that must not be mistaken for "all 75 matrix cells exist".  Fall back
        to the known physical layout instead, and keep all-True only for an
        unknown grid.
        """
        try:
            flags = self.read_calibration_status()
            if any(flags):
                return [bool(value) for value in flags]
        except ProtocolError:
            pass
        mask = [False] * self.board.total_keys
        for key in layout.keys_for(self.board):
            index = key.row * self.board.cols + key.col
            if 0 <= index < len(mask):
                mask[index] = True
        return mask or [True] * self.board.total_keys

    # -- actuation / rapid trigger ---------------------------------------
    def read_actuation(self) -> list[float]:
        values: list[float] = []
        total = self.board.total_keys
        while len(values) < total:
            want = min(MAX_ACTUATION_READ, total - len(values))
            reply = self._ask(
                self._bulk_request(V_BULK_ACTUATION, len(values), want),
                CMD_GET_KEYBOARD_VALUE,
                bytes([CUSTOM_CHANNEL, V_BULK_ACTUATION]),
            )
            data = self._bulk_reply_data(
                reply, len(values), want, 2, "actuation"
            )
            values.extend(travel_from_raw(int.from_bytes(data[i:i + 2], "big"))
                          for i in range(0, len(data), 2))
        return values[:total]

    def read_rapid_trigger(self) -> list[RapidTrigger]:
        total = self.board.total_keys
        values: list[RapidTrigger] = []
        while len(values) < total:
            want = min(MAX_RT_READ, total - len(values))
            reply = self._ask(
                self._bulk_request(V_BULK_RT, len(values), want),
                CMD_GET_KEYBOARD_VALUE,
                bytes([CUSTOM_CHANNEL, V_BULK_RT]),
            )
            data = self._bulk_reply_data(
                reply, len(values), want, 5, "rapid trigger"
            )
            for i in range(0, len(data), 5):
                values.append(
                    RapidTrigger(
                        enabled=bool(data[i]),
                        release_mm=travel_from_raw(int.from_bytes(data[i + 1:i + 3], "big")),
                        press_mm=travel_from_raw(int.from_bytes(data[i + 3:i + 5], "big")),
                    )
                )
        return values[:total]

    def _bulk_write(self, sub: int, offset: int, count: int, data: bytes, flash: int) -> None:
        payload = bytearray(REPORT - 1)
        payload[0] = CUSTOM_CHANNEL
        payload[1] = sub
        payload[4] = (offset >> 8) & 0xFF
        payload[5] = offset & 0xFF
        payload[6] = count & 0xFF
        payload[7] = flash
        payload[8:8 + len(data)] = data
        self._ask(
            build_report(CMD_SET_KEYBOARD_VALUE, bytes(payload)),
            CMD_SET_KEYBOARD_VALUE,
            bytes([CUSTOM_CHANNEL, sub]),
        )

    def write_actuation(
        self, values: list[float], offset: int = 0, *, flash: int = FLASH_NORMAL
    ) -> None:
        self._guard("changing the actuation point")
        values = [clamp_travel(value) for value in values]
        index = 0
        while index < len(values):
            chunk = values[index:index + MAX_ACTUATION_WRITE]
            data = b"".join(_travel_bytes(value) for value in chunk)
            self._bulk_write(V_BULK_ACTUATION, offset + index, len(chunk), data, flash)
            index += len(chunk)

    def write_rapid_trigger(
        self, values: list[RapidTrigger], offset: int = 0, *, flash: int = FLASH_NORMAL
    ) -> None:
        self._guard("changing rapid trigger")
        index = 0
        while index < len(values):
            chunk = values[index:index + MAX_RT_WRITE]
            data = bytearray()
            for rt in chunk:
                data.append(1 if rt.enabled else 0)
                data += _travel_bytes(clamp_travel(rt.release_mm))
                data += _travel_bytes(clamp_travel(rt.press_mm))
            self._bulk_write(V_BULK_RT, offset + index, len(chunk), bytes(data), flash)
            index += len(chunk)

    def write_one_actuation(self, row: int, col: int, mm: float) -> None:
        self._guard("changing one actuation point")
        self._ask_vendor(
            CMD_SET_KEYBOARD_VALUE, V_ONE_ACTUATION,
            bytes([row, col]) + _travel_bytes(clamp_travel(mm)),
        )

    def write_one_rapid_trigger(self, row: int, col: int, rt: RapidTrigger) -> None:
        self._guard("changing one rapid-trigger setting")
        self._ask_vendor(
            CMD_SET_KEYBOARD_VALUE, V_ONE_RT,
            bytes([row, col, 1 if rt.enabled else 0])
            + _travel_bytes(clamp_travel(rt.release_mm))
            + _travel_bytes(clamp_travel(rt.press_mm)),
        )

    # -- lighting ---------------------------------------------------------
    def read_light(self) -> LightInfo:
        reply = self._ask_custom(CMD_CUSTOM_GET_VALUE, V_LIGHT_INFO)
        if len(reply) < 9:
            raise ProtocolError("short lighting reply")
        return LightInfo(
            effect=reply[2],
            speed=reply[4],
            r=reply[5],
            g=reply[6],
            b=reply[7],
            brightness=reply[8],
        )

    def _write_light_payload(self, light: LightInfo) -> None:
        payload = bytes([
            light.effect & 0xFF,
            0,
            light.speed & 0xFF,
            light.r & 0xFF,
            light.g & 0xFF,
            light.b & 0xFF,
            min(light.brightness, BRIGHTNESS_MAX),
        ])
        self._ask_custom(CMD_CUSTOM_SET_VALUE, V_LIGHT_INFO, payload)

    def write_light(self, light: LightInfo) -> None:
        self._guard("changing lighting")
        # This firmware ignores colour/brightness writes while the effect is
        # Off.  Stage a visible effect with the target values and then turn it
        # off, otherwise an Off -> Off brightness/colour edit is lost.
        if light.effect == 0:
            self._write_light_payload(LightInfo(
                effect=2,
                speed=light.speed,
                r=light.r,
                g=light.g,
                b=light.b,
                brightness=light.brightness,
            ))
        self._write_light_payload(light)

    def read_key_colors(self, row: int = 0, col: int = 0, count: int | None = None) -> list[tuple[int, int, int]]:
        count = MAX_COLORS if count is None else min(count, MAX_COLORS)
        reply = self._ask_custom(CMD_CUSTOM_GET_VALUE, V_GET_KEY_COLOR,
                                 bytes([row, col, count]))
        if len(reply) < 5:
            raise ProtocolError("short per-key colour reply")
        if reply[1] != V_GET_KEY_COLOR or reply[2] != row or reply[3] != col or reply[4] != count:
            raise ProtocolError(
                "per-key colour reply did not echo the requested row, column and count"
            )
        span = count * 3
        data = reply[5:5 + span]
        if len(data) != span:
            raise ProtocolError(
                f"per-key colour reply had {len(data)} payload bytes, expected {span}"
            )
        return [
            (data[index], data[index + 1], data[index + 2])
            for index in range(0, span, 3)
        ]

    def read_all_key_colors(self) -> list[tuple[int, int, int]]:
        colors: list[tuple[int, int, int]] = []
        while len(colors) < self.board.total_keys:
            row, col = divmod(len(colors), self.board.cols)
            want = min(MAX_COLORS, self.board.total_keys - len(colors))
            chunk = self.read_key_colors(row, col, want)
            if len(chunk) != want:
                raise ProtocolError(
                    f"per-key colour read returned {len(chunk)} of {want} colours"
                )
            colors.extend(chunk)
        return colors[:self.board.total_keys]

    def write_key_colors(
        self, row: int, col: int, colors: list[tuple[int, int, int]]
    ) -> None:
        self._guard("changing per-key lighting")
        if len(colors) > MAX_COLORS:
            raise ValueError("too many colours in one packet")
        payload = bytes([row, col, len(colors)]) + b"".join(
            bytes([max(0, min(255, value)) for value in color]) for color in colors
        )
        self._ask_custom(CMD_CUSTOM_SET_VALUE, V_SET_KEY_COLOR, payload)

    def write_all_key_colors(self, colors: list[tuple[int, int, int]]) -> None:
        for index in range(0, min(len(colors), self.board.total_keys), MAX_COLORS):
            row, col = divmod(index, self.board.cols)
            self.write_key_colors(row, col, colors[index:index + MAX_COLORS])

    def save_lighting(self) -> None:
        self._guard("saving lighting")
        self._ask_vendor(CMD_SET_KEYBOARD_VALUE, V_SAVE_LAMPLIGHT)

    def read_box_light(self) -> BoxLight:
        reply = self._ask_vendor(CMD_GET_KEYBOARD_VALUE, V_BOX_LIGHT)
        data = reply[3:]
        if len(data) < 4:
            raise ProtocolError("short side-light reply")
        return BoxLight(data[0], data[1], data[2], data[3])

    def write_box_light(self, box: BoxLight) -> None:
        self._guard("changing the side light")
        self._ask_vendor(CMD_SET_KEYBOARD_VALUE, V_BOX_LIGHT,
                         bytes([box.mode, box.colorful, box.brightness, box.speed]))

    # -- global switches ---------------------------------------------------
    def read_features(self) -> Features:
        reply = self._ask_vendor(CMD_GET_KEYBOARD_VALUE, V_FEATURE)
        data = reply[3:]
        if len(data) < 5:
            raise ProtocolError("short feature reply")
        return Features(data[0], data[1], data[2], data[3], data[4])

    def write_features(self, features: Features) -> None:
        self._guard("changing keyboard switches")
        self._ask_vendor(
            CMD_SET_KEYBOARD_VALUE, V_FEATURE,
            bytes([
                features.rgb_area & 0xFF,
                features.wasd_swap & 0xFF,
                features.mac_mode & 0xFF,
                features.win_lock & 0xFF,
                features.nkro & 0xFF,
            ]),
        )

    def read_dead_band(self) -> DeadBand:
        reply = self._ask_vendor(CMD_GET_KEYBOARD_VALUE, V_DEAD_BAND)
        data = reply[3:]
        if len(data) < 4:
            raise ProtocolError("short dead-band reply")
        return DeadBand(
            travel_from_raw(int.from_bytes(data[0:2], "big")),
            travel_from_raw(int.from_bytes(data[2:4], "big")),
        )

    def write_dead_band(self, band: DeadBand) -> None:
        self._guard("changing the dead band")
        self._ask_vendor(
            CMD_SET_KEYBOARD_VALUE, V_DEAD_BAND,
            _travel_bytes(band.top_mm) + _travel_bytes(band.bottom_mm),
        )

    def read_game_mode(self) -> int:
        reply = self._ask_vendor(CMD_GET_KEYBOARD_VALUE, V_GAME_MODE)
        _require_len(reply, 4, "game mode")
        return reply[3]

    def write_game_mode(self, mode: int) -> None:
        self._guard("changing game mode")
        self._ask_vendor(CMD_SET_KEYBOARD_VALUE, V_GAME_MODE, bytes([mode & 0xFF]))

    def read_bottom_optimize(self) -> int:
        reply = self._ask_vendor(CMD_GET_KEYBOARD_VALUE, V_BOTTOM_OPTIMIZE)
        _require_len(reply, 4, "bottom-out optimisation")
        return reply[3]

    def write_bottom_optimize(self, value: int) -> None:
        self._guard("changing bottom-out optimisation")
        self._ask_vendor(CMD_SET_KEYBOARD_VALUE, V_BOTTOM_OPTIMIZE, bytes([value & 0xFF]))

    # -- keymap -----------------------------------------------------------
    def read_keymap(self) -> bytes:
        return self.read_buffer(CMD_DYNAMIC_KEYMAP_GET_BUFFER, self.board.keymap_size)

    def write_keycode(self, layer: int, row: int, col: int, keycode: int) -> None:
        # Big-endian is correct for SET_KEYCODE on this firmware; verified by
        # reading the dynamic keymap buffer back on a MAD68 HE RGB.
        self._guard("changing the keymap")
        self._ask(
            build_report(
                CMD_DYNAMIC_KEYMAP_SET_KEYCODE,
                bytes([layer, row, col]) + keycode.to_bytes(2, "big"),
            ),
            CMD_DYNAMIC_KEYMAP_SET_KEYCODE,
        )

    def read_keycode(self, layer: int, row: int, col: int) -> int:
        # The dynamic keymap buffer is authoritative.  GET_KEYCODE returns the
        # same value at raw[4:6] on this firmware, but is kept separate so a
        # future firmware cannot make the keymap page disagree with the buffer.
        keymap = self.read_keymap()
        offset = ((layer * self.board.rows + row) * self.board.cols + col) * 2
        return int.from_bytes(keymap[offset:offset + 2], "big")

    def read_keycode_direct(self, layer: int, row: int, col: int) -> int:
        """Raw GET_KEYCODE reply, for diagnostics and protocol tests."""
        reply = self._ask(
            build_report(CMD_DYNAMIC_KEYMAP_GET_KEYCODE, bytes([layer, row, col])),
            CMD_DYNAMIC_KEYMAP_GET_KEYCODE,
        )
        _require_len(reply, 6, "keycode")
        return int.from_bytes(reply[4:6], "big")

    # -- macros ------------------------------------------------------------
    def read_macros(self) -> bytes:
        size = self.read_macro_buffer_size()
        if not size:
            return b""
        return self.read_buffer(CMD_MACRO_GET_BUFFER, size)

    def write_macros(self, data: bytes) -> None:
        self._guard("changing macros")
        self.write_buffer(CMD_MACRO_SET_BUFFER, data)

    # -- advanced keys -----------------------------------------------------
    def read_advanced_key(self, index: int) -> AdvancedKey:
        payload = bytearray(REPORT - 1)
        payload[0] = CUSTOM_CHANNEL
        payload[1] = V_ADVANCED_KEY
        payload[4] = SUB_GET
        payload[5] = index
        payload[6] = index
        reply = self._ask(
            build_report(CMD_GET_KEYBOARD_VALUE, bytes(payload)),
            CMD_GET_KEYBOARD_VALUE,
            bytes([CUSTOM_CHANNEL, V_ADVANCED_KEY]),
        )
        if len(reply) < 18:
            raise ProtocolError("short advanced-key reply")
        try:
            mode = AdvancedMode(reply[7])
        except ValueError:
            mode = AdvancedMode.NONE
        return AdvancedKey(
            index=reply[6],
            mode=mode,
            key_id=reply[8],
            rs_apc_lv=int.from_bytes(reply[9:11], "big"),
            gapc_sw=reply[11],
            rt_sw=reply[12],
            key1_row=reply[13],
            key1_col=reply[14],
            key2_row=reply[15],
            key2_col=reply[16],
            layer=reply[17],
        )

    def write_advanced_key(self, key: AdvancedKey) -> None:
        self._guard("changing an advanced key")
        payload = bytearray(REPORT - 1)
        payload[0] = CUSTOM_CHANNEL
        payload[1] = V_ADVANCED_KEY
        payload[4] = SUB_SET
        payload[5] = key.index
        payload[6] = int(key.mode)
        key_id = key.key_id - 0x1A if key.key_id >= 0x1A else key.key_id
        payload[7] = key_id & 0xFF
        payload[8:10] = min(0xFFFF, key.rs_apc_lv).to_bytes(2, "big")
        payload[10] = key.gapc_sw & 0xFF
        payload[11] = key.rt_sw & 0xFF
        payload[12] = key.key1_row & 0xFF
        payload[13] = key.key1_col & 0xFF
        payload[14] = key.key2_row & 0xFF
        payload[15] = key.key2_col & 0xFF
        payload[16] = key.layer & 0xFF
        self._ask(
            build_report(CMD_SET_KEYBOARD_VALUE, bytes(payload)),
            CMD_SET_KEYBOARD_VALUE,
            bytes([CUSTOM_CHANNEL, V_ADVANCED_KEY]),
        )

    def read_dks(self, index: int) -> Dks:
        payload = bytearray(REPORT - 1)
        payload[0] = CUSTOM_CHANNEL
        payload[1] = V_DKS
        payload[4] = SUB_GET
        payload[5] = index
        reply = self._ask(
            build_report(CMD_GET_KEYBOARD_VALUE, bytes(payload)),
            CMD_GET_KEYBOARD_VALUE,
            bytes([CUSTOM_CHANNEL, V_DKS]),
        )
        _require_len(reply, 23, "DKS binding")
        body = reply[7:23]
        actions = tuple(DksAction.from_bytes(body[i:i + 4]) for i in range(0, 16, 4))
        return Dks(index=index, actions=actions)  # type: ignore[arg-type]

    def write_dks(self, dks: Dks) -> None:
        self._guard("changing a DKS binding")
        payload = bytearray(REPORT - 1)
        payload[0] = CUSTOM_CHANNEL
        payload[1] = V_DKS
        payload[4] = SUB_SET
        payload[5] = dks.index
        payload[6:22] = dks.to_bytes()
        self._ask(
            build_report(CMD_SET_KEYBOARD_VALUE, bytes(payload)),
            CMD_SET_KEYBOARD_VALUE,
            bytes([CUSTOM_CHANNEL, V_DKS]),
        )

    def read_tap_dance(self, index: int) -> TapDance:
        # Vial framing: FE 0D 01 index
        report = build_report(CMD_VIAL_PREFIX, bytes([0x0D, V_TAP_DANCE_GET, index]))
        reply = self._ask(report, CMD_VIAL_PREFIX, bytes([0x0D, V_TAP_DANCE_GET]))
        if len(reply) < 10:
            raise ProtocolError("short hold/click reply")
        return TapDance(
            index=reply[3],
            tap=int.from_bytes(reply[4:6], "big"),
            hold=int.from_bytes(reply[6:8], "big"),
            timer_ms=int.from_bytes(reply[8:10], "big"),
        )

    def write_tap_dance(self, tap_dance: TapDance) -> None:
        self._guard("changing a hold/click binding")
        report = build_report(
            CMD_VIAL_PREFIX,
            bytes([0x0D, V_TAP_DANCE_SET, tap_dance.index])
            + tap_dance.tap.to_bytes(2, "big")
            + tap_dance.hold.to_bytes(2, "big")
            + max(0, min(0xFFFF, tap_dance.timer_ms)).to_bytes(2, "big"),
        )
        self._ask(report, CMD_VIAL_PREFIX, bytes([0x0D, V_TAP_DANCE_SET]))

    # -- telemetry ---------------------------------------------------------
    def _read_u16_buffer(self, sub: int, count: int) -> list[int]:
        values: list[int] = []
        while len(values) < count:
            want = min(MAX_TELEMETRY_READ, count - len(values))
            last_error: Exception | None = None
            for _attempt in range(3):
                try:
                    reply = self._ask(
                        self._bulk_request(sub, len(values), want),
                        CMD_GET_KEYBOARD_VALUE,
                        bytes([CUSTOM_CHANNEL, sub]),
                        timeout=0.6,
                    )
                    break
                except ProtocolError as exc:
                    last_error = exc
            else:
                raise last_error or ProtocolError("telemetry read failed")
            data = self._bulk_reply_data(reply, len(values), want, 2, "telemetry")
            values.extend(int.from_bytes(data[i:i + 2], "big") for i in range(0, len(data), 2))
        return values

    def read_adc(self) -> list[int]:
        return self._read_u16_buffer(V_ADC_BUFFER, self.board.total_keys)

    def read_travel(self) -> list[float]:
        raw = self._read_u16_buffer(V_TRIP_BUFFER, self.board.total_keys)
        return [travel_from_raw(value) for value in raw]

    def read_one_travel(self, row: int, col: int) -> float:
        reply = self._ask_vendor(CMD_GET_KEYBOARD_VALUE, V_TRIP_SINGLE,
                                 bytes([row, col]), timeout=0.4)
        _require_len(reply, 7, "single travel value")
        return travel_from_raw(int.from_bytes(reply[5:7], "big"))

    def read_one_adc(self, row: int, col: int) -> int:
        reply = self._ask_vendor(CMD_GET_KEYBOARD_VALUE, V_ADC_SINGLE,
                                 bytes([row, col]), timeout=0.4)
        _require_len(reply, 7, "single ADC value")
        return int.from_bytes(reply[5:7], "big")

    # -- persistence -------------------------------------------------------
    def commit(self) -> None:
        """Persist the live actuation and rapid-trigger values to flash."""
        self._guard("saving settings")
        actuation = self.read_actuation()
        triggers = self.read_rapid_trigger()
        self.write_actuation(actuation, flash=FLASH_ERASE_AND_WRITE)
        self.write_rapid_trigger(triggers, flash=FLASH_ERASE_AND_WRITE)

    def save_all(self) -> str | None:
        """Persist tuning and lighting, returning a lighting warning if any.

        Tuning is committed first.  A lighting failure must not turn a
        partially successful save into a success message.
        """
        self.commit()
        try:
            self.save_lighting()
        except Exception as exc:  # noqa: BLE001 - reported to the caller
            return str(exc)
        return None

    # -- diagnostics -------------------------------------------------------
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            board=self.board,
            title=self.info.title,
            product_name=self.info.product_name,
            serial=self.info.serial,
            usb_id=self.info.usb_id,
            hidraw=self.info.hidraw,
            interface=self.info.interface,
            protocol_version=self.protocol_version,
            firmware_verified=self._firmware_verified,
            writable=self._writable,
            read_only_reason=self._read_only_reason,
        )

    def read_report(self, *, include_serial: bool = False) -> dict:
        """A read-only diagnostic snapshot for issue reports.

        The USB serial is redacted unless the caller explicitly opts in.
        """
        result: dict = {
            "board": self.board.name,
            "usb_id": self.info.usb_id,
            "product_name": self.info.product_name,
            "serial": self.info.serial if include_serial else "redacted",
            "hidraw": self.info.hidraw,
            "protocol_version": self.protocol_version,
            "writable": self._writable,
            "read_only_reason": self._read_only_reason,
        }
        readers: list[tuple[str, Callable[[], object]]] = [
            ("layers", self.read_layer_count),
            ("features", lambda: self.read_features().to_json()),
            ("dead_band", lambda: self.read_dead_band().to_json()),
            ("game_mode", self.read_game_mode),
            ("bottom_optimize", self.read_bottom_optimize),
            ("light", lambda: self.read_light().to_json()),
            ("box_light", lambda: self.read_box_light().__dict__),
        ]
        for name, reader in readers:
            try:
                result[name] = reader()
            except (DeviceError, ValueError, OSError) as exc:
                result[name] = f"error: {exc}"
        return result
