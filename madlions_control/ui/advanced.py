"""Performance switches, dead band, advanced keys and diagnostics."""

from __future__ import annotations

from dataclasses import replace

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402

from .. import keycodes, layout
from ..device import (
    AdvancedKey,
    AdvancedMode,
    BoxLight,
    DeadBand,
    Dks,
    DksAction,
    Features,
    TapDance,
)
from .widgets import Debouncer, LabeledScale, Page, Section, SwitchRow, button, label, separator

MODE_NAMES = [
    (None, "Disabled"),
    (AdvancedMode.RS, "Rapid snappy"),
    (AdvancedMode.SOCD, "SOCD — last input wins"),
    (AdvancedMode.SOCD_KEY1, "SOCD — key 1 wins"),
    (AdvancedMode.SOCD_KEY2, "SOCD — key 2 wins"),
    (AdvancedMode.SOCD_BALANCE, "SOCD — neutral"),
    (AdvancedMode.OKS, "OKS — release to activate"),
    ("MT", "Hold / click"),
]


class AdvancedKeyDialog(Adw.Dialog):
    def __init__(self, parent, index: int, current: AdvancedKey, tap: TapDance,
                 on_save) -> None:
        super().__init__()
        self.set_content_width(560)
        self.set_title("Advanced key")
        self._index = index
        self._parent = parent
        self._on_save = on_save
        self._tap = tap

        view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.set_title_widget(Adw.WindowTitle(title=f"Advanced key {index}",
                                                 subtitle="Stored on the keyboard"))
        cancel = Gtk.Button(label="Cancel")
        cancel.connect("clicked", lambda _b: self.close())
        save = Gtk.Button(label="Save")
        save.add_css_class("suggested-action")
        save.connect("clicked", lambda _b: self._save())
        header.pack_start(cancel)
        header.pack_end(save)
        view.add_top_bar(header)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(14)
        box.set_margin_bottom(16)
        box.set_margin_start(18)
        box.set_margin_end(18)

        box.append(label(
            "Advanced keys let one physical key behave differently depending on "
            "what you press alongside or release. The keyboard evaluates these "
            "itself, so they work in games and outside them.",
            "muted small", wrap=True,
        ))
        mode_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        mode_row.append(label("Behaviour", "row-title"))
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        mode_row.append(spacer)
        self.mode = Gtk.DropDown.new_from_strings([name for _value, name in MODE_NAMES])
        for position, (value, _name) in enumerate(MODE_NAMES):
            if value == current.mode:
                self.mode.set_selected(position)
                break
        if not current.active and tap.active:
            self.mode.set_selected(len(MODE_NAMES) - 1)
        self.mode.connect("notify::selected", lambda *_a: self._mode_changed())
        mode_row.append(self.mode)
        box.append(mode_row)

        self.keys_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.options = [
            (key.row, key.col, key.label)
            for key in layout.keys_for(parent.state.board)
        ]
        self.key1 = self._key_dropdown(current.key1_row, current.key1_col)
        self.key2 = self._key_dropdown(current.key2_row, current.key2_col)
        self.keys_box.append(self._labelled("Key 1", self.key1))
        self.keys_box.append(self._labelled("Key 2", self.key2))
        box.append(self.keys_box)

        self.rs_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.rs_value = LabeledScale(
            "Rapid snappy sensitivity", 0.01, 3.40, 0.01,
            value=current.rs_apc_lv / 100 if current.rs_apc_lv else 0.50,
            unit=" mm",
            subtitle="How far the second key has to travel before it takes over.",
        )
        self.rt_switch = SwitchRow(
            "Quick trigger", "Let the key trigger immediately while rapid snap is active.",
        )
        self.rt_switch.set_active(bool(current.rt_sw))
        self.gap_switch = SwitchRow(
            "Gap compensation", "Compensate for a small difference in travel between the two keys.",
        )
        self.gap_switch.set_active(bool(current.gapc_sw))
        self.rs_box.append(self.rs_value)
        self.rs_box.append(self.rt_switch)
        self.rs_box.append(self.gap_switch)
        box.append(self.rs_box)

        self.layer_row = self._labelled(
            "Layer", Gtk.SpinButton.new_with_range(0, 3, 1)
        )
        self.layer_row.get_last_child().set_value(current.layer)
        box.append(self.layer_row)

        self.mt_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.mt_tap = Gtk.Entry()
        self.mt_tap.set_text(keycodes.name(tap.tap) if tap.tap else "Space")
        self.mt_tap.set_placeholder_text("Key code on a tap, e.g. Space")
        self.mt_hold = Gtk.Entry()
        self.mt_hold.set_text(keycodes.name(tap.hold) if tap.hold else "MO(1)")
        self.mt_hold.set_placeholder_text("Key code while held, e.g. MO(1)")
        self.mt_timer = LabeledScale(
            "Hold threshold", 10, 1000, 10, value=tap.timer_ms or 200, unit=" ms",
            subtitle="How long a press has to last before it counts as a hold.",
        )
        self.mt_box.append(self._labelled("Tap sends", self.mt_tap))
        self.mt_box.append(self._labelled("Hold sends", self.mt_hold))
        self.mt_box.append(self.mt_timer)
        box.append(self.mt_box)
        self.error_label = label("", "error", wrap=True)
        self.error_label.set_visible(False)
        box.append(self.error_label)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_vexpand(True)
        scroller.set_child(box)
        view.set_content(scroller)
        self.set_child(view)
        self._mode_changed()

    def _key_dropdown(self, row: int, col: int) -> Gtk.DropDown:
        names = [f"{label_text}  ({key_row},{key_col})"
                 for key_row, key_col, label_text in self.options]
        dropdown = Gtk.DropDown.new_from_strings(names)
        for index, (key_row, key_col, _label) in enumerate(self.options):
            if key_row == row and key_col == col:
                dropdown.set_selected(index)
                break
        return dropdown

    def _labelled(self, text: str, widget: Gtk.Widget) -> Gtk.Box:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        row.append(label(text, "row-title"))
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        row.append(spacer)
        widget.set_hexpand(False)
        row.append(widget)
        return row

    def _mode_changed(self) -> None:
        value = MODE_NAMES[self.mode.get_selected()][0]
        is_mt = value == "MT"
        is_rs = value == AdvancedMode.RS
        self.keys_box.set_visible(value is not None and not is_mt)
        self.rs_box.set_visible(is_rs)
        self.layer_row.set_visible(value is not None and not is_mt)
        self.mt_box.set_visible(is_mt)

    def _show_error(self, message: str) -> None:
        self.error_label.set_text(message)
        self.error_label.set_visible(True)

    def _save(self) -> None:
        value = MODE_NAMES[self.mode.get_selected()][0]
        row1, col1 = self.options[self.key1.get_selected()][:2] if self.options else (0, 0)
        row2, col2 = self.options[self.key2.get_selected()][:2] if self.options else (0, 0)
        if value == "MT":
            if self._index >= 8:
                self._show_error(
                    "Hold / click is only available for slots 0–7. "
                    "Choose a different behaviour for this slot."
                )
                return
            tap = keycodes.from_name(self.mt_tap.get_text())
            hold = keycodes.from_name(self.mt_hold.get_text())
            if tap is None or not self.mt_tap.get_text().strip():
                self._show_error("Tap must be a valid key name, for example Space.")
                return
            if hold is None or not self.mt_hold.get_text().strip():
                self._show_error("Hold must be a valid key name, for example MO(1).")
                return
            self._on_save("tap", TapDance(
                index=self._index,
                tap=tap,
                hold=hold,
                timer_ms=int(self.mt_timer.scale.get_value()),
            ))
        elif value is None:
            self._on_save("advanced", AdvancedKey(index=self._index))
        else:
            self._on_save("advanced", AdvancedKey(
                index=self._index,
                mode=value,
                key1_row=row1,
                key1_col=col1,
                key2_row=row2,
                key2_col=col2,
                rs_apc_lv=int(self.rs_value.scale.get_value() * 100),
                rt_sw=1 if self.rt_switch.switch.get_active() else 0,
                gapc_sw=1 if self.gap_switch.switch.get_active() else 0,
                layer=int(self.layer_row.get_last_child().get_value()),
            ))
        self.close()


