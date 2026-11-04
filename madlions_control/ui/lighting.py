"""Lighting and per-key colour editor."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Pango", "1.0")

from gi.repository import Gdk, Gtk, Pango  # noqa: E402

from ..device import BoxLight, LightInfo
from ..lighting import (
    BRIGHTNESS_MAX,
    DEFAULT_SPEED,
    EFFECTS,
    SPEED_MAX,
    SPEED_MIN,
    effect as find_effect,
    effective_color,
    rgb_to_hex,
)
from .color_picker import ColorPickerDialog, ColorPreview
from .keyboard import KeyboardCanvas
from .widgets import Debouncer, LabeledScale, Page, Section, SwitchRow, button, label, separator, toast


class EffectSwatch(Gtk.DrawingArea):
    def __init__(self, color: tuple[int, int, int] = (255, 77, 109), *, number: int = 2) -> None:
        super().__init__()
        self.set_content_height(20)
        self.set_size_request(60, 18)
        self.color = color
        self.number = number
        self.set_draw_func(self._draw)

    def set_color(self, color: tuple[int, int, int]) -> None:
        self.color = color
        self.queue_draw()

    def _draw(self, _area, cr, w, h):
        import cairo

        effect = find_effect(self.number)
        r, g, b = (component / 255 for component in self.color)
        if effect is None or effect.number == 0:
            cr.set_source_rgba(0.2, 0.2, 0.24, 1)
            cr.rectangle(0, 0, w, h)
            cr.fill()
            cr.set_source_rgba(1, 1, 1, 0.2)
            cr.set_line_width(1.5)
            cr.move_to(3, h - 3)
            cr.line_to(w - 3, 3)
            cr.stroke()
            return
        if effect.uses_color:
            gradient = cairo.LinearGradient(0, 0, w, 0)
            gradient.add_color_stop_rgb(0, r, g, b)
            gradient.add_color_stop_rgb(1, r * 0.35, g * 0.35, b * 0.35 + 0.08)
            cr.set_source(gradient)
        else:
            gradient = cairo.LinearGradient(0, 0, w, 0)
            for step in range(7):
                t = step / 6
                hue = t * 0.82
                rr, gg, bb = _hsv(hue, 0.75, 0.95)
                gradient.add_color_stop_rgb(t, rr, gg, bb)
            cr.set_source(gradient)
        cr.rectangle(0, 0, w, h)
        cr.fill()
        if effect.animated:
            cr.set_source_rgba(1, 1, 1, 0.28)
            for x in range(2, int(w), 9):
                cr.rectangle(x, 3, 2, h - 6)
                cr.fill()


def _hsv(h: float, s: float, v: float) -> tuple[float, float, float]:
    i = int(h * 6)
    f = h * 6 - i
    p, q, t = v * (1 - s), v * (1 - f * s), v * (1 - (1 - f) * s)
    return [
        (v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q)
    ][i % 6]


class LightingPage(Page):
    title = "Lighting"
    subtitle = "Pick an effect, tune it, or paint individual keys."

    def __init__(self, window) -> None:
        super().__init__(window, max_width=1180)
        self._effect_tiles: dict[int, Gtk.Button] = {}
        self._bright_debounce = Debouncer(180, self._apply_light)
        self._speed_debounce = Debouncer(180, self._apply_light)
        self._side_debounce = Debouncer(220, self._apply_side)
        self._suppress = False
        self._build()

    def _build(self) -> None:
        save = button("Save lighting", icon="document-save-symbolic", suggested=True)
        save.connect("clicked", lambda _b: self.window.save_lighting())
        self.add(self.header(save))
        self._writable = True

        self.warning = Section(tight=True)
        self.warning.set_visible(False)
        self.add(self.warning)

        content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        content.set_vexpand(True)

        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        left.set_hexpand(True)

        effects = Section("Effect", "The firmware's own effect set.")
        self.flow = Gtk.FlowBox()
        self.flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self.flow.set_max_children_per_line(3)
        self.flow.set_min_children_per_line(2)
        self.flow.set_homogeneous(True)
        self.flow.set_row_spacing(6)
        self.flow.set_column_spacing(6)
        self.flow.add_css_class("effect-grid")
        for effect in EFFECTS:
            tile = Gtk.Button()
            tile.add_css_class("effect-tile")
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            swatch = EffectSwatch(number=effect.number)
            box.append(swatch)
            effect_label = label(effect.name, "effect-name", wrap=True)
            effect_label.set_max_width_chars(12)
            effect_label.set_ellipsize(Pango.EllipsizeMode.END)
            effect_label.set_xalign(0.0)
            box.append(effect_label)
            tile.set_child(box)
            tile.connect("clicked", lambda _b, number=effect.number: self._choose_effect(number))
            self._effect_tiles[effect.number] = tile
            tile.set_size_request(102, -1)
            child = Gtk.FlowBoxChild()
            child.set_child(tile)
            self.flow.append(child)
        effect_scroller = Gtk.ScrolledWindow()
        effect_scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        effect_scroller.set_min_content_height(280)
        effect_scroller.set_max_content_height(280)
        effect_scroller.set_child(self.flow)
        effects.add(effect_scroller)
        left.append(effects)

        controls = Section("Light")
        self.brightness = LabeledScale(
            "Brightness", 0, BRIGHTNESS_MAX, 1, value=170, unit="",
            subtitle="The firmware's ceiling is 210; higher values are silently dropped.",
            digits=0,
            on_change=lambda _v: self._bright_debounce.trigger(),
        )
        self.speed = LabeledScale(
            "Animation speed", SPEED_MIN, SPEED_MAX, 1, value=DEFAULT_SPEED, unit="",
            subtitle="Only animated effects use this.",
            digits=0,
            on_change=lambda _v: self._speed_debounce.trigger(),
        )
        controls.add(self.brightness)
        controls.add(self.speed)
        color_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        color_row.append(label("Colour", "row-title"))
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        color_row.append(spacer)
        self._color = (255, 77, 109)
        self.color_control = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.color_control.add_css_class("color-control")
        self.color_control.set_tooltip_text("Choose the lighting colour")
        self.color_control.set_cursor(Gdk.Cursor.new_from_name("pointer"))
        self.color_preview = ColorPreview(30, 22)
        self.color_preview.set_size_request(30, 22)
        self.color_preview.set_content_height(22)
        self.color_control.append(self.color_preview)
        self.color_hex = label("#ff4d6d", "mono muted")
        self.color_control.append(self.color_hex)
        self.color_control.append(Gtk.Image.new_from_icon_name("go-next-symbolic"))
        gesture = Gtk.GestureClick()
        gesture.connect("released", lambda *_args: self._open_main_color())
        self.color_control.add_controller(gesture)
        color_row.append(self.color_control)
        controls.add(color_row)
        left.append(controls)
        content.append(left)

        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        right.set_size_request(420, -1)
        preview = Section("Preview")
        self.canvas = KeyboardCanvas(height=200, on_key=self._key_color_clicked)
        self.canvas.set_mode("lighting")
        preview.add(self.canvas)
        per_key_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.custom_note = label(
            "Per-key colours are only visible with the Custom effect.",
            "row-sub", wrap=True,
        )
        self.custom_note.set_hexpand(True)
        per_key_row.append(self.custom_note)
        self.custom_button = button("Use Custom effect", flat=True)
        self.custom_button.connect("clicked", lambda _b: self._choose_effect(1))
        per_key_row.append(self.custom_button)
        preview.add(per_key_row)
        right.append(preview)

        side = Section("Side light", "The light strip around the edge.")
        self.side_card = side
        side_mode_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        side_mode_row.append(label("Mode", "row-title"))
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        side_mode_row.append(spacer)
        self.side_mode = Gtk.DropDown.new_from_strings(
            ["Off", "Mode 1", "Mode 2", "Mode 3", "Mode 4", "Mode 5"]
        )
        self.side_mode.connect("notify::selected", lambda *_a: self._side_debounce.trigger())
        side_mode_row.append(self.side_mode)
        side.add(side_mode_row)
        self.side_colorful = SwitchRow("Multi-colour", "Let the side light cycle through colours.",
                                       on_toggle=lambda _on: self._side_debounce.trigger())
        side.add(self.side_colorful)
        self.side_brightness = LabeledScale(
            "Brightness", 0, 255, 1, value=130, digits=0,
            on_change=lambda _v: self._side_debounce.trigger()
        )
        self.side_speed = LabeledScale(
            "Speed", 0, 255, 1, value=120, digits=0,
            on_change=lambda _v: self._side_debounce.trigger()
        )
        side.add(self.side_brightness)
        side.add(self.side_speed)
        right.append(side)
        content.append(right)
        self.add(content)

    # -- state -------------------------------------------------------------
    def on_show(self) -> None:
        state = self.window.state
        if state.connected and not state.colors:
            self.window.worker.refresh_colors(
                callback=lambda loaded: self.window.set_state_local(loaded)
            )

    def on_state(self, state) -> None:
        self.canvas.set_state(state)
        self.side_card.set_visible(bool(state.board.side_light) or self.window.demo)
        self._writable = state.writable
        if not state.connected:
            self._show_warning("Connect a keyboard to change lighting.")
        elif not state.writable:
            self._show_warning(
                "Read-only session. Lighting can be previewed but not changed."
            )
        else:
            self.warning.set_visible(False)
        self._suppress = True
        try:
            light = state.light
            self.brightness.set_value(light.brightness)
            self.speed.set_value(light.speed or DEFAULT_SPEED)
            color = effective_color(light.r, light.g, light.b)
            self._color = color
            self.color_preview.set_color(color)
            self.color_hex.set_text(rgb_to_hex(color))
            self._highlight_effect(light.effect)
            effect = find_effect(light.effect)
            self.speed.set_sensitive(bool(effect and effect.animated) and state.writable)
            self.brightness.set_sensitive(state.writable)
            self.color_control.set_sensitive(state.writable)
            for tile in self._effect_tiles.values():
                tile.set_sensitive(state.writable)
            self.side_mode.set_sensitive(state.writable)
            self.side_colorful.set_sensitive(state.writable)
            self.side_brightness.set_sensitive(state.writable)
            self.side_speed.set_sensitive(state.writable)
            self.side_mode.set_selected(min(max(state.box_light.mode, 0), 5))
            self.side_colorful.set_active(bool(state.box_light.colorful))
            self.side_brightness.set_value(state.box_light.brightness)
            self.side_speed.set_value(state.box_light.speed)
            if effect and effect.number == 1:
                self.custom_note.set_text(
                    "Click a key on the preview to choose its colour."
                )
                self.custom_button.set_visible(False)
            else:
                self.custom_note.set_text(
                    "Per-key colours are only visible with the Custom effect."
                )
                self.custom_button.set_visible(state.writable)
        finally:
            self._suppress = False
        self._refresh_preview()

    def _open_main_color(self) -> None:
        if not self._writable:
            self.window.notify("The session is read-only.")
            return
        ColorPickerDialog(self._color, self._set_main_color, title="Lighting colour").present(self.window)

    def _set_main_color(self, color: tuple[int, int, int]) -> None:
        if not self._writable:
            return
        self._color = color
        self.color_preview.set_color(color)
        self.color_hex.set_text(rgb_to_hex(color))
        self._apply_light()

    def _highlight_effect(self, number: int) -> None:
        for effect_number, tile in self._effect_tiles.items():
            if effect_number == number:
                tile.add_css_class("active")
            else:
                tile.remove_css_class("active")

    def _show_warning(self, text: str) -> None:
        while child := self.warning.content.get_first_child():
            self.warning.content.remove(child)
        self.warning.set_visible(True)
        self.warning.add(label(text, "warning-box", wrap=True))

    def _refresh_preview(self) -> None:
        state = self.window.state
        effect = find_effect(state.light.effect)
        if state.light.effect == 0:
            color = (26, 26, 32)
        else:
            color = effective_color(state.light.r, state.light.g, state.light.b)
        per_key = bool(effect and effect.number == 1)
        self.canvas.set_lighting_preview(color, per_key)

    # -- edits -------------------------------------------------------------
    def _choose_effect(self, number: int) -> None:
        if not self._writable:
            self.window.notify("The session is read-only.")
            return
        state = self.window.state
        light = LightInfo(
            effect=number,
            speed=self.speed.scale.get_value() if find_effect(number) and find_effect(number).animated else 0,
            r=state.light.r,
            g=state.light.g,
            b=state.light.b,
            brightness=min(int(self.brightness.scale.get_value()), BRIGHTNESS_MAX),
        )
        from dataclasses import replace

        self.window.set_state_local(replace(self.window.state, light=light))
        self._highlight_effect(number)
        effect = find_effect(number)
        self.speed.set_sensitive(bool(effect and effect.animated))
        self._apply_light()

    def _apply_light(self) -> None:
        if self._suppress or not self._writable:
            return
        state = self.window.state
        effect_number = state.light.effect
        effect = find_effect(effect_number)
        r, g, b = self._color
        light = LightInfo(
            effect=effect_number,
            speed=int(self.speed.scale.get_value()) if effect and effect.animated else 0,
            r=r,
            g=g,
            b=b,
            brightness=min(int(self.brightness.scale.get_value()), BRIGHTNESS_MAX),
        )
        self.window.set_state_local(_replace_light(self.window.state, light))
        self._refresh_preview()

        def job(device):
            device.write_light(light)

        def error(exc):
            self.window.notify(f"Lighting not applied: {exc}")
            self.window.refresh()

        self.window.worker.submit(job, error=error, description="lighting")

    def _key_color_clicked(self, row: int, col: int, ctrl: bool) -> None:
        if not self._writable:
            self.window.notify("The session is read-only.")
            return
        if self.window.state.light.effect != 1:
            self._choose_effect(1)
        state = self.window.state
        index = row * state.board.cols + col
        current = state.colors[index] if index < len(state.colors) else (255, 255, 255)
        ColorPickerDialog(
            current,
            lambda color: self._set_key_color(row, col, color),
            title=f"Colour · row {row}, column {col}",
        ).present(self.window)

    def _set_key_color(self, row: int, col: int, color: tuple[int, int, int]) -> None:
        if not self._writable:
            return
        state = self.window.state
        index = row * state.board.cols + col
        colors = list(state.colors)
        if len(colors) < state.total_keys:
            colors += [(0, 0, 0)] * (state.total_keys - len(colors))
        colors[index] = color
        self.window.set_state_local(_replace_colors(state, colors))
        self.canvas.set_state(self.window.state)
        self._refresh_preview()

        def job(device):
            device.write_key_colors(row, col, [color])

        def error(exc):
            self.window.notify(f"Key colour not applied: {exc}")
            self.window.refresh()

        self.window.worker.submit(job, error=error, description="key colour")

    def _side_changed(self) -> None:
        if self._suppress:
            return
        self._side_debounce.trigger()

    def _apply_side(self) -> None:
        if self._suppress or not self._writable:
            return
        state = self.window.state
        box = BoxLight(
            mode=self.side_mode.get_selected(),
            colorful=1 if self.side_colorful.switch.get_active() else 0,
            brightness=int(self.side_brightness.scale.get_value()),
            speed=int(self.side_speed.scale.get_value()),
        )
        self.window.set_state_local(_replace_side(self.window.state, box))

        def job(device):
            device.write_box_light(box)

        def error(exc):
            self.window.notify(f"Side light not applied: {exc}")

        self.window.worker.submit(job, error=error, description="side light")


def _replace_light(state, light):
    from dataclasses import replace

    return replace(state, light=light)


def _replace_colors(state, colors):
    from dataclasses import replace

    return replace(state, colors=colors)


def _replace_side(state, box):
    from dataclasses import replace

    return replace(state, box_light=box)
