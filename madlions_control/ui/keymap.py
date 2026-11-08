"""Keymap editor with the four onboard layers."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402

from .. import keycodes, layout
from .keyboard import KeyboardCanvas
from .widgets import Page, Section, button, label, toast


class KeycodeDialog(Adw.Dialog):
    def __init__(self, current: int, on_select) -> None:
        super().__init__()
        self.set_content_width(800)
        self.set_content_height(620)
        self.set_title("Choose a key")
        self._on_select = on_select

        view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.set_title_widget(Adw.WindowTitle(title="Choose a key",
                                                 subtitle="Writes to onboard memory"))
        view.add_top_bar(header)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(10)
        box.set_margin_bottom(12)
        box.set_margin_start(14)
        box.set_margin_end(14)

        filters = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.search = Gtk.SearchEntry()
        self.search.set_hexpand(True)
        self.search.set_placeholder_text("Search keys, e.g. space, F5, MO(1)")
        self.search.connect("search-changed", lambda *_a: self._populate())
        filters.append(self.search)
        self.category = Gtk.DropDown.new_from_strings(["All"] + list(keycodes.CATEGORIES))
        self.category.connect("notify::selected", lambda *_a: self._populate())
        filters.append(self.category)
        box.append(filters)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_vexpand(True)
        self.flow = Gtk.FlowBox()
        self.flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self.flow.set_max_children_per_line(7)
        self.flow.set_min_children_per_line(3)
        self.flow.set_homogeneous(True)
        self.flow.set_row_spacing(5)
        self.flow.set_column_spacing(5)
        self.flow.set_margin_top(6)
        self.flow.set_margin_bottom(6)
        scroller.set_child(self.flow)
        box.append(scroller)
        view.set_content(box)
        self.set_child(view)
        self._current = current
        self._populate()

    def _populate(self) -> None:
        while child := self.flow.get_first_child():
            self.flow.remove(child)
        text = self.search.get_text()
        selected = self.category.get_selected()
        category = None if selected == 0 else list(keycodes.CATEGORIES)[selected - 1]
        for key in keycodes.search(text, category):
            button_widget = Gtk.Button(label=key.label)
            button_widget.set_tooltip_text(f"{key.name} · {key.category}")
            button_widget.add_css_class("preset-chip")
            if key.code == self._current:
                button_widget.add_css_class("suggested-action")
            button_widget.connect("clicked", lambda _b, code=key.code: self._choose(code))
            child = Gtk.FlowBoxChild()
            child.set_child(button_widget)
            self.flow.append(child)

    def _choose(self, code: int) -> None:
        self._on_select(code)
        self.close()


class KeymapPage(Page):
    title = "Keymap"
    subtitle = "Four layers of physical keys, stored on the keyboard."

    def __init__(self, window) -> None:
        super().__init__(window, max_width=1260)
        self.layer = 0
        self.selected: tuple[int, int] | None = None
        self._loading = False
        self._layer_buttons: list[Gtk.Button] = []
        self._build()

    def _build(self) -> None:
        refresh = button("Reload", icon="view-refresh-symbolic")
        refresh.connect("clicked", lambda _b: self._load(force=True))
        self.add(self.header(refresh))

        note = label(
            "Key changes are written straight to the keyboard's onboard memory — "
            "they survive unplugging and do not need a Save button.",
            "info-box", wrap=True,
        )
        self.add(note)

        layer_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        layer_row.append(label("Layer", "row-title"))
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        layer_row.append(spacer)
        for number in range(4):
            btn = Gtk.Button(label=f"L{number}")
            btn.add_css_class("layer-btn")
            btn.connect("clicked", lambda _b, n=number: self._set_layer(n))
            self._layer_buttons.append(btn)
            layer_row.append(btn)
        self.add(layer_row)

        self.canvas = KeyboardCanvas(height=300, on_key=self._key_clicked)
        self.canvas.set_mode("keymap")
        self.add(self.canvas)
        self.status = label("", "tiny muted")
        self.add(self.status)

        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        controls.set_homogeneous(True)
        info = Section("Selected key", "Click any cap above to inspect it.")
        self.key_title = label("No key selected", "section-title")
        self.key_sub = label("Click a key on the board.", "tiny muted", wrap=True)
        self.code_label = label("—", "value-big")
        self.code_name = label("", "mono muted")
        info.add(self.key_title)
        info.add(self.key_sub)
        info.add(self.code_label)
        info.add(self.code_name)
        controls.append(info)

        actions = Section("Change", "The new keycode is written to onboard memory immediately.")
        self.change = button("Choose a key…", icon="view-list-symbolic", suggested=True)
        self.change.set_sensitive(False)
        self.change.connect("clicked", lambda _b: self._open_picker())
        actions.add(self.change)
        quick = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.transparent_btn = button("Transparent", flat=True)
        self.transparent_btn.connect("clicked", lambda _b: self._write(keycodes.KC_TRNS))
        self.clear_btn = button("Clear", flat=True)
        self.clear_btn.connect("clicked", lambda _b: self._write(keycodes.KC_NO))
        quick.append(self.transparent_btn)
        quick.append(self.clear_btn)
        actions.add(quick)
        actions.add(label(
            "Transparent passes the key through to the layer below. Clear disables it.",
            "tiny muted", wrap=True,
        ))
        controls.append(actions)

        layers = Section(
            "Layers",
            f"Each layer has its own {self.window.state.board.total_keys}-key map.",
        )
        self.layer_info = label("", "row-sub", wrap=True)
        layers.add(self.layer_info)
        layers.add(label(
            "Fn on the keyboard is usually MO(1). Hold it to reach layer 1.",
            "tiny muted", wrap=True,
        ))
        controls.append(layers)
        self.add(controls)
        self._update_layers()

    # -- state -------------------------------------------------------------
    def on_show(self) -> None:
        self._load()

    def on_state(self, state) -> None:
        self.canvas.set_state(state)
        self._update_layers()
        if state.connected and state.keymap is None:
            self._load()
        self._update_selection()
        if state.keymap is not None:
            self.status.set_text(
                f"Layer {self.layer} loaded · {state.layers} layers · "
                f"{state.board.keymap_size} bytes"
            )
            if hasattr(self, "layer_info"):
                codes = state.layer_keycodes(self.layer)
                custom = sum(1 for row in codes for code in row if code not in (0, 1))
                self.layer_info.set_text(
                    f"Layer {self.layer} · {custom} mapped positions · "
                    f"{state.board.keymap_size} bytes total"
                )
        elif state.connected:
            self.status.set_text("Reading keymap…")
        else:
            self.status.set_text("No keyboard connected.")

    def _load(self, force: bool = False) -> None:
        state = self.window.state
        if not state.connected or self._loading:
            return
        if state.keymap is not None and not force:
            return
        self._loading = True
        self.status.set_text("Reading keymap…")

        def done(loaded):
            self._loading = False
            self.window.set_state_local(loaded)

        def error(exc):
            self._loading = False
            self.status.set_text(f"Could not read the keymap: {exc}")

        self.window.worker.refresh_keymap(callback=done)

    # -- layers / selection ------------------------------------------------
    def _set_layer(self, layer: int) -> None:
        self.layer = max(0, min(3, layer))
        self.canvas.set_layer(self.layer)
        self._update_layers()
        self._update_selection()

    def _update_layers(self) -> None:
        for number, btn in enumerate(self._layer_buttons):
            btn.set_visible(number < max(1, self.window.state.layers))
            if number == self.layer:
                btn.add_css_class("active")
            else:
                btn.remove_css_class("active")

    def _key_clicked(self, row: int, col: int, ctrl: bool) -> None:
        self.selected = (row, col)
        self.canvas.set_selection({self.selected})
        self._update_selection()

    def _update_selection(self) -> None:
        state = self.window.state
        if not self.selected:
            self.key_title.set_text("No key selected")
            self.key_sub.set_text("Click a key on the board.")
            self.code_label.set_text("")
            self.code_name.set_text("")
            self.change.set_sensitive(False)
            return
        row, col = self.selected
        key = layout.key_at(state.board, row, col)
        self.key_title.set_text(key.label if key else f"Row {row}, col {col}")
        self.key_sub.set_text(f"Layer {self.layer} · row {row}, column {col}")
        code = state.keycode_at(self.layer, row, col)
        resolved = keycodes.lookup(code)
        self.code_label.set_text(resolved.label)
        self.code_name.set_text(f"{resolved.name} · {code:#06x}")
        self.change.set_sensitive(bool(state.writable))
        if hasattr(self, "transparent_btn"):
            self.transparent_btn.set_sensitive(bool(state.writable))
            self.clear_btn.set_sensitive(bool(state.writable))

    def _open_picker(self) -> None:
        if not self.selected:
            return
        row, col = self.selected
        current = self.window.state.keycode_at(self.layer, row, col)
        KeycodeDialog(current, lambda code: self._write(code)).present(self.window)

    def _write(self, code: int) -> None:
        if not self.selected:
            return
        state = self.window.state
        if not state.writable:
            self.window.notify("This session is read-only.")
            return
        row, col = self.selected
        layer = self.layer
        updated = state.with_keycode(layer, row, col, code)
        self.window.set_state_local(updated)
        self.canvas.set_state(updated)
        self._update_selection()

        def job(device):
            device.write_keycode(layer, row, col, code)

        def done(_result):
            physical = layout.key_at(state.board, row, col)
            self.window.notify(
                f"{physical.label if physical else f'{row},{col}'} → {keycodes.label(code)}"
            )

        def error(exc):
            self.window.notify(f"Key not written: {exc}")
            self.window.refresh()

        self.window.worker.submit(job, callback=done, error=error, description="keycode")
