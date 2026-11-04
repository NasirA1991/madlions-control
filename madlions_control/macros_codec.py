"""VIA / Vial macro buffer encoding.

The keyboard stores all macros in one NUL-separated buffer:

* ordinary bytes are typed text,
* ``0x01`` introduces an opcode,
* a delay is two bytes in 1..255 so neither can be NUL,
* Vial's two-byte keycode opcodes cover keys above ``0xFF``.
"""

from __future__ import annotations

from dataclasses import dataclass

ESCAPE = 0x01
TERMINATOR = 0x00

OP_TAP = 0x01
OP_DOWN = 0x02
OP_UP = 0x03
OP_DELAY = 0x04
OP_EXT_TAP = 0x05
OP_EXT_DOWN = 0x06
OP_EXT_UP = 0x07


@dataclass(frozen=True)
class MacroStep:
    kind: str                   # tap, down, up, delay, text
    keycode: int = 0
    delay_ms: int = 0
    text: str = ""

    @property
    def summary(self) -> str:
        if self.kind == "text":
            return f'Text "{self.text}"'
        if self.kind == "delay":
            return f"Wait {self.delay_ms} ms"
        return {
            "tap": "Tap",
            "down": "Press",
            "up": "Release",
        }.get(self.kind, self.kind)


def _decode_delay(first: int, second: int) -> int:
    return max(0, (first - 1) + (second - 1) * 255)


def _encode_delay(milliseconds: int) -> bytes:
    milliseconds = max(0, min(255 * 255 + 254, int(milliseconds)))
    return bytes([(milliseconds % 255) + 1, (milliseconds // 255) + 1])


def decode(data: bytes) -> list[MacroStep]:
    steps: list[MacroStep] = []
    text = ""
    index = 0
    while index < len(data):
        byte = data[index]
        if byte != ESCAPE:
            if byte == TERMINATOR:
                break
            text += chr(byte)
            index += 1
            continue
        if text:
            steps.append(MacroStep("text", text=text))
            text = ""
        if index + 1 >= len(data):
            break
        opcode = data[index + 1]
        if opcode in (OP_TAP, OP_DOWN, OP_UP) and index + 2 < len(data):
            kind = {OP_TAP: "tap", OP_DOWN: "down", OP_UP: "up"}[opcode]
            steps.append(MacroStep(kind, keycode=data[index + 2]))
            index += 3
        elif opcode in (OP_EXT_TAP, OP_EXT_DOWN, OP_EXT_UP) and index + 3 < len(data):
            kind = {OP_EXT_TAP: "tap", OP_EXT_DOWN: "down", OP_EXT_UP: "up"}[opcode]
            steps.append(MacroStep(kind, keycode=data[index + 2] | (data[index + 3] << 8)))
            index += 4
        elif opcode == OP_DELAY and index + 3 < len(data):
            steps.append(MacroStep("delay", delay_ms=_decode_delay(data[index + 2], data[index + 3])))
            index += 4
        else:
            index += 2
    if text:
        steps.append(MacroStep("text", text=text))
    return steps


def encode(steps: list[MacroStep]) -> bytes:
    out = bytearray()
    for step in steps:
        if step.kind == "text":
            for character in step.text:
                code = ord(character)
                if code in (ESCAPE, TERMINATOR) or code > 0x7F:
                    raise ValueError(
                        f"macro text cannot contain {character!r}; use a key tap instead"
                    )
                out.append(code)
        elif step.kind == "delay":
            out += bytes([ESCAPE, OP_DELAY]) + _encode_delay(step.delay_ms)
        elif step.kind in ("tap", "down", "up"):
            if step.keycode < 0 or step.keycode > 0xFFFF:
                raise ValueError("keycode out of range")
            if step.keycode > 0xFF:
                opcode = {"tap": OP_EXT_TAP, "down": OP_EXT_DOWN, "up": OP_EXT_UP}[step.kind]
                out += bytes([ESCAPE, opcode, step.keycode & 0xFF,
                              (step.keycode >> 8) & 0xFF])
            else:
                opcode = {"tap": OP_TAP, "down": OP_DOWN, "up": OP_UP}[step.kind]
                out += bytes([ESCAPE, opcode, step.keycode])
        else:
            raise ValueError(f"unknown macro step {step.kind!r}")
    return bytes(out)


def split(buffer: bytes, count: int) -> list[bytes]:
    macros: list[bytes] = []
    start = 0
    for _ in range(count):
        end = buffer.find(bytes([TERMINATOR]), start)
        if end < 0:
            macros.append(buffer[start:])
            start = len(buffer)
            continue
        macros.append(buffer[start:end])
        start = end + 1
    while len(macros) < count:
        macros.append(b"")
    return macros[:count]


def managed_end(buffer: bytes, count: int) -> int:
    position = 0
    seen = 0
    while seen < count and position < len(buffer):
        found = buffer.find(bytes([TERMINATOR]), position)
        if found < 0:
            return len(buffer)
        position = found + 1
        seen += 1
    return position


def join(macros: list[bytes], size: int, *, tail: bytes = b"") -> bytes:
    body = bytearray()
    for macro in macros:
        body += macro
        body.append(TERMINATOR)
    if len(body) > size:
        raise ValueError(f"macros need {len(body)} bytes, the buffer is {size}")
    if len(body) + len(tail) > size:
        tail = tail[: max(0, size - len(body))]
    out = bytes(body) + tail
    return out[:size] + bytes(max(0, size - len(out)))


def rebuild(buffer: bytes, index: int, encoded: bytes, count: int) -> bytes:
    """Replace one macro while preserving every other byte of the buffer."""
    current = split(buffer, count)
    if not 0 <= index < len(current):
        raise ValueError("macro index out of range")
    current[index] = encoded
    return join(current, len(buffer), tail=buffer[managed_end(buffer, count):])


def steps_summary(steps: list[MacroStep]) -> str:
    if not steps:
        return "Empty"
    pieces = []
    for step in steps[:4]:
        if step.kind == "text":
            pieces.append(f'"{step.text[:12]}"')
        elif step.kind == "delay":
            pieces.append(f"{step.delay_ms} ms")
        else:
            from . import keycodes

            pieces.append(keycodes.label(step.keycode))
    suffix = " …" if len(steps) > 4 else ""
    return " · ".join(pieces) + suffix
