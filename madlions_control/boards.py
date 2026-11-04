"""Supported MADLIONS / FGG boards.

The controller behind these keyboards is shared across a large family.  The
registry below is the subset that ships on the 32-byte ``VIA``/``DuckBread``
vendor channel this application speaks.  Geometry (rows, columns, layers) is a
property of the board, not of the protocol, so it is kept here.

``verified`` means the board has actually been driven by this project.  Boards
with ``verified=False`` are still readable: the app refuses writes on an
unverified board unless the user explicitly unlocks experimental writes, and it
never writes when the firmware reports a protocol version other than the one the
packet layouts were checked against.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import VID

KNOWN_PROTOCOL_VERSION = 9


@dataclass(frozen=True)
class BoardSpec:
    product_id: int
    name: str
    rows: int = 5
    cols: int = 15
    layers: int = 4
    bootloader_id: int = 0
    verified: bool = False
    layout: str = "65"
    side_light: bool = False

    @property
    def total_keys(self) -> int:
        return self.rows * self.cols

    @property
    def usb_id(self) -> str:
        return f"{VID:04X}:{self.product_id:04X}"

    @property
    def form_factor(self) -> str:
        if self.cols <= 8:
            return "Macropad"
        return "60%" if self.cols <= 14 else "65%"

    @property
    def keymap_size(self) -> int:
        return self.layers * self.rows * self.cols * 2


BOARDS: tuple[BoardSpec, ...] = (
    # 60% family, 5 x 14
    BoardSpec(0x1053, "MAD60 HE", 5, 14, 4, 0x201F, verified=True, layout="60"),
    BoardSpec(0x1054, "MAD60 HE RGB", 5, 14, 4, 0x2020, layout="60"),
    BoardSpec(0x1055, "MAD60 HE Ultra", 5, 14, 4, 0x2021, layout="60"),
    BoardSpec(0x1056, "MAD60 HE Limited", 5, 14, 4, 0x2022, layout="60"),
    BoardSpec(0x105D, "MAD60", 5, 14, 4, 0x202B, layout="60"),
    BoardSpec(0x10AD, "MAD60 Pro", 5, 14, 4, 0x2053, layout="60"),
    BoardSpec(0x1120, "MAD60 HE V2", 5, 14, 4, 0x210B, layout="60"),
    BoardSpec(0x10F6, "MAD Light 60 HE", 5, 14, 4, 0x2085, layout="60"),
    BoardSpec(0x110B, "MAD63 HE", 5, 14, 4, 0x2102, layout="60"),
    BoardSpec(0x112A, "Z60", 5, 14, 4, 0x2115, layout="60"),
    # 65% family, 5 x 15
    BoardSpec(0x1057, "MAD68 HE", 5, 15, 4, 0x2023),
    BoardSpec(0x1058, "MAD68 HE RGB", 5, 15, 4, 0x2024, verified=True),
    BoardSpec(0x1059, "MAD68 HE Ultra", 5, 15, 4, 0x2025),
    BoardSpec(0x105A, "MAD68 HE Limited", 5, 15, 4, 0x2026),
    BoardSpec(0x10A7, "MAD68 R", 5, 15, 4, 0x204E),
    BoardSpec(0x10D6, "MAD68 Pro", 5, 15, 4, 0x2075),
    BoardSpec(0x1123, "MAD68 HE V2", 5, 15, 4, 0x210E),
    BoardSpec(0x1144, "MAD Light 68 HE", 5, 15, 4, 0x212D),
    BoardSpec(0x1136, "Z68", 5, 15, 4, 0x2121),
    BoardSpec(0x1139, "MAG68", 5, 15, 4, 0x2124),
    BoardSpec(0x10A3, "FIRE68", 5, 15, 4, 0x204A),
    BoardSpec(0x10A9, "FIRE68", 5, 15, 4, 0x2050),
    BoardSpec(0x10AA, "FIRE68 Pro", 5, 15, 4, 0x2051),
    BoardSpec(0x10A4, "FIRE68 Ultra", 5, 15, 4, 0x204B),
    BoardSpec(0x10AB, "FIRE68 Ultra", 5, 15, 4, 0x2052),
    # Compact board
    BoardSpec(0x107D, "MAD Smart", 5, 6, 4, 0x2035, layout="grid"),
)

BY_ID: dict[int, BoardSpec] = {board.product_id: board for board in BOARDS}
BOOTLOADER_IDS: frozenset[int] = frozenset(b.bootloader_id for b in BOARDS if b.bootloader_id)
DEFAULT_BOARD = BY_ID[0x1058]


def lookup(product_id: int) -> BoardSpec | None:
    return BY_ID.get(product_id)


def describe(product_id: int, product_name: str = "") -> BoardSpec:
    """The board registry entry, or a conservative generic spec for a new board."""
    board = BY_ID.get(product_id)
    if board is not None:
        return board
    name = product_name.strip() or f"MADLIONS {product_id:04X}"
    return BoardSpec(
        product_id=product_id,
        name=name,
        rows=5,
        cols=15,
        layers=4,
        verified=False,
        layout="grid",
    )


def display_name(board: BoardSpec, product_name: str = "") -> str:
    if board.product_id in BY_ID:
        return board.name
    return product_name.strip() or board.name
