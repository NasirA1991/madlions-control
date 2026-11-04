"""Physical key layouts for the supported boards.

The matrix is packed row-major, but several matrix positions are empty (a
68-key board has 75 matrix cells).  The tables below describe where each
physical key sits on the drawn board and how wide its keycap is, in key units.
"""

from __future__ import annotations

from dataclasses import dataclass

from .boards import BoardSpec


@dataclass(frozen=True)
class KeySpec:
    row: int
    col: int
    width: float
    label: str
    legend: str = ""

    @property
    def ident(self) -> tuple[int, int]:
        return self.row, self.col


def _k(row: int, col: int, width: float, label: str, legend: str = "") -> KeySpec:
    return KeySpec(row, col, width, label, legend)


# --- 65% / 68 keys, 5 x 15 matrix, 16 units wide ---------------------------
_LAYOUT_65: tuple[tuple[KeySpec, ...], ...] = (
    (
        _k(0, 0, 1, "Esc", "esc"),
        _k(0, 1, 1, "1", "!"),
        _k(0, 2, 1, "2", "@"),
        _k(0, 3, 1, "3", "#"),
        _k(0, 4, 1, "4", "$"),
        _k(0, 5, 1, "5", "%"),
        _k(0, 6, 1, "6", "^"),
        _k(0, 7, 1, "7", "&"),
        _k(0, 8, 1, "8", "*"),
        _k(0, 9, 1, "9", "("),
        _k(0, 10, 1, "0", ")"),
        _k(0, 11, 1, "-", "_"),
        _k(0, 12, 1, "=", "+"),
        _k(0, 13, 2, "Backspace"),
        _k(0, 14, 1, "Ins"),
    ),
    (
        _k(1, 0, 1.5, "Tab"),
        _k(1, 1, 1, "Q"),
        _k(1, 2, 1, "W"),
        _k(1, 3, 1, "E"),
        _k(1, 4, 1, "R"),
        _k(1, 5, 1, "T"),
        _k(1, 6, 1, "Y"),
        _k(1, 7, 1, "U"),
        _k(1, 8, 1, "I"),
        _k(1, 9, 1, "O"),
        _k(1, 10, 1, "P"),
        _k(1, 11, 1, "["),
        _k(1, 12, 1, "]"),
        _k(1, 13, 1.5, "\\", "|"),
        _k(1, 14, 1, "Del"),
    ),
    (
        _k(2, 0, 1.75, "Caps"),
        _k(2, 1, 1, "A"),
        _k(2, 2, 1, "S"),
        _k(2, 3, 1, "D"),
        _k(2, 4, 1, "F"),
        _k(2, 5, 1, "G"),
        _k(2, 6, 1, "H"),
        _k(2, 7, 1, "J"),
        _k(2, 8, 1, "K"),
        _k(2, 9, 1, "L"),
        _k(2, 10, 1, ";", ":"),
        _k(2, 11, 1, "'", '"'),
        _k(2, 13, 2.25, "Enter"),
        _k(2, 14, 1, "PgUp"),
    ),
    (
        _k(3, 0, 2.25, "Shift"),
        _k(3, 2, 1, "Z"),
        _k(3, 3, 1, "X"),
        _k(3, 4, 1, "C"),
        _k(3, 5, 1, "V"),
        _k(3, 6, 1, "B"),
        _k(3, 7, 1, "N"),
        _k(3, 8, 1, "M"),
        _k(3, 9, 1, ",", "<"),
        _k(3, 10, 1, ".", ">"),
        _k(3, 11, 1, "/", "?"),
        _k(3, 12, 1.75, "Shift"),
        _k(3, 13, 1, "↑"),
        _k(3, 14, 1, "PgDn"),
    ),
    (
        _k(4, 0, 1.25, "Ctrl"),
        _k(4, 1, 1.25, "Win"),
        _k(4, 2, 1.25, "Alt"),
        _k(4, 6, 6.25, "Space"),
        _k(4, 9, 1, "Alt"),
        _k(4, 10, 1, "Fn"),
        _k(4, 11, 1, "Ctrl"),
        _k(4, 12, 1, "←"),
        _k(4, 13, 1, "↓"),
        _k(4, 14, 1, "→"),
    ),
)

