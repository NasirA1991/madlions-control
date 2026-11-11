"""Per-key actuation and rapid-trigger editor."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk  # noqa: E402

from .. import layout
from ..device import DEFAULT_ACTUATION_MM, RapidTrigger, clamp_travel
from ..lighting import heat_color
from .keyboard import KeyboardCanvas
from .widgets import (
    Debouncer,
    LabeledScale,
    Page,
    Section,
    SwitchRow,
    button,
    label,
    separator,
    toast,
)


class GradientBar(Gtk.DrawingArea):
    def __init__(self, width: int = 180) -> None:
        super().__init__()
        self.set_content_height(7)
        self.set_size_request(width, 7)
        self.set_draw_func(self._draw)

    def _draw(self, _area, cr, w, h):
        import cairo

        gradient = cairo.LinearGradient(0, 0, w, 0)
        for step in range(9):
            t = step / 8
            r, g, b = heat_color(t)
            gradient.add_color_stop_rgb(t, r / 255, g / 255, b / 255)
        cr.set_source(gradient)
        cr.rectangle(0, 0, w, h)
        cr.fill()


class PerKeyPage(Page):
    title = "Per-key"
    subtitle = "Give every key its own travel and rapid-trigger feel."

    def __init__(self, window) -> None:
        super().__init__(window, max_width=1260)
        self.mode = "actuation"
        self.selected: set[tuple[int, int]] = set()
        self._suppress = False
        self._actuation_debounce = Debouncer(220, self._apply_actuation)
        self._rt_debounce = Debouncer(220, self._apply_rt)
        self._build()

    def _build(self) -> None:
        save = button("Save to keyboard", icon="document-save-symbolic", suggested=True)
        save.connect("clicked", lambda _b: self.window.save_to_keyboard())
        self.add(self.header(save))

        self.warning = Section(tight=True)
        self.warning.set_visible(False)
        self.add(self.warning)

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.mode_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.btn_act = Gtk.Button(label="Actuation")
        self.btn_act.add_css_class("layer-btn")
        self.btn_act.connect("clicked", lambda _b: self._set_mode("actuation"))
        self.btn_rt = Gtk.Button(label="Rapid trigger")
        self.btn_rt.add_css_class("layer-btn")
        self.btn_rt.connect("clicked", lambda _b: self._set_mode("rt"))
        self.mode_box.append(self.btn_act)
        self.mode_box.append(self.btn_rt)
        toolbar.append(self.mode_box)
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        toolbar.append(spacer)
        self.select_all_btn = button("Select all", icon="object-select-symbolic")
        self.select_all_btn.connect("clicked", lambda _b: self._select_all())
        clear = button("Clear", icon="edit-clear-symbolic", flat=True)
        clear.connect("clicked", lambda _b: self._clear_selection())
        toolbar.append(self.select_all_btn)
        toolbar.append(clear)
        self.add(toolbar)

        self.canvas = KeyboardCanvas(height=300, on_key=self._key_clicked)
        self.add(self.canvas)
        legend = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        legend.append(label("0.05 mm", "tiny muted"))
        bar = GradientBar()
        bar.set_hexpand(True)
        legend.append(bar)
        legend.append(label("3.40 mm", "tiny muted"))
        self.add(legend)
        self.legend_hint = label(
            "Colour shows the actuation point of each key. Click a key to edit it, "
            "or Ctrl-click to build a selection.",
            "tiny muted", wrap=True,
        )
        self.add(self.legend_hint)

        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)

        selection = Section("Selection", "Edit one key or a group at once.")
        self.selection_label = label("No keys selected", "section-title")
        self.selection_hint = label("Click a key on the board to start.", "tiny muted", wrap=True)
        selection.add(self.selection_label)
        selection.add(self.selection_hint)
        selection.add(label(
            "Edits are applied live. “Save to keyboard” keeps them after unplugging.",
            "tiny muted", wrap=True,
        ))
        controls.append(selection)

        actuation = Section("Actuation point", "How far a key travels before it registers.")
        self.actuation_scale = LabeledScale(
            "Travel", 0.05, 3.40, 0.01, value=1.50, unit=" mm",
            on_change=self._actuation_changed,
        )
        actuation.add(self.actuation_scale)
        presets = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        presets.add_css_class("flow-tight")
        for value in (0.10, 0.50, 1.00, 1.50, 2.00, 3.00):
            chip = Gtk.Button(label=f"{value:.2f}")
            chip.add_css_class("preset-chip")
            chip.set_tooltip_text(f"Set {value:.2f} mm")
            chip.connect(
                "clicked",
                lambda _b, v=value: self.actuation_scale.set_value(v, notify=True),
            )
            presets.append(chip)
        actuation.add(presets)
        reset = button("Reset selection to 1.50 mm", flat=True)
        reset.connect(
            "clicked",
            lambda _b: self.actuation_scale.set_value(1.50, notify=True),
        )
        actuation.add(reset)
        controls.append(actuation)

        rapid = Section("Rapid trigger", "Reset on the way up instead of at a fixed point.")
        self.rt_switch = SwitchRow(
            "Enable on selection",
            "The key releases as soon as it moves back up.",
            on_toggle=self._rt_toggled,
        )
        rapid.add(self.rt_switch)
        self.rt_press = LabeledScale(
            "Press sensitivity", 0.01, 3.40, 0.01, value=0.50, unit=" mm",
            subtitle="Travel needed to trigger again after a reset.",
            on_change=lambda _v: self._rt_changed(),
        )
        self.rt_release = LabeledScale(
            "Release sensitivity", 0.01, 3.40, 0.01, value=0.50, unit=" mm",
            subtitle="Upward movement that releases the key.",
            on_change=lambda _v: self._rt_changed(),
        )
        rapid.add(self.rt_press)
        rapid.add(self.rt_release)
        controls.append(rapid)
        self.add(controls)

        self._update_mode_buttons()
        self._update_panel()

    # -- selection ---------------------------------------------------------
    def _populated(self) -> set[tuple[int, int]]:
        state = self.window.state
        board = state.board
        if not state.calibration:
            return {
                (key.row, key.col)
                for key in layout.keys_for(board)
            }
        out = set()
        for key in layout.keys_for(board):
            index = key.row * board.cols + key.col
            if index < len(state.calibration) and state.calibration[index]:
                out.add((key.row, key.col))
        return out or {(key.row, key.col) for key in layout.keys_for(board)}

    def _select_all(self) -> None:
        self.selected = set(self._populated())
        self._selection_changed()

    def _clear_selection(self) -> None:
        self.selected.clear()
        self._selection_changed()

    def _key_clicked(self, row: int, col: int, ctrl: bool) -> None:
        if (row, col) not in self._populated():
            return
        if ctrl:
            if (row, col) in self.selected:
                self.selected.discard((row, col))
            else:
                self.selected.add((row, col))
        else:
            self.selected = {(row, col)}
        self._selection_changed()

    def _selection_changed(self) -> None:
        self.canvas.set_selection(self.selected)
        self._update_panel()

    def _update_panel(self) -> None:
        state = self.window.state
        count = len(self.selected)
        writable = state.writable
        if not count:
            self.selection_label.set_text("No keys selected")
            self.selection_hint.set_text("Click a key on the board to start. Ctrl-click selects more.")
        else:
            names = []
            for row, col in sorted(self.selected):
                key = layout.key_at(state.board, row, col)
                names.append(key.label if key else f"{row},{col}")
            shown = " · ".join(names[:6])
            if len(names) > 6:
                shown += f"  +{len(names) - 6}"
            self.selection_label.set_text(f"{count} key{'s' if count != 1 else ''} selected")
            self.selection_hint.set_text(shown)

        self._suppress = True
        try:
            if count:
                first = sorted(self.selected)[0]
            else:
                populated = sorted(self._populated())
                first = populated[0] if populated else (0, 0)
            if state.actuation:
                self.actuation_scale.set_value(state.actuation_of(*first))
                rt = state.rt_of(*first)
                self.rt_switch.set_active(rt.enabled)
                self.rt_press.set_value(rt.press_mm)
                self.rt_release.set_value(rt.release_mm)
                if count:
                    values = {round(state.actuation_of(row, col), 2) for row, col in self.selected}
                    if len(values) > 1:
                        self.selection_hint.set_text(self.selection_hint.get_text() + "  ·  mixed actuation")
            self.actuation_scale.set_sensitive(bool(count) and writable)
            self.rt_switch.set_sensitive(bool(count) and writable)
            self.rt_press.set_sensitive(bool(count) and writable and self.rt_switch.switch.get_active())
            self.rt_release.set_sensitive(bool(count) and writable and self.rt_switch.switch.get_active())
        finally:
            self._suppress = False

    # -- mode --------------------------------------------------------------
    def _set_mode(self, mode: str) -> None:
        self.mode = mode
        self.canvas.set_mode(mode)
        self._update_mode_buttons()
        if mode == "actuation":
            self.legend_hint.set_text(
                "Colour shows the actuation point of each key. Click a key to edit it, "
                "or Ctrl-click to build a selection."
            )
        else:
            self.legend_hint.set_text(
                "A pink underline means rapid trigger is on for that key. Click a key "
                "to tune its press and release sensitivity."
            )

    def _update_mode_buttons(self) -> None:
        for btn, mode in ((self.btn_act, "actuation"), (self.btn_rt, "rt")):
            if mode == self.mode:
                btn.add_css_class("active")
            else:
                btn.remove_css_class("active")

    # -- changes -----------------------------------------------------------
    def _actuation_changed(self, value: float) -> None:
        if self._suppress or not self.selected:
            return
        changes = {key: clamp_travel(value) for key in self.selected}
        self.window.set_state_local(self.window.state.with_actuation(changes))
        self._actuation_debounce.trigger()

    def _rt_toggled(self, enabled: bool) -> None:
        if self._suppress:
            return
        self.rt_press.set_sensitive(enabled and bool(self.selected))
        self.rt_release.set_sensitive(enabled and bool(self.selected))
        if not self.selected:
            return
        rt = RapidTrigger(
            enabled=enabled,
            press_mm=self.rt_press.scale.get_value(),
            release_mm=self.rt_release.scale.get_value(),
        )
        changes = {key: rt for key in self.selected}
        self.window.set_state_local(self.window.state.with_rt(changes))
        self._rt_debounce.trigger()

    def _rt_changed(self) -> None:
        if self._suppress or not self.selected:
            return
        rt = RapidTrigger(
            enabled=self.rt_switch.switch.get_active(),
            press_mm=self.rt_press.scale.get_value(),
            release_mm=self.rt_release.scale.get_value(),
        )
        changes = {key: rt for key in self.selected}
        self.window.set_state_local(self.window.state.with_rt(changes))
        self._rt_debounce.trigger()

    def _apply_actuation(self) -> None:
        if not self.selected:
            return
        values = list(self.window.state.actuation)
        if not values:
            return
        selected = set(self.selected)
        cols = self.window.state.board.cols

        def job(device):
            if len(selected) <= 4:
                for row, col in selected:
                    device.write_one_actuation(
                        row, col, values[row * cols + col]
                    )
            else:
                device.write_actuation(values)
            return len(selected)

        def error(exc):
            self.window.notify(f"Actuation not applied: {exc}")
            self.window.refresh()

        self.window.worker.submit(job, error=error, description="actuation")

    def _apply_rt(self) -> None:
        if not self.selected:
            return
        values = list(self.window.state.rapid_trigger)
        if not values:
            return
        selected = set(self.selected)
        cols = self.window.state.board.cols

        def job(device):
            if len(selected) <= 4:
                for row, col in selected:
                    device.write_one_rapid_trigger(
                        row, col, values[row * cols + col]
                    )
            else:
                device.write_rapid_trigger(values)
            return len(selected)

        def error(exc):
            self.window.notify(f"Rapid trigger not applied: {exc}")
            self.window.refresh()

        self.window.worker.submit(job, error=error, description="rapid trigger")

    # -- lifecycle ---------------------------------------------------------
    def on_state(self, state) -> None:
        self.canvas.set_state(state)
        if not state.connected:
            self._show_warning("Connect a keyboard to edit per-key settings.")
            return
        if not state.writable:
            self._show_warning(
                f"Read-only session: {state.info.read_only_reason}. You can still "
                f"browse the values and use the Test page."
            )
        else:
            self.warning.set_visible(False)
        valid = self._populated()
        self.selected &= valid
        self._selection_changed()
        if self.window.demo and not self.selected:
            self.selected = {(2, 1), (2, 2), (2, 3)}
            self._selection_changed()

    def _show_warning(self, text: str) -> None:
        while child := self.warning.content.get_first_child():
            self.warning.content.remove(child)
        self.warning.set_visible(True)
        self.warning.add(label(text, "warning-box", wrap=True))
