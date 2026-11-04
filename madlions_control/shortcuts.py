"""Human-readable Fn-layer shortcuts read from the keyboard's keymap.

The keyboard's layer 1 is the Fn layer.  Reading it is more accurate than
hard-coding a manual: the same board can have a different Fn map after the user
edits it, and other members of the MADLIONS family use the same controller.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import keycodes, layout
from .state import KeyboardState

# QMK/VIA lighting keycodes.  The stock MAD68 HE layer 1 uses these exact
# values, and the vendor firmware accepts them as programmable keycodes.
LIGHTING_ACTIONS: dict[int, str] = {
    0x7800: "Backlight on",
    0x7801: "Backlight off",
    0x7802: "Toggle backlight",
    0x7803: "Decrease backlight",
    0x7804: "Increase backlight",
    0x7805: "Cycle backlight level",
    0x7806: "Toggle backlight breathing",
    0x7820: "Toggle RGB lighting",
    0x7821: "Next lighting effect",
    0x7822: "Previous lighting effect",
    0x7823: "Increase colour hue",
    0x7824: "Decrease colour hue",
    0x7825: "Increase saturation",
    0x7826: "Decrease saturation",
    0x7827: "Increase brightness",
    0x7828: "Decrease brightness",
    0x7829: "Increase effect speed",
    0x782A: "Decrease effect speed",
    0x782B: "Plain colour effect",
    0x782C: "Breathing effect",
    0x782D: "Rainbow effect",
    0x782E: "Swirl effect",
    0x782F: "Snake effect",
    0x7830: "Knight rider effect",
    0x7831: "Christmas effect",
    0x7832: "Gradient effect",
    0x7833: "RGB test effect",
    0x7834: "Twinkle effect",
}


@dataclass(frozen=True)
class Shortcut:
    keys: str
    action: str
    detail: str = ""
    category: str = "Lighting"
    code: int = 0


def _fn_key(state: KeyboardState) -> tuple[str, int]:
    """Return the Fn key's cap label and the layer it activates."""
    keys = layout.keys_for(state.board)
    for key in keys:
        code = state.keycode_at(0, key.row, key.col)
        if 0x5220 <= code <= 0x523F:
            layer = code & 0x1F
            if layer > 0:
                return key.label, layer
    for key in keys:
        if key.label.lower() == "fn":
            return key.label, 1
    return "Fn", 1


def build_shortcuts(state: KeyboardState) -> list[Shortcut]:
    """Return the current Fn-layer shortcuts, or [] if the keymap is not loaded."""
    if not state.keymap:
        return []
    fn, fn_layer = _fn_key(state)
    shortcuts: list[Shortcut] = []
    for key in layout.keys_for(state.board):
        code = state.keycode_at(fn_layer, key.row, key.col)
        if code in (0, keycodes.KC_TRNS):
            continue
        combination = f"{fn} + {key.label}"
        if code in LIGHTING_ACTIONS:
            shortcuts.append(Shortcut(
                keys=combination,
                action=LIGHTING_ACTIONS[code],
                category="Lighting",
                code=code,
            ))
        elif 0x3A <= code <= 0x45:
            shortcuts.append(Shortcut(
                keys=combination,
                action=keycodes.label(code),
                category="Function keys",
                code=code,
            ))
        elif code == 0x35:
            shortcuts.append(Shortcut(
                keys=combination,
                action="` / ~",
                category="Function keys",
                code=code,
            ))
        elif 0x7E00 <= code <= 0x7EFF:
            shortcuts.append(Shortcut(
                keys=combination,
                action="Vendor-specific function",
                detail="Not named by the firmware",
                category="Other",
                code=code,
            ))
        else:
            label = keycodes.label(code)
            if label.startswith("0x"):
                continue
            shortcuts.append(Shortcut(
                keys=combination,
                action=label,
                category="Other",
                code=code,
            ))
    return shortcuts
