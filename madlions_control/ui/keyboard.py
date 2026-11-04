"""The drawn keyboard: one canvas for editing, keymaps and the live tester."""

from __future__ import annotations

import os

import math
from typing import Callable

import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")

from gi.repository import Gdk, Gtk, Pango, PangoCairo  # noqa: E402

from .. import keycodes, layout
from ..lighting import effect as lighting_effect
from ..lighting import heat_color
from ..state import KeyboardState

PAD = 12.0
MAX_UNIT = 52.0


def _rounded(cr: cairo.Context, x: float, y: float, w: float, h: float, r: float) -> None:
    r = min(r, w / 2, h / 2)
    cr.new_path()
    cr.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
    cr.arc(x + w - r, y + r, r, 1.5 * math.pi, 2 * math.pi)
    cr.arc(x + w - r, y + h - r, r, 0, 0.5 * math.pi)
    cr.arc(x + r, y + h - r, r, 0.5 * math.pi, math.pi)
    cr.close_path()


def _text(cr: cairo.Context, text: str, x: float, y: float, w: float, h: float,
          size: float, color: tuple[float, float, float], weight: Pango.Weight = Pango.Weight.NORMAL,
          align: Pango.Alignment = Pango.Alignment.CENTER) -> None:
    if not text:
        return
    layout_item = PangoCairo.create_layout(cr)
    desc = Pango.FontDescription("Cantarell")
    desc.set_absolute_size(max(7.0, size) * Pango.SCALE)
    desc.set_weight(weight)
    layout_item.set_font_description(desc)
    layout_item.set_text(text, -1)
    layout_item.set_width(int(max(1, w) * Pango.SCALE))
    layout_item.set_alignment(align)
    _ink, logical = layout_item.get_pixel_extents()
    offset_y = y + (h - logical.height) / 2
    cr.move_to(x, offset_y)
    cr.set_source_rgb(*color)
    PangoCairo.show_layout(cr, layout_item)


def _lum(color: tuple[int, int, int]) -> float:
    r, g, b = (value / 255 for value in color)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


