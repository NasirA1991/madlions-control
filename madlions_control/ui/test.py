"""Live analogue key test: travel, thresholds and a short history."""

from __future__ import annotations

import math
import time

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import GLib, Gtk  # noqa: E402

from .. import layout
from ..lighting import heat_color
from .keyboard import KeyboardCanvas
from .widgets import Page, Section, button, label

MAX_TRAVEL = 3.4
HISTORY = 300


class TravelGauge(Gtk.DrawingArea):
    def __init__(self) -> None:
        super().__init__()
        self.set_content_height(220)
        self.set_size_request(340, 220)
        self.set_draw_func(self._draw)
        self.travel = 0.0
        self.actuation = 1.5
        self.rt = None
        self.history: list[float] = []

    def set_data(self, travel: float, actuation: float, rt, history: list[float]) -> None:
        self.travel = travel
        self.actuation = actuation
        self.rt = rt
        self.history = history[-HISTORY:]
        self.queue_draw()

    def _draw(self, _area, cr, width, height):
        import cairo

        top, bottom = 26.0, height - 24.0
        gauge_x, gauge_w = 18.0, 34.0
        chart_x = 110.0
        chart_w = max(20.0, width - chart_x - 10.0)

        cr.set_source_rgba(0.5, 0.5, 0.56, 0.75)
        cr.select_font_face("Cantarell", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(10)

        # Track.
        _rounded(cr, gauge_x, top, gauge_w, bottom - top, 10)
        cr.set_source_rgba(0.5, 0.5, 0.56, 0.12)
        cr.fill()
        ratio = max(0.0, min(1.0, self.travel / MAX_TRAVEL))
        color = heat_color(ratio)
        if ratio > 0.005:
            fill_h = (bottom - top) * ratio
            _rounded(cr, gauge_x, bottom - fill_h, gauge_w, fill_h, 10)
            cr.set_source_rgb(*(value / 255 for value in color))
            cr.fill()
        _rounded(cr, gauge_x, top, gauge_w, bottom - top, 10)
        cr.set_source_rgba(0.5, 0.5, 0.56, 0.28)
        cr.set_line_width(1)
        cr.stroke()

        # Threshold line.
        ay = bottom - (bottom - top) * (self.actuation / MAX_TRAVEL)
        cr.set_dash([3, 3])
        cr.set_source_rgba(1.0, 0.30, 0.42, 0.9)
        cr.set_line_width(1.4)
        cr.move_to(gauge_x - 4, ay)
        cr.line_to(gauge_x + gauge_w + 8, ay)
        cr.stroke()
        cr.set_dash([])
        cr.set_source_rgba(1.0, 0.45, 0.55, 0.95)
        cr.move_to(gauge_x + gauge_w + 10, ay + 3)
        cr.set_font_size(9)
        cr.show_text(f"{self.actuation:.2f}")

        # Current travel value.
        cr.set_source_rgba(0.9, 0.9, 0.94, 0.95)
        cr.set_font_size(20)
        cr.move_to(gauge_x - 2, top - 8)
        cr.show_text(f"{self.travel:.2f}")
        cr.set_font_size(9)
        cr.set_source_rgba(0.55, 0.55, 0.62, 1)
        cr.move_to(gauge_x + 47, top - 8)
        cr.show_text("mm")

        # History chart.
        cr.set_source_rgba(0.5, 0.5, 0.56, 0.10)
        _rounded(cr, chart_x, top, chart_w, bottom - top, 9)
        cr.fill()
        for step in range(1, 4):
            y = bottom - (bottom - top) * (step * 1.0 / MAX_TRAVEL)
            cr.set_source_rgba(0.5, 0.5, 0.56, 0.08)
            cr.move_to(chart_x, y)
            cr.line_to(chart_x + chart_w, y)
            cr.stroke()
        ay_chart = bottom - (bottom - top) * (self.actuation / MAX_TRAVEL)
        cr.set_dash([4, 4])
        cr.set_source_rgba(1.0, 0.30, 0.42, 0.55)
        cr.move_to(chart_x, ay_chart)
        cr.line_to(chart_x + chart_w, ay_chart)
        cr.stroke()
        cr.set_dash([])
        if len(self.history) > 1:
            step = chart_w / max(1, HISTORY - 1)
            start = max(0, HISTORY - len(self.history))
            points = []
            for index, value in enumerate(self.history):
                x = chart_x + (start + index) * step
                y = bottom - (bottom - top) * min(1.0, value / MAX_TRAVEL)
                points.append((x, y))
            gradient = cairo.LinearGradient(chart_x, 0, chart_x + chart_w, 0)
            gradient.add_color_stop_rgb(0.0, 0.32, 0.48, 1.0)
            gradient.add_color_stop_rgb(0.55, 0.43, 0.86, 0.80)
            gradient.add_color_stop_rgb(1.0, 1.0, 0.30, 0.42)
            cr.set_source(gradient)
            cr.set_line_width(1.8)
            cr.move_to(*points[0])
            for point in points[1:]:
                cr.line_to(*point)
            cr.stroke()
            cr.line_to(points[-1][0], bottom)
            cr.line_to(points[0][0], bottom)
            cr.close_path()
            fill = cairo.LinearGradient(0, top, 0, bottom)
            fill.add_color_stop_rgba(0, 1.0, 0.30, 0.42, 0.16)
            fill.add_color_stop_rgba(1, 1.0, 0.30, 0.42, 0.0)
            cr.set_source(fill)
            cr.fill()

        cr.set_source_rgba(0.5, 0.5, 0.56, 0.8)
        cr.set_font_size(9)
        cr.move_to(chart_x, top + 12)
        cr.show_text("last 5 seconds")
        cr.move_to(chart_x, bottom + 14)
        cr.show_text("0 mm")
        cr.move_to(chart_x + chart_w - 34, bottom + 14)
        cr.show_text(f"{MAX_TRAVEL:.1f} mm")


def _rounded(cr, x, y, w, h, r):
    r = min(r, w / 2, h / 2)
    cr.new_path()
    cr.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
    cr.arc(x + w - r, y + r, r, 1.5 * math.pi, 2 * math.pi)
    cr.arc(x + w - r, y + h - r, r, 0, 0.5 * math.pi)
    cr.arc(x + r, y + h - r, r, 0.5 * math.pi, math.pi)
    cr.close_path()


class TestPage(Page):
    title = "Test"
    subtitle = "See the analogue travel of every key, live."

    def __init__(self, window) -> None:
        super().__init__(window, max_width=1260)
        self.selected = (2, 1)
        self.history: list[float] = []
        self.frame_count = 0
        self.last_frame_time = 0.0
        self._idle = False
        self.scan_hz = 0.0
        self.peak = 0.0
        self.pressed_max = 0
        self._running = False
        self._build()

    def _build(self) -> None:
        self.toggle = Gtk.Button()
        toggle_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.toggle_icon = Gtk.Image.new_from_icon_name("media-playback-start-symbolic")
        self.toggle_label = label("Start")
        toggle_box.append(self.toggle_icon)
        toggle_box.append(self.toggle_label)
        self.toggle.set_child(toggle_box)
        self.toggle.add_css_class("suggested-action")
        self.toggle.connect("clicked", lambda _b: self._toggle())
        self.add(self.header(self.toggle))

        info = label(
            "Travel comes from the keyboard's own linearised sensor stream and is "
            "read-only. Use it to check thresholds, spot a noisy switch, or just "
            "watch your typing.",
            "info-box", wrap=True,
        )
        self.add(info)

        self.canvas = KeyboardCanvas(height=300, on_key=self._key_clicked)
        self.canvas.set_mode("live")
        self.canvas.set_selection({self.selected})
        self.add(self.canvas)
        legend = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        legend.append(label("released", "tiny muted"))
        for value in (0.0, 0.25, 0.5, 0.75, 1.0):
            swatch = Gtk.Box()
            swatch.set_size_request(26, 6)
            hex_color = heat_color(value)
            css = Gtk.CssProvider()
            css.load_from_data(
                f"box {{ background: rgb({hex_color[0]},{hex_color[1]},{hex_color[2]});"
                f" border-radius: 3px; }}".encode()
            )
            swatch.get_style_context().add_provider(css, 800)
            legend.append(swatch)
        legend.append(label(f"{MAX_TRAVEL:.1f} mm", "tiny muted"))
        self.scan_label = label("Idle", "tiny muted")
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        legend.append(spacer)
        legend.append(self.scan_label)
        self.add(legend)

        content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)

        gauge_card = Section("Selected key", "Click a key above to follow it.")
        gauge_card.set_size_request(350, -1)
        self.key_title = label("A", "section-title")
        self.key_sub = label("row 2, column 1", "tiny muted")
        gauge_card.add(self.key_title)
        gauge_card.add(self.key_sub)
        self.gauge = TravelGauge()
        gauge_card.add(self.gauge)
        self.value_label = label("0.00 mm", "value-big")
        self.state_label = label("Released", "pill")
        state_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        state_row.append(self.value_label)
        state_row.append(self.state_label)
        gauge_card.add(state_row)
        content.append(gauge_card)
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        right.set_hexpand(True)

        self.details = {}
        details = Section("Key settings", "Thresholds currently on the keyboard.")
        for name in ("Actuation", "Rapid trigger", "Press / release"):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            row.add_css_class("list-row")
            row.append(label(name, "row-sub"))
            value = label("—", "row-title", xalign=1.0)
            value.set_hexpand(True)
            value.set_xalign(1.0)
            row.append(value)
            self.details[name] = value
            details.add(row)
        details.add(label(
            "Travel is reported by the keyboard's own linearised sensor stream.",
            "tiny muted", wrap=True,
        ))
        right.append(details)

        stats = Section("Session", "Measured while you watch; nothing leaves this app.")
        self.stat_hz = self._stat_row(stats, "Update rate")
        self.stat_frames = self._stat_row(stats, "Frames")
        self.stat_pressed = self._stat_row(stats, "Keys pressed")
        self.stat_peak = self._stat_row(stats, "Peak travel")
        right.append(stats)
        content.append(right)
        self.add(content)

    def _stat_row(self, section: Section, name: str):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row.add_css_class("list-row")
        row.append(label(name, "row-sub"))
        value = label("—", "row-title", xalign=1.0)
        value.set_hexpand(True)
        value.set_xalign(1.0)
        row.append(value)
        section.add(row)
        return value

    # -- streaming ---------------------------------------------------------
    def on_show(self) -> None:
        self.canvas.set_state(self.window.state)
        if self.window.state.connected and not self._running:
            self._start()

    def on_hide(self) -> None:
        self._stop()

    def _toggle(self) -> None:
        if self._running:
            self._stop()
        else:
            self._start()

    def _start(self) -> None:
        if not self.window.state.connected:
            self.window.notify("Connect a keyboard first.")
            return
        self._running = True
        self.history.clear()
        self.frame_count = 0
        self.last_frame_time = 0.0
        self._idle = False
        self.scan_hz = 0.0
        self.peak = 0.0
        self.pressed_max = 0
        self.toggle_label.set_text("Pause")
        self.toggle_icon.set_from_icon_name("media-playback-pause-symbolic")
        self.window.worker.start_stream(self._frame)
        self.scan_label.set_text("Streaming…")

    def _stop(self) -> None:
        self._running = False
        self.window.worker.stop_stream()
        self.toggle_label.set_text("Start")
        self.toggle_icon.set_from_icon_name("media-playback-start-symbolic")
        self.scan_label.set_text("Idle")

    def _frame(self, frame: list[float]) -> None:
        if not self._running:
            return
        now = time.monotonic()
        if self.last_frame_time:
            delta = now - self.last_frame_time
            if delta > 0:
                instant = 1.0 / delta
                self.scan_hz = instant if not self.scan_hz else self.scan_hz * 0.85 + instant * 0.15
        self.last_frame_time = now
        self.frame_count += 1

        # An idle board sends the same all-zero frame forever.  Do not repaint
        # the canvas/gauge at 60 Hz when nothing is happening; repaint once on
        # the transition to idle, then stay quiet until a key moves.
        active = any(value > 0.005 for value in frame)
        if not active and self._idle:
            if self.frame_count % 60 == 0:
                self.stat_frames.set_text(str(self.frame_count))
            return
        self._idle = not active

        self.canvas.set_travel(frame)
        state = self.window.state
        row, col = self.selected
        index = row * state.board.cols + col
        travel = frame[index] if 0 <= index < len(frame) else 0.0
        self.history.append(travel)
        if len(self.history) > HISTORY:
            del self.history[:-HISTORY]
        self.peak = max(self.peak, travel)
        pressed = sum(1 for value in frame if value > 0.03)
        self.pressed_max = max(self.pressed_max, pressed)
        self.gauge.set_data(travel, state.actuation_of(row, col), state.rt_of(row, col), self.history)
        self.value_label.set_text(f"{travel:.2f} mm")
        if travel > 0.02:
            self.state_label.set_text("Pressed")
            self.state_label.remove_css_class("gray")
            self.state_label.add_css_class("green")
        else:
            self.state_label.set_text("Released")
            self.state_label.remove_css_class("green")
            self.state_label.add_css_class("gray")
        if self.frame_count % 4 == 0:
            self.stat_hz.set_text(f"{self.scan_hz:.0f} Hz")
            self.stat_frames.set_text(str(self.frame_count))
            self.stat_pressed.set_text(str(self.pressed_max))
            self.stat_peak.set_text(f"{self.peak:.2f} mm")

    def stream_error(self, message: str) -> None:
        self._stop()
        self.window.notify(f"Live stream stopped: {message}")

    # -- state -------------------------------------------------------------
    def on_state(self, state) -> None:
        self.canvas.set_state(state)
        if not state.connected and self._running:
            self._stop()
        if (state.connected and not self._running
                and self.window._current_page == "test"):
            self._start()
        row, col = self.selected
        key = layout.key_at(state.board, row, col)
        self.key_title.set_text(key.label if key else f"{row},{col}")
        self.key_sub.set_text(f"row {row}, column {col}")
        self.canvas.set_selection({self.selected})
        if state.actuation:
            self.details["Actuation"].set_text(f"{state.actuation_of(row, col):.2f} mm")
            rt = state.rt_of(row, col)
            self.details["Rapid trigger"].set_text("On" if rt.enabled else "Off")
            self.details["Press / release"].set_text(
                f"{rt.press_mm:.2f} / {rt.release_mm:.2f} mm" if rt.enabled else "—"
            )
            self.gauge.set_data(self.history[-1] if self.history else 0.0,
                                state.actuation_of(row, col), rt, self.history)
        if not self._running:
            self.scan_label.set_text("Idle")

    def _key_clicked(self, row: int, col: int, _ctrl: bool) -> None:
        self.selected = (row, col)
        self.history.clear()
        self.window.worker.stop_stream()
        if self._running:
            self.window.worker.start_stream(self._frame)
        self.on_state(self.window.state)
        self.canvas.set_selection({self.selected})