class DksDialog(Adw.Dialog):
    def __init__(self, index: int, current: Dks, on_save) -> None:
        super().__init__()
        self.set_content_width(520)
        self.set_title(f"DKS {index}")
        self._index = index
        self._on_save = on_save
        view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.set_title_widget(Adw.WindowTitle(title=f"Dynamic keystroke {index}",
                                                 subtitle="Four travel events"))
        cancel = Gtk.Button(label="Cancel")
        cancel.connect("clicked", lambda _b: self.close())
        save = Gtk.Button(label="Save")
        save.add_css_class("suggested-action")
        save.connect("clicked", lambda _b: self._save())
        header.pack_start(cancel)
        header.pack_end(save)
        view.add_top_bar(header)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(14)
        box.set_margin_bottom(16)
        box.set_margin_start(18)
        box.set_margin_end(18)
        box.append(label(
            "Each row is one keystroke. The status mask selects which press and "
            "release events fire it; the firmware's own editor uses the same 10 bits. "
            "The value is preserved as a bit mask so a binding written by the vendor "
            "tool round-trips without interpretation.",
            "muted small", wrap=True,
        ))
        self.entries: list[tuple[Gtk.Entry, Gtk.Entry]] = []
        grid = Gtk.Grid(column_spacing=10, row_spacing=8)
        grid.attach(label("Keystroke", "row-sub"), 0, 0, 1, 1)
        grid.attach(label("Status (hex)", "row-sub"), 1, 0, 1, 1)
        for slot, action in enumerate(current.actions):
            key_entry = Gtk.Entry()
            key_entry.set_text(keycodes.name(action.keycode) if action.keycode else "")
            key_entry.set_placeholder_text("e.g. Space")
            status_entry = Gtk.Entry()
            status_entry.set_text(f"{action.status:03x}" if action.status else "000")
            status_entry.set_width_chars(6)
            grid.attach(key_entry, 0, slot + 1, 1, 1)
            grid.attach(status_entry, 1, slot + 1, 1, 1)
            self.entries.append((key_entry, status_entry))
        box.append(grid)
        self.error_label = label("", "error", wrap=True)
        self.error_label.set_visible(False)
        box.append(self.error_label)
        view.set_content(box)
        self.set_child(view)

    def _show_error(self, message: str) -> None:
        self.error_label.set_text(message)
        self.error_label.set_visible(True)

    def _save(self) -> None:
        actions = []
        for slot, (key_entry, status_entry) in enumerate(self.entries, start=1):
            key_text = key_entry.get_text().strip()
            keycode = keycodes.from_name(key_text) if key_text else 0
            if key_text and keycode is None:
                self._show_error(
                    f"Keystroke {slot} is not a known key name. "
                    "Use a name such as Space, or clear the field."
                )
                return
            status_text = status_entry.get_text().strip()
            if status_text:
                try:
                    status = int(status_text, 16)
                except ValueError:
                    self._show_error(
                        f"Status {slot} must be hexadecimal between 000 and 3ff."
                    )
                    return
                if not 0 <= status <= 0x3FF:
                    self._show_error(
                        f"Status {slot} must be hexadecimal between 000 and 3ff."
                    )
                    return
            else:
                status = 0
            actions.append(DksAction(status=status, keycode=keycode))
        self._on_save(Dks(index=self._index, actions=tuple(actions)))
        self.close()


