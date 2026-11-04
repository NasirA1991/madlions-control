"""QMK-style 16-bit keycodes used by the VIA dynamic keymap.

The keyboard stores one 16-bit value per matrix cell.  Values up to ``0x00FF``
are ordinary HID usages; the layer functions live in QMK's ``0x52xx`` block.
Only keycodes this firmware family is known to accept are offered in the picker.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Keycode:
    code: int
    name: str
    label: str
    category: str = "Special"
    legend: str = ""

    @property
    def search(self) -> str:
        return f"{self.name} {self.label} {self.legend} {self.category}".lower()


KC_NO = 0x0000
KC_TRNS = 0x0001

MOD_NAMES = {
    0xE0: "LCtrl",
    0xE1: "LShift",
    0xE2: "LAlt",
    0xE3: "LGui",
    0xE4: "RCtrl",
    0xE5: "RShift",
    0xE6: "RAlt",
    0xE7: "RGui",
}

_PUNCT = [
    (0x2D, "-", "_", "Minus"),
    (0x2E, "=", "+", "Equal"),
    (0x2F, "[", "{", "LeftBracket"),
    (0x30, "]", "}", "RightBracket"),
    (0x31, "\\", "|", "Backslash"),
    (0x33, ";", ":", "Semicolon"),
    (0x34, "'", '"', "Quote"),
    (0x35, "`", "~", "Grave"),
    (0x36, ",", "<", "Comma"),
    (0x37, ".", ">", "Period"),
    (0x38, "/", "?", "Slash"),
]
_NAV = [
    (0x49, "Ins", "Insert"),
    (0x4A, "Home", "Home"),
    (0x4B, "PgUp", "PageUp"),
    (0x4C, "Del", "Delete"),
    (0x4D, "End", "End"),
    (0x4E, "PgDn", "PageDown"),
    (0x4F, "Right", "RightArrow"),
    (0x50, "Left", "LeftArrow"),
    (0x51, "Down", "DownArrow"),
    (0x52, "Up", "UpArrow"),
]
_MEDIA = [
    (0x00A4, "Power", "POWER", "Media"),
    (0x00A5, "Sleep", "SLEEP", "Media"),
    (0x00A6, "Wake", "WAKE", "Media"),
    (0x00A7, "Mute", "MUTE", "Media"),
    (0x00A8, "Vol+", "VOL+", "Media"),
    (0x00A9, "Vol-", "VOL-", "Media"),
    (0x00AB, "Next", "NEXT", "Media"),
    (0x00AC, "Prev", "PREV", "Media"),
    (0x00AD, "Stop", "STOP", "Media"),
    (0x00AE, "Play", "PLAY", "Media"),
]


def _build() -> list[Keycode]:
    out: list[Keycode] = [
        Keycode(KC_NO, "KC_NO", "—", "Special", "nothing empty disabled"),
        Keycode(KC_TRNS, "KC_TRNS", "▽", "Special", "transparent pass through"),
    ]
    for i, letter in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
        out.append(Keycode(0x04 + i, f"KC_{letter}", letter, "Letters", letter.lower()))
    for i, digit in enumerate("1234567890"):
        shifted = ")!@#$%^&*("[i]
        out.append(Keycode(0x1E + i, f"KC_{digit}", digit, "Numbers", shifted))
    out += [
        Keycode(0x28, "KC_ENTER", "Enter", "Control", "return"),
        Keycode(0x29, "KC_ESC", "Esc", "Control", "escape"),
        Keycode(0x2A, "KC_BSPC", "Bspc", "Control", "backspace delete"),
        Keycode(0x2B, "KC_TAB", "Tab", "Control"),
        Keycode(0x2C, "KC_SPACE", "Space", "Control"),
        Keycode(0x39, "KC_CAPS", "Caps", "Control", "capslock"),
        Keycode(0x65, "KC_APP", "Menu", "Control", "application"),
        Keycode(0x46, "KC_PSCR", "PrtSc", "Control", "printscreen"),
        Keycode(0x47, "KC_SCRL", "ScrLk", "Control", "scrolllock"),
        Keycode(0x48, "KC_PAUS", "Pause", "Control"),
        Keycode(0x53, "KC_NUM", "NumLk", "Keypad", "numlock"),
    ]
    for code, label, legend, name in _PUNCT:
        out.append(Keycode(code, f"KC_{name.upper()}", label, "Symbols", legend))
    for i in range(12):
        out.append(Keycode(0x3A + i, f"KC_F{i + 1}", f"F{i + 1}", "Function"))
    for i in range(12):
        out.append(Keycode(0x68 + i, f"KC_F{i + 13}", f"F{i + 13}", "Function"))
    for code, label, name in _NAV:
        out.append(Keycode(code, f"KC_{name.upper()}", label, "Navigation"))
    for code, name in MOD_NAMES.items():
        out.append(Keycode(code, f"KC_{name.upper()}", name, "Modifiers"))
    for code, label, name, category in _MEDIA:
        out.append(Keycode(code, f"KC_{name}", label, category))
    # Keypad
    kp = [
        (0x54, "KP/"), (0x55, "KP*"), (0x56, "KP-"), (0x57, "KP+"),
        (0x58, "KPEnt"), (0x59, "KP1"), (0x5A, "KP2"), (0x5B, "KP3"),
        (0x5C, "KP4"), (0x5D, "KP5"), (0x5E, "KP6"), (0x5F, "KP7"),
        (0x60, "KP8"), (0x61, "KP9"), (0x62, "KP0"), (0x63, "KP."),
    ]
    for code, label in kp:
        out.append(Keycode(code, "KC_" + label.replace("KP", "KP_").upper(), label, "Keypad"))
    # Layer functions.  The firmware uses QMK's post-rework 0x52xx block.
    for layer in range(4):
        out += [
            Keycode(0x5200 + layer, f"TO({layer})", f"TO {layer}", "Layers", "switch layer"),
            Keycode(0x5220 + layer, f"MO({layer})", f"MO {layer}", "Layers", "momentary layer"),
            Keycode(0x5240 + layer, f"DF({layer})", f"DF {layer}", "Layers", "default layer"),
            Keycode(0x5260 + layer, f"TG({layer})", f"TG {layer}", "Layers", "toggle layer"),
            Keycode(0x5280 + layer, f"OSL({layer})", f"OSL {layer}", "Layers", "one shot layer"),
        ]
    return out


KEYCODES: tuple[Keycode, ...] = tuple(_build())
BY_CODE: dict[int, Keycode] = {key.code: key for key in KEYCODES}
_BY_NAME: dict[str, Keycode] = {key.name.lower(): key for key in KEYCODES}
for _alias, _target in {
    "kc_lctl": "KC_LCTRL", "kc_lsft": "KC_LSHIFT", "kc_lalt": "KC_LALT",
    "kc_lgui": "KC_LGUI", "kc_rctl": "KC_RCTRL", "kc_rsft": "KC_RSHIFT",
    "kc_ralt": "KC_RALT", "kc_rgui": "KC_RGUI", "kc_ent": "KC_ENTER",
    "kc_esc": "KC_ESC", "kc_bspc": "KC_BSPC", "kc_spc": "KC_SPACE",
    "kc_tab": "KC_TAB", "kc_caps": "KC_CAPS", "kc_del": "KC_DEL",
    "kc_pgup": "KC_PGUP", "kc_pgdn": "KC_PGDN", "kc_ins": "KC_INS",
    "kc_volup": "KC_VOL+", "kc_voldown": "KC_VOL-", "kc_mute": "KC_MUTE",
}.items():
    _target_key = _BY_NAME.get(_target.lower())
    if _target_key is not None:
        _BY_NAME[_alias] = _target_key
_BY_LABEL: dict[str, Keycode] = {}
for _key in KEYCODES:
    _BY_LABEL.setdefault(_key.label.lower(), _key)
CATEGORIES: tuple[str, ...] = tuple(
    dict.fromkeys(key.category for key in KEYCODES)
)


def lookup(code: int) -> Keycode:
    """Resolve a keycode, or synthesise a readable placeholder."""
    key = BY_CODE.get(code)
    if key is not None:
        return key
    if 0x5200 <= code <= 0x529F:
        base = code & 0xFFE0
        layer = code & 0x1F
        names = {0x5200: "TO", 0x5220: "MO", 0x5240: "DF", 0x5260: "TG", 0x5280: "OSL"}
        fn = names.get(base)
        if fn:
            return Keycode(code, f"{fn}({layer})", f"{fn} {layer}", "Layers")
    return Keycode(code, f"0x{code:04X}", f"{code:#06x}", "Special")


def label(code: int) -> str:
    return lookup(code).label


def name(code: int) -> str:
    return lookup(code).name


def from_name(text: str) -> int | None:
    text = text.strip()
    if not text:
        return None
    lowered = text.lower()
    key = _BY_NAME.get(lowered) or _BY_LABEL.get(lowered)
    if key is None and lowered.startswith("kc_"):
        key = _BY_NAME.get(lowered[3:]) or _BY_LABEL.get(lowered[3:])
    if key is not None:
        return key.code
    try:
        if lowered.startswith("0x"):
            return int(text, 16)
        if text.isdigit():
            return int(text)
    except ValueError:
        pass
    return None


def search(text: str, category: str | None = None) -> list[Keycode]:
    needle = text.strip().lower()
    out = []
    for key in KEYCODES:
        if category and key.category != category:
            continue
        if not needle or needle in key.search:
            out.append(key)
    return out