class KeyboardCanvas(Gtk.DrawingArea):
    """Interactive keyboard renderer.

    Modes:
      ``actuation`` — per-key travel heat map
      ``rt``        — rapid trigger state
      ``lighting``  — per-key colours
      ``keymap``    — keycode labels
      ``live``      — live travel from the test stream
    """

    def __init__(self, *, height: int = 260, interactive: bool = True,
                 on_key: Callable[[int, int, bool], None] | None = None) -> None:
        super().__init__()
        self.set_content_height(height)
        self.set_size_request(-1, height)
        self.set_draw_func(self._draw)
        self.state = KeyboardState()
        self.mode = "actuation"
        self.selected: set[tuple[int, int]] = set()
        self.travel: list[float] = []
        self.layer = 0
        self.preview_color = (255, 77, 109)
        self.per_key = False
        self._on_key = on_key
        self._interactive = interactive
        self._focused = (0, 0)
        self.set_focusable(interactive)
        if interactive:
            keys = Gtk.EventControllerKey()
            keys.connect("key-pressed", self._key_pressed)
            self.add_controller(keys)
        if not os.environ.get("MADLIONS_NO_TOOLTIPS"):
            self.set_has_tooltip(True)
            self.connect("query-tooltip", self._query_tooltip)
        if interactive:
            gesture = Gtk.GestureClick(button=1)
            gesture.connect("pressed", self._pressed)
            self.add_controller(gesture)
        self.set_cursor(Gdk.Cursor.new_from_name("pointer") if interactive else None)

    # -- public ------------------------------------------------------------
    def set_state(self, state: KeyboardState) -> None:
        self.state = state
        self.queue_draw()

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.queue_draw()

    def set_selection(self, selected: set[tuple[int, int]]) -> None:
        self.selected = set(selected)
        self.queue_draw()

    def set_layer(self, layer: int) -> None:
        self.layer = layer
        self.queue_draw()

    def set_travel(self, travel: list[float]) -> None:
        self.travel = travel
        self.queue_draw()

    def set_lighting_preview(self, color: tuple[int, int, int], per_key: bool) -> None:
        self.preview_color = color
        self.per_key = per_key
        self.queue_draw()

    # -- geometry ----------------------------------------------------------
    def _geometry(self, width: float, height: float):
        rows = layout.layout_for(self.state.board)
        max_units = layout.max_row_width(rows)
        gap = max(3.0, min(4.5, width * 0.005))
        unit_w = (width - 2 * PAD - (max_units - 1) * gap) / max_units
        unit_h = (height - 2 * PAD - 4 * gap) / 5
        unit = max(12.0, min(MAX_UNIT, unit_w, unit_h))
        key_h = unit * 0.94
        board_w = max_units * unit + (max_units - 1) * gap
        board_h = 5 * key_h + 4 * gap
        x0 = (width - board_w) / 2
        y0 = (height - board_h) / 2
        return rows, gap, unit, key_h, board_w, board_h, x0, y0

    def _rect_for(self, row: int, col: int) -> tuple[float, float, float, float] | None:
        width = self.get_width()
        height = self.get_height()
        if width <= 1 or height <= 1:
            return None
        rows, gap, unit, key_h, _bw, _bh, x0, y0 = self._geometry(width, height)
        if row >= len(rows):
            return None
        x = x0
        for key in rows[row]:
            if key.col == col:
                return x, y0 + row * (key_h + gap), key.width * unit + (key.width - 1) * gap, key_h
            x += key.width * unit + key.width * gap
        return None

    # -- drawing -----------------------------------------------------------
    def _draw(self, _area: Gtk.DrawingArea, cr: cairo.Context, width: int, height: int) -> None:
        rows, gap, unit, key_h, board_w, board_h, x0, y0 = self._geometry(width, height)
        theme = self.state
        is_dark = True
        try:
            style = self.get_style_context()
            is_dark = style.get_color().red < 0.5
        except Exception:
            pass

        # The keyboard plate.
        _rounded(cr, x0 - 9, y0 - 9, board_w + 18, board_h + 18, 13)
        cr.set_source_rgba(0.035, 0.035, 0.045, 0.72 if is_dark else 0.08)
        cr.fill_preserve()
        cr.set_source_rgba(1, 1, 1, 0.06 if is_dark else 0.18)
        cr.set_line_width(1)
        cr.stroke()

        font_main = unit * 0.30
        font_small = max(7.0, unit * 0.17)

        for row_index, row in enumerate(rows):
            x = x0
            for key in row:
                w = key.width * unit + (key.width - 1) * gap
                y = y0 + row_index * (key_h + gap)
                selected = (key.row, key.col) in self.selected
                press = 0.0
                if self.travel:
                    idx = key.row * theme.board.cols + key.col
                    if 0 <= idx < len(self.travel):
                        press = self.travel[idx]

                fill_top = (0.155, 0.155, 0.185)
                fill_bottom = (0.082, 0.082, 0.100)
                border = (0.24, 0.24, 0.30)
                text = (0.92, 0.92, 0.97)
                sub = (0.57, 0.57, 0.64)

                if self.mode == "lighting":
                    if self.per_key and theme.colors:
                        idx = key.row * theme.board.cols + key.col
                        base = (theme.colors[idx] if idx < len(theme.colors)
                                else self.preview_color)
                    else:
                        base = self.preview_color
                    fill_top = tuple(value / 255 for value in base)
                    fill_bottom = tuple(max(0.0, value / 255 * 0.62) for value in base)
                    border = tuple(min(1.0, value / 255 + 0.16) for value in base)
                    text = (0.05, 0.05, 0.07) if _lum(base) > 0.58 else (1.0, 1.0, 1.0)
                    sub = (0.10, 0.10, 0.12) if _lum(base) > 0.58 else (0.85, 0.85, 0.85)
                elif press > 0.02:
                    heat = heat_color(press / 3.4)
                    fill_top = tuple(value / 255 for value in heat)
                    fill_bottom = tuple(value / 255 * 0.55 for value in heat)
                    border = tuple(min(1.0, value / 255 + 0.22) for value in heat)
                    text = (1.0, 1.0, 1.0)
                    sub = (1.0, 1.0, 1.0)

                gradient = cairo.LinearGradient(x, y, x, y + key_h)
                gradient.add_color_stop_rgb(0, *fill_top)
                gradient.add_color_stop_rgb(1, *fill_bottom)
                _rounded(cr, x, y, w, key_h, min(7, key_h * 0.18))
                cr.set_source(gradient)
                cr.fill_preserve()
                cr.set_source_rgba(*border, 0.9)
                cr.set_line_width(1)
                cr.stroke()

                # Thin top highlight keeps the caps from looking flat.
                cr.set_source_rgba(1, 1, 1, 0.07 if self.mode != "lighting" else 0.12)
                _rounded(cr, x + 2, y + 1.5, w - 4, key_h * 0.38, min(6, key_h * 0.16))
                cr.fill()

                main_text = key.label
                sub_text = key.legend
                if self.mode == "keymap":
                    code = theme.keycode_at(self.layer, key.row, key.col)
                    resolved = keycodes.lookup(code)
                    main_text = resolved.label
                    sub_text = key.label if resolved.label != key.label else ""
                    if code == keycodes.KC_TRNS:
                        cr.set_source_rgba(0.5, 0.5, 0.56, 0.55)
                        _rounded(cr, x, y, w, key_h, min(7, key_h * 0.18))
                        cr.fill()
                elif self.mode in ("actuation", "rt") and theme.actuation:
                    idx = key.row * theme.board.cols + key.col
                    if self.mode == "actuation" and idx < len(theme.actuation):
                        value = theme.actuation[idx]
                        t = max(0.0, min(1.0, (value - 0.05) / 3.35))
                        strip = heat_color(t)
                        cr.set_source_rgb(*(channel / 255 for channel in strip))
                        _rounded(cr, x + 4, y + key_h - 6, w - 8, 2.6, 1.3)
                        cr.fill()
                    if self.mode == "rt":
                        rt = theme.rt_of(key.row, key.col)
                        if rt.enabled:
                            cr.set_source_rgba(1.0, 0.30, 0.42, 0.92)
                            _rounded(cr, x + 4, y + key_h - 6, w - 8, 2.6, 1.3)
                            cr.fill()
                        else:
                            cr.set_source_rgba(0.5, 0.5, 0.56, 0.22)
                            _rounded(cr, x + 4, y + key_h - 6, w - 8, 2.6, 1.3)
                            cr.fill()

                if selected:
                    _rounded(cr, x - 1.5, y - 1.5, w + 3, key_h + 3, min(8, key_h * 0.22))
                    cr.set_source_rgba(1.0, 0.30, 0.42, 0.92)
                    cr.set_line_width(2)
                    cr.stroke()
                if self.has_focus() and (key.row, key.col) == self._focused:
                    cr.set_dash([3, 2])
                    _rounded(cr, x - 4, y - 4, w + 8, key_h + 8, min(9, key_h * 0.24))
                    cr.set_source_rgba(1.0, 1.0, 1.0, 0.65)
                    cr.set_line_width(1.4)
                    cr.stroke()
                    cr.set_dash([])

                if self.mode == "live" and press > 0.02:
                    # A fill from the bottom makes the analogue travel legible.
                    fill_h = max(2.0, key_h * min(1.0, press / 3.4))
                    cr.save()
                    _rounded(cr, x, y, w, key_h, min(7, key_h * 0.18))
                    cr.clip()
                    cr.set_source_rgba(1, 1, 1, 0.14)
                    cr.rectangle(x, y + key_h - fill_h, w, fill_h)
                    cr.fill()
                    cr.restore()

                _text(cr, main_text, x + 2, y, w - 4, key_h * 0.72, font_main, text,
                      Pango.Weight.SEMIBOLD)
                if sub_text and key_h > 28:
                    _text(cr, sub_text, x + 2, y + key_h * 0.55, w - 4, key_h * 0.42,
                          font_small, sub)

                if self.mode == "actuation" and theme.actuation and key_h > 40:
                    idx = key.row * theme.board.cols + key.col
                    if idx < len(theme.actuation):
                        _text(cr, f"{theme.actuation[idx]:.2f}", x, y + key_h - 19,
                              w - 4, key_h * 0.3, font_small, sub, Pango.Weight.BOLD)
                if self.mode == "rt" and theme.rapid_trigger and key_h > 40:
                    rt = theme.rt_of(key.row, key.col)
                    if rt.enabled:
                        _text(cr, f"{rt.press_mm:.2f}", x, y + key_h - 19, w - 4,
                              key_h * 0.3, font_small, sub, Pango.Weight.BOLD)

                x += w + gap

        # Small brand mark on the plate, kept subtle.
        if board_h > 140:
            _text(cr, "MADLIONS", x0, y0 + board_h + 2, board_w, 10,
                  max(6.5, unit * 0.15), (0.55, 0.55, 0.62,))

    def _pressed(self, gesture: Gtk.GestureClick, _n: int, x: float, y: float) -> None:
        rows, gap, unit, key_h, _bw, _bh, x0, y0 = self._geometry(self.get_width(), self.get_height())
        row = int((y - y0) // (key_h + gap))
        if row < 0 or row >= len(rows):
            return
        local_x = x - x0
        if local_x < 0:
            return
        cursor = x0
        for key in rows[row]:
            w = key.width * unit + (key.width - 1) * gap
            if cursor <= x <= cursor + w:
                state = gesture.get_current_event_state()
                ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
                self._focused = (key.row, key.col)
                self.grab_focus()
                if self._on_key:
                    self._on_key(key.row, key.col, ctrl)
                return
            cursor += w + gap

    def _physical_keys(self) -> list:
        return sorted(
            layout.keys_for(self.state.board),
            key=lambda key: (key.row, key.col),
        )

    def _key_pressed(self, _controller, keyval: int, _keycode: int, state) -> bool:
        keys = self._physical_keys()
        if not keys:
            return False
        current = next(
            (key for key in keys if (key.row, key.col) == self._focused),
            keys[0],
        )
        if keyval in (Gdk.KEY_Left, Gdk.KEY_Right, Gdk.KEY_Up, Gdk.KEY_Down):
            if keyval in (Gdk.KEY_Left, Gdk.KEY_Right):
                candidates = [key for key in keys if key.row == current.row]
                candidates.sort(key=lambda key: key.col, reverse=keyval == Gdk.KEY_Left)
                target = next(
                    (key for key in candidates
                     if (key.col < current.col if keyval == Gdk.KEY_Left
                         else key.col > current.col)),
                    current,
                )
            else:
                candidates = [key for key in keys if key.col == current.col]
                candidates.sort(key=lambda key: key.row, reverse=keyval == Gdk.KEY_Up)
                target = next(
                    (key for key in candidates
                     if (key.row < current.row if keyval == Gdk.KEY_Up
                         else key.row > current.row)),
                    current,
                )
            self._focused = (target.row, target.col)
            self.queue_draw()
            return True
        if keyval in (Gdk.KEY_space, Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
            if self._on_key:
                self._on_key(current.row, current.col, ctrl)
            return True
        return False

    def _query_tooltip(self, _widget, x: int, y: int, _keyboard, tooltip: Gtk.Tooltip) -> bool:
        rows, gap, unit, key_h, _bw, _bh, x0, y0 = self._geometry(self.get_width(), self.get_height())
        row = int((y - y0) // (key_h + gap))
        if row < 0 or row >= len(rows):
            return False
        cursor = x0
        for key in rows[row]:
            w = key.width * unit + (key.width - 1) * gap
            if cursor <= x <= cursor + w:
                lines = [f"{key.label}  (row {key.row}, col {key.col})"]
                if self.state.actuation:
                    lines.append(f"Actuation {self.state.actuation_of(key.row, key.col):.2f} mm")
                rt = self.state.rt_of(key.row, key.col)
                lines.append(
                    f"Rapid trigger {'on' if rt.enabled else 'off'} · "
                    f"{rt.press_mm:.2f}/{rt.release_mm:.2f} mm"
                )
                if self.mode == "keymap":
                    lines.append(
                        f"Layer {self.layer}: {keycodes.name(self.state.keycode_at(self.layer, key.row, key.col))}"
                    )
                tooltip.set_text("\n".join(lines))
                return True
            cursor += w + gap
        return False