class AdvancedPage(Page):
    title = "Advanced"
    subtitle = "Switches, dead band and the keyboard's own smart keys."

    def __init__(self, window) -> None:
        super().__init__(window, max_width=1040)
        self._suppress = False
        self._advanced_loading = False
        self._deadband_debounce = Debouncer(220, self._apply_deadband)
        self._build()

    def _build(self) -> None:
        reload = button("Reload", icon="view-refresh-symbolic")
        reload.connect("clicked", lambda _b: self._reload())
        self.add(self.header(reload))

        self.warning = Section(tight=True)
        self.warning.set_visible(False)
        self.add(self.warning)

        performance = Section(
            "Switches",
            "Firmware-level behaviour. Changes apply immediately and are volatile.",
        )
        self.sw_nkro = SwitchRow(
            "N-key rollover",
            "Report every key independently instead of the 6-key boot report.",
            on_toggle=lambda on: self._features(nkro=1 if on else 0),
        )
        self.sw_win = SwitchRow(
            "Lock the Windows key",
            "Prevents accidental desktop shortcuts while gaming.",
            on_toggle=lambda on: self._features(win_lock=1 if on else 0),
        )
        self.sw_wasd = SwitchRow(
            "Swap WASD with arrows",
            "Some games only accept the arrow keys.",
            on_toggle=lambda on: self._features(wasd_swap=1 if on else 0),
        )
        self.sw_mac = SwitchRow(
            "macOS layout",
            "Switches the modifier arrangement to the Mac convention.",
            on_toggle=lambda on: self._features(mac_mode=1 if on else 0),
        )
        for widget in (self.sw_nkro, self.sw_win, self.sw_wasd, self.sw_mac):
            performance.add(widget)
        performance.add(separator())
        self.sw_game = SwitchRow(
            "Game mode", "The firmware's competitive preset.",
            on_toggle=lambda on: self._set_scalar("game", 1 if on else 0),
        )
        self.sw_bottom = SwitchRow(
            "Bottom-out optimisation",
            "Treat a key that reaches the bottom as pressed, smoothing over tiny "
            "travel differences between switches.",
            on_toggle=lambda on: self._set_scalar("bottom", 1 if on else 0),
        )
        performance.add(self.sw_game)
        performance.add(self.sw_bottom)
        self.add(performance)

        dead = Section(
            "Dead band",
            "Ignore movement at the very top and bottom of a key's travel.",
        )
        self.dead_top = LabeledScale(
            "Top dead band", 0.0, 0.50, 0.01, unit=" mm",
            subtitle="Movement ignored before the press starts counting.",
            on_change=lambda _v: self._deadband_debounce.trigger(),
        )
        self.dead_bottom = LabeledScale(
            "Bottom dead band", 0.0, 0.50, 0.01, unit=" mm",
            subtitle="Movement ignored near the bottom of travel.",
            on_change=lambda _v: self._deadband_debounce.trigger(),
        )
        dead.add(self.dead_top)
        dead.add(self.dead_bottom)
        self.add(dead)

        advanced = Section(
            "Advanced keys",
            "Rapid snappy, SOCD and OKS. The keyboard evaluates these itself.",
            trailing=button("Reload", icon="view-refresh-symbolic", flat=True),
        )
        advanced.trailing.connect("clicked", lambda _b: self._reload_advanced())
        self.advanced_rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        advanced.add(self.advanced_rows)
        advanced.add(label(
            "A slot can be rebound at any time. These bindings are written to the "
            "keyboard immediately, not held for the tuning Save button.",
            "tiny muted", wrap=True,
        ))
        self.add(advanced)

        dks = Section(
            "Dynamic keystroke (DKS)",
            "Up to four keystrokes from how far a key is pressed and released.",
            trailing=button("Reload", icon="view-refresh-symbolic", flat=True),
        )
        dks.trailing.connect("clicked", lambda _b: self._reload_advanced())
        self.dks_rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        dks.add(self.dks_rows)
        self.add(dks)

        calibration = Section("Calibration", "The keyboard calibrates its own Hall sensors.")
        self.calibration_label = label("", "row-sub", wrap=True)
        calibration.add(self.calibration_label)
        rows = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        report = button("Device report", icon="dialog-information-symbolic")
        report.connect("clicked", lambda _b: self.window.show_diagnostics())
        permissions = button("Permissions", icon="dialog-password-symbolic", flat=True)
        permissions.connect("clicked", lambda _b: self.window.show_permissions())
        rows.append(report)
        rows.append(permissions)
        calibration.add(rows)
        calibration.add(label(
            "Switch calibration is deliberately not started from this app: a badly "
            "interrupted calibration is the one thing that can make a Hall-effect "
            "board feel broken. Use the official web driver for that step.",
            "tiny muted", wrap=True,
        ))
        self.add(calibration)

    # -- state -------------------------------------------------------------
    def on_show(self) -> None:
        if self.window.state.connected and self.window.state.advanced_keys is None:
            self._reload_advanced()

    def on_state(self, state) -> None:
        self._suppress = True
        try:
            self.sw_nkro.set_active(bool(state.features.nkro))
            self.sw_win.set_active(bool(state.features.win_lock))
            self.sw_wasd.set_active(bool(state.features.wasd_swap))
            self.sw_mac.set_active(bool(state.features.mac_mode))
            self.sw_game.set_active(bool(state.game_mode))
            self.sw_bottom.set_active(bool(state.bottom_optimize))
            self.dead_top.set_value(state.dead_band.top_mm)
            self.dead_bottom.set_value(state.dead_band.bottom_mm)
            if state.calibration:
                good = sum(1 for value in state.calibration if value)
                self.calibration_label.set_text(
                    f"{good} of {len(state.calibration)} matrix positions report a "
                    f"calibrated sensor. Empty matrix positions are expected to be blank."
                )
            else:
                self.calibration_label.set_text("Calibration status was not read.")
        finally:
            self._suppress = False
        self._update_advanced(state)
        writable = state.writable
        for widget in (self.sw_nkro, self.sw_win, self.sw_wasd, self.sw_mac,
                       self.sw_game, self.sw_bottom, self.dead_top, self.dead_bottom):
            widget.set_sensitive(writable)
        if not state.connected:
            self._show_warning("Connect a keyboard to change these settings.")
        elif not writable:
            self._show_warning(
                f"Read-only session: {state.info.read_only_reason}. Values can be "
                f"viewed but not changed."
            )
        else:
            self.warning.set_visible(False)

    def _show_warning(self, text: str) -> None:
        while child := self.warning.content.get_first_child():
            self.warning.content.remove(child)
        self.warning.set_visible(True)
        self.warning.add(label(text, "warning-box", wrap=True))

    # -- writes ------------------------------------------------------------
    def _features(self, **changes) -> None:
        if self._suppress or not self.window.state.writable:
            return
        features = replace(self.window.state.features, **changes)
        self.window.set_state_local(replace(self.window.state, features=features))

        def job(device):
            device.write_features(features)

        self.window.worker.submit(job, error=lambda exc: self._error(exc),
                                  description="features")

    def _set_scalar(self, which: str, value: int) -> None:
        if self._suppress or not self.window.state.writable:
            return
        state = self.window.state
        if which == "game":
            self.window.set_state_local(replace(state, game_mode=value))
            job_fn = lambda device: device.write_game_mode(value)
        else:
            self.window.set_state_local(replace(state, bottom_optimize=value))
            job_fn = lambda device: device.write_bottom_optimize(value)
        self.window.worker.submit(job_fn, error=lambda exc: self._error(exc),
                                  description=which)

    def _apply_deadband(self) -> None:
        if self._suppress or not self.window.state.writable:
            return
        band = DeadBand(
            top_mm=self.dead_top.scale.get_value(),
            bottom_mm=self.dead_bottom.scale.get_value(),
        )
        self.window.set_state_local(replace(self.window.state, dead_band=band))
        self.window.worker.submit(
            lambda device: device.write_dead_band(band),
            error=lambda exc: self._error(exc),
            description="dead band",
        )

    def _error(self, exc: Exception) -> None:
        self.window.notify(f"Setting not applied: {exc}")
        self.window.refresh()

    # -- advanced keys -----------------------------------------------------
    def _reload(self) -> None:
        self.window.refresh()

    def _reload_advanced(self) -> None:
        state = self.window.state
        if not state.connected or self._advanced_loading:
            return
        self._advanced_loading = True

        def done(loaded):
            self._advanced_loading = False
            self.window.set_state_local(loaded)

        def error(exc):
            self._advanced_loading = False
            self.window.notify(f"Could not read advanced keys: {exc}")

        self.window.worker.refresh_advanced(callback=done)

    def _update_advanced(self, state) -> None:
        self._update_advanced_rows(state)
        self._update_dks_rows(state)

    def _update_advanced_rows(self, state) -> None:
        while child := self.advanced_rows.get_first_child():
            self.advanced_rows.remove(child)
        if state.advanced_keys is None:
            self.advanced_rows.append(
                label("Read advanced keys to see their current bindings.",
                      "muted small", wrap=True)
            )
            return
        active = [key for key in state.advanced_keys if key.active]
        if not active:
            self.advanced_rows.append(
                label("No advanced keys are configured.", "muted small")
            )
        for key in active:
            item = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            item.add_css_class("list-row")
            text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
            text.set_hexpand(True)
            text.append(label(f"Slot {key.index} · {key.mode.name}", "row-title"))
            key1 = layout.key_at(state.board, key.key1_row, key.key1_col)
            key2 = layout.key_at(state.board, key.key2_row, key.key2_col)
            text.append(label(
                f"{key1.label if key1 else '?'} + {key2.label if key2 else '?'}",
                "row-sub",
            ))
            item.append(text)
            edit = button("Edit", flat=True)
            edit.connect("clicked", lambda _b, k=key: self._edit_advanced(k))
            item.append(edit)
            self.advanced_rows.append(item)
            self.advanced_rows.append(separator())
        idle = [key for key in state.advanced_keys if not key.active]
        if idle and active:
            self.advanced_rows.append(
                label(f"{len(idle)} unused slots available.", "tiny muted")
            )
        add = button("Configure the first free slot", flat=True)
        free = next((key for key in state.advanced_keys if not key.active), None)
        if free is not None:
            add.connect("clicked", lambda _b, k=free: self._edit_advanced(k))
            self.advanced_rows.append(add)

    def _edit_advanced(self, key: AdvancedKey) -> None:
        if not self.window.state.writable:
            self.window.notify("The session is read-only.")
            return
        tap = TapDance(index=key.index % 8)
        if self.window.state.tap_dance and key.index % 8 < len(self.window.state.tap_dance):
            tap = self.window.state.tap_dance[key.index % 8]

        def save(kind: str, value) -> None:
            if kind == "tap":
                self._write_tap(value)
            else:
                self._write_advanced(value)

        AdvancedKeyDialog(self.window, key.index, key, tap, save).present(self.window)

    def _write_advanced(self, key: AdvancedKey) -> None:
        state = self.window.state
        keys = list(state.advanced_keys or [])
        while len(keys) <= key.index:
            keys.append(AdvancedKey(index=len(keys)))
        keys[key.index] = key
        self.window.set_state_local(replace(state, advanced_keys=keys))
        self.window.worker.submit(
            lambda device: device.write_advanced_key(key),
            callback=lambda _r: self.window.notify("Advanced key updated."),
            error=lambda exc: self._error(exc),
            description="advanced key",
        )

    def _write_tap(self, tap: TapDance) -> None:
        state = self.window.state
        taps = list(state.tap_dance or [TapDance(index=index) for index in range(8)])
        while len(taps) <= tap.index:
            taps.append(TapDance(index=len(taps)))
        taps[tap.index] = tap
        self.window.set_state_local(replace(state, tap_dance=taps))
        self.window.worker.submit(
            lambda device: device.write_tap_dance(tap),
            callback=lambda _r: self.window.notify("Hold/click updated."),
            error=lambda exc: self._error(exc),
            description="hold click",
        )

    def _update_dks_rows(self, state) -> None:
        while child := self.dks_rows.get_first_child():
            self.dks_rows.remove(child)
        if state.dks is None:
            self.dks_rows.append(label("Read DKS slots to see their bindings.",
                                        "muted small", wrap=True))
            return
        active = [dks for dks in state.dks if any(action.keycode for action in dks.actions)]
        if not active:
            self.dks_rows.append(label("No dynamic keystrokes configured.", "muted small"))
        for dks in active:
            item = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            item.add_css_class("list-row")
            keys = [keycodes.label(action.keycode) for action in dks.actions if action.keycode]
            text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
            text.set_hexpand(True)
            text.append(label(f"Slot {dks.index}", "row-title"))
            text.append(label(" · ".join(keys), "row-sub"))
            item.append(text)
            edit = button("Edit", flat=True)
            edit.connect("clicked", lambda _b, d=dks: self._edit_dks(d))
            item.append(edit)
            self.dks_rows.append(item)
            self.dks_rows.append(separator())
        if state.dks:
            add = button("Configure the first empty DKS slot", flat=True)
            free = next((dks for dks in state.dks
                         if not any(action.keycode for action in dks.actions)), None)
            if free:
                add.connect("clicked", lambda _b, d=free: self._edit_dks(d))
                self.dks_rows.append(add)

    def _edit_dks(self, dks: Dks) -> None:
        if not self.window.state.writable:
            self.window.notify("The session is read-only.")
            return

        def save(updated: Dks) -> None:
            state = self.window.state
            slots = list(state.dks or [])
            while len(slots) <= updated.index:
                slots.append(Dks(index=len(slots)))
            slots[updated.index] = updated
            self.window.set_state_local(replace(state, dks=slots))
            self.window.worker.submit(
                lambda device: device.write_dks(updated),
                callback=lambda _r: self.window.notify("DKS updated."),
                error=lambda exc: self._error(exc),
                description="dks",
            )

        DksDialog(dks.index, dks, save).present(self.window)
