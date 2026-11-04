"""Known, non-destructive tuning baselines for verified boards.

A baseline deliberately covers only volatile tuning: actuation, rapid trigger,
lighting, switches, dead band, game mode and bottom-out optimisation.  It never
touches the keymap, macros, advanced keys, hold/click, DKS, per-key colours or
sensor calibration.

The values here were read from physical hardware before any test writes.  They
are offered as an *observed* baseline, not as a universal factory reset: boards
and firmware revisions differ, and no reset command is used.
"""

from __future__ import annotations

from dataclasses import dataclass

from .boards import BoardSpec
from .device import (
    DeadBand,
    Features,
    LightInfo,
    MadlionsDevice,
    RapidTrigger,
)
from .lighting import effect_name


class BaselineError(ValueError):
    """A baseline could not be applied or did not read back."""


@dataclass(frozen=True)
class Baseline:
    product_id: int
    label: str
    actuation_mm: float
    rapid_trigger: RapidTrigger
    light: LightInfo
    features: Features
    dead_band: DeadBand
    game_mode: int
    bottom_optimize: int

    def applies_to(self, board: BoardSpec) -> bool:
        return board.product_id == self.product_id

    def preview_lines(self) -> list[str]:
        rt = self.rapid_trigger
        features = self.features
        return [
            f"Actuation: {self.actuation_mm:.2f} mm on every key",
            f"Rapid trigger: {'on' if rt.enabled else 'off'}, "
            f"{rt.press_mm:.2f}/{rt.release_mm:.2f} mm",
            f"Lighting: {effect_name(self.light.effect)}, brightness {self.light.brightness}, "
            f"{self.light.hex}",
            "Switches: NKRO " + ("on" if features.nkro else "off")
            + ", Win lock " + ("on" if features.win_lock else "off")
            + ", WASD " + ("swapped" if features.wasd_swap else "standard")
            + ", macOS " + ("on" if features.mac_mode else "off"),
            f"Dead band: {self.dead_band.top_mm:.2f}/{self.dead_band.bottom_mm:.2f} mm",
            f"Game mode: {self.game_mode} · bottom-out optimisation: "
            + ("on" if self.bottom_optimize else "off"),
        ]

    def apply(self, device: MadlionsDevice, board: BoardSpec) -> list[str]:
        """Write and verify the volatile baseline; never persist it."""
        total = board.total_keys
        actions: list[str] = []

        device.write_actuation([self.actuation_mm] * total)
        actions.append(f"{total} actuation points")

        device.write_rapid_trigger([self.rapid_trigger] * total)
        actions.append(f"{total} rapid-trigger values")

        device.write_light(self.light)
        actions.append("lighting")

        device.write_features(self.features)
        actions.append("switches")

        device.write_dead_band(self.dead_band)
        actions.append("dead band")

        device.write_game_mode(self.game_mode)
        device.write_bottom_optimize(self.bottom_optimize)
        actions.append("game mode and bottom-out optimisation")

        self.verify(device, board)
        return actions

    def verify(self, device: MadlionsDevice, board: BoardSpec) -> None:
        actuation = device.read_actuation()
        bad = [
            index for index, value in enumerate(actuation)
            if abs(value - self.actuation_mm) > 0.011
        ]
        if bad:
            raise BaselineError(
                f"actuation did not read back on {len(bad)} key(s)"
            )

        triggers = device.read_rapid_trigger()
        bad = [
            index for index, value in enumerate(triggers)
            if (value.enabled != self.rapid_trigger.enabled
                or abs(value.press_mm - self.rapid_trigger.press_mm) > 0.011
                or abs(value.release_mm - self.rapid_trigger.release_mm) > 0.011)
        ]
        if bad:
            raise BaselineError(
                f"rapid trigger did not read back on {len(bad)} key(s)"
            )

        light = device.read_light()
        if light.effect != self.light.effect or light.brightness != self.light.brightness:
            raise BaselineError("lighting did not read back")

        if device.read_features() != self.features:
            raise BaselineError("switches did not read back")

        dead_band = device.read_dead_band()
        if (abs(dead_band.top_mm - self.dead_band.top_mm) > 0.011
                or abs(dead_band.bottom_mm - self.dead_band.bottom_mm) > 0.011):
            raise BaselineError("dead band did not read back")

        if device.read_game_mode() != self.game_mode:
            raise BaselineError("game mode did not read back")
        if device.read_bottom_optimize() != self.bottom_optimize:
            raise BaselineError("bottom-out optimisation did not read back")


# Only boards that have been driven and observed on real hardware get a
# baseline.  Adding another board means capturing its values deliberately,
# not guessing them.
BASELINES: tuple[Baseline, ...] = (
    Baseline(
        product_id=0x1058,
        label="MAD68 HE RGB observed baseline",
        actuation_mm=1.50,
        rapid_trigger=RapidTrigger(True, 0.50, 0.50),
        light=LightInfo(effect=0, speed=127, r=7, g=30, b=29, brightness=103),
        features=Features(nkro=1),
        dead_band=DeadBand(0.20, 0.20),
        game_mode=0,
        bottom_optimize=1,
    ),
)


def for_board(board: BoardSpec) -> Baseline | None:
    for baseline in BASELINES:
        if baseline.applies_to(board):
            return baseline
    return None


def require(board: BoardSpec) -> Baseline:
    baseline = for_board(board)
    if baseline is None:
        raise BaselineError(
            f"no verified tuning baseline is available for {board.name}"
        )
    return baseline


__all__ = [
    "BASELINES",
    "Baseline",
    "BaselineError",
    "for_board",
    "require",
]