# --- 60%, 5 x 14 matrix, 15 units wide -------------------------------------
_LAYOUT_60: tuple[tuple[KeySpec, ...], ...] = (
    (
        _k(0, 0, 1, "Esc"),
        _k(0, 1, 1, "1", "!"),
        _k(0, 2, 1, "2", "@"),
        _k(0, 3, 1, "3", "#"),
        _k(0, 4, 1, "4", "$"),
        _k(0, 5, 1, "5", "%"),
        _k(0, 6, 1, "6", "^"),
        _k(0, 7, 1, "7", "&"),
        _k(0, 8, 1, "8", "*"),
        _k(0, 9, 1, "9", "("),
        _k(0, 10, 1, "0", ")"),
        _k(0, 11, 1, "-", "_"),
        _k(0, 12, 1, "=", "+"),
        _k(0, 13, 2, "Backspace"),
    ),
    (
        _k(1, 0, 1.5, "Tab"),
        _k(1, 1, 1, "Q"),
        _k(1, 2, 1, "W"),
        _k(1, 3, 1, "E"),
        _k(1, 4, 1, "R"),
        _k(1, 5, 1, "T"),
        _k(1, 6, 1, "Y"),
        _k(1, 7, 1, "U"),
        _k(1, 8, 1, "I"),
        _k(1, 9, 1, "O"),
        _k(1, 10, 1, "P"),
        _k(1, 11, 1, "["),
        _k(1, 12, 1, "]"),
        _k(1, 13, 1.5, "\\", "|"),
    ),
    (
        _k(2, 0, 1.75, "Caps"),
        _k(2, 1, 1, "A"),
        _k(2, 2, 1, "S"),
        _k(2, 3, 1, "D"),
        _k(2, 4, 1, "F"),
        _k(2, 5, 1, "G"),
        _k(2, 6, 1, "H"),
        _k(2, 7, 1, "J"),
        _k(2, 8, 1, "K"),
        _k(2, 9, 1, "L"),
        _k(2, 10, 1, ";", ":"),
        _k(2, 11, 1, "'", '"'),
        _k(2, 13, 2.25, "Enter"),
    ),
    (
        _k(3, 0, 2.25, "Shift"),
        _k(3, 2, 1, "Z"),
        _k(3, 3, 1, "X"),
        _k(3, 4, 1, "C"),
        _k(3, 5, 1, "V"),
        _k(3, 6, 1, "B"),
        _k(3, 7, 1, "N"),
        _k(3, 8, 1, "M"),
        _k(3, 9, 1, ",", "<"),
        _k(3, 10, 1, ".", ">"),
        _k(3, 11, 1, "/", "?"),
        _k(3, 13, 2.75, "Shift"),
    ),
    (
        _k(4, 0, 1.25, "Ctrl"),
        _k(4, 1, 1.25, "Win"),
        _k(4, 2, 1.25, "Alt"),
        _k(4, 6, 6.25, "Space"),
        _k(4, 10, 1.25, "Fn"),
        _k(4, 11, 1.25, "Menu"),
        _k(4, 12, 1.25, "Ctrl"),
        _k(4, 13, 1.25, "Fn"),
    ),
)


def _grid(cols: int) -> tuple[tuple[KeySpec, ...], ...]:
    return tuple(
        tuple(_k(row, col, 1, "") for col in range(cols))
        for row in range(5)
    )


def layout_for(board: BoardSpec) -> tuple[tuple[KeySpec, ...], ...]:
    if board.cols == 15 and board.rows == 5:
        return _LAYOUT_65
    if board.cols == 14 and board.rows == 5:
        return _LAYOUT_60
    return _grid(board.cols)


def keys_for(board: BoardSpec) -> list[KeySpec]:
    return [key for row in layout_for(board) for key in row]


def key_at(board: BoardSpec, row: int, col: int) -> KeySpec | None:
    for key in keys_for(board):
        if key.row == row and key.col == col:
            return key
    return None


def row_width(row: tuple[KeySpec, ...]) -> float:
    return sum(key.width for key in row)


def max_row_width(rows: tuple[tuple[KeySpec, ...], ...]) -> float:
    return max((row_width(row) for row in rows), default=1.0)
