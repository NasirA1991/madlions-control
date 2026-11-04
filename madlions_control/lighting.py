"""Lighting effect metadata shared by the UI, profiles and CLI."""

from __future__ import annotations

from dataclasses import dataclass

BRIGHTNESS_MAX = 210
SPEED_MIN = 1
SPEED_MAX = 255
DEFAULT_SPEED = 128
DEFAULT_COLOR = (255, 255, 255)
PER_KEY_EFFECT = 1

RGB = tuple[int, int, int]


@dataclass(frozen=True)
class Effect:
    number: int
    name: str
    uses_color: bool
    animated: bool

    @property
    def accent(self) -> str:
        if not self.uses_color:
            return "rainbow"
        if self.animated:
            return "motion"
        return "solid"


# From the vendor configurator's own effect table.  A static effect is a still
# image by design; 4 and 5 are the two "Rainbow static" images.
EFFECTS: tuple[Effect, ...] = (
    Effect(0, "Off", False, False),
    Effect(1, "Custom", True, False),
    Effect(2, "Solid colour", True, False),
    Effect(3, "Focus", True, False),
    Effect(4, "Rainbow — vertical", True, False),
    Effect(5, "Rainbow — horizontal", True, False),
    Effect(6, "Breathing", True, True),
    Effect(7, "Ribbon 1", True, True),
    Effect(8, "Ribbon 2", True, True),
    Effect(9, "Rotating belt 1", True, True),
    Effect(11, "Rotating belt 2", True, True),
    Effect(13, "Spectrum cycle", False, True),
    Effect(19, "Colour swirl 1", False, True),
    Effect(23, "Colour swirl 2", False, True),
    Effect(25, "Christmas", False, False),
    Effect(26, "Spectrum breathing", True, True),
    Effect(28, "Spectrum floating", True, True),
    Effect(30, "Digital rain", False, False),
    Effect(31, "Lighting up", True, True),
    Effect(36, "Crucifix", True, True),
    Effect(39, "Fingertip rainbow", False, True),
)

BY_NUMBER: dict[int, Effect] = {effect.number: effect for effect in EFFECTS}


def effect(number: int) -> Effect | None:
    return BY_NUMBER.get(number)


def effect_name(number: int) -> str:
    found = effect(number)
    return found.name if found else f"Effect {number}"


def effective_color(r: int, g: int, b: int) -> RGB:
    """An all-zero colour means "never chosen"; use a renderable white."""
    if r == 0 and g == 0 and b == 0:
        return DEFAULT_COLOR
    return (
        max(0, min(255, int(r))),
        max(0, min(255, int(g))),
        max(0, min(255, int(b))),
    )


def clamp_speed(speed: int) -> int:
    return max(SPEED_MIN, min(SPEED_MAX, int(speed)))


def clamp_brightness(brightness: int) -> int:
    return max(0, min(BRIGHTNESS_MAX, int(brightness)))


def rgb_to_hex(color: RGB) -> str:
    r, g, b = color
    return f"#{r:02x}{g:02x}{b:02x}"


def hex_to_rgb(text: str) -> RGB:
    text = text.strip().lstrip("#")
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    if len(text) != 6:
        raise ValueError(f"invalid colour {text!r}")
    return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)


def lerp_color(a: RGB, b: RGB, t: float) -> RGB:
    t = max(0.0, min(1.0, t))
    return (
        round(a[0] + (b[0] - a[0]) * t),
        round(a[1] + (b[1] - a[1]) * t),
        round(a[2] + (b[2] - a[2]) * t),
    )


def heat_color(t: float) -> RGB:
    """Blue → cyan → green → amber → red for live travel displays."""
    t = max(0.0, min(1.0, t))
    stops = [
        (0.0, (56, 122, 255)),
        (0.25, (56, 208, 214)),
        (0.5, (110, 220, 120)),
        (0.72, (255, 190, 70)),
        (1.0, (255, 77, 109)),
    ]
    for (left_t, left), (right_t, right) in zip(stops, stops[1:]):
        if left_t <= t <= right_t:
            rel = 0.0 if right_t == left_t else (t - left_t) / (right_t - left_t)
            return lerp_color(left, right, rel)
    return stops[-1][1]


def rgb_to_hsv(color: RGB) -> tuple[float, float, float]:
    import colorsys

    r, g, b = (component / 255 for component in color)
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    return h * 360.0, s * 100.0, v * 100.0


def hsv_to_rgb(h: float, s: float, v: float) -> RGB:
    import colorsys

    r, g, b = colorsys.hsv_to_rgb((h % 360) / 360.0, max(0.0, min(100.0, s)) / 100.0,
                                  max(0.0, min(100.0, v)) / 100.0)
    return round(r * 255), round(g * 255), round(b * 255)
