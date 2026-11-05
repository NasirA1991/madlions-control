"""Macro editor for the keyboard's shared VIA macro buffer."""

from __future__ import annotations

from dataclasses import replace

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402

from .. import keycodes, macros_codec
from .keymap import KeycodeDialog
from .widgets import Page, Section, button, label, separator


class MacrosPage(Page):
    title = "Macros"
    subtitle = "Automate a sequence of keys, text and delays."

    def __init__(self, window) -> None:
        super().__init__(window, max_width=1120)
        self.slot = 0
        self.steps: list[macros_codec.MacroStep] = []
        self._loading = False
        self._slot_buttons: list[Gtk.Button] = []
        self._build()

    def _build(self) -> None:
        reload = button("Reload", icon="view-refresh-symbolic")
        reload.connect("clicked", lambda _b: self._load(force=True))
        self.add(self.header(reload))
        self.add(label(
            "Macros are stored in the keyboard. Changes write to onboard memory "
            "immediately — there is no separate save step.",
            "info-box", wrap=True,
        ))

        content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        left = Section("Slots", "Sixteen independent sequences.")
        left.set_size_request(300, -1)
        self.slots_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_min_content_height(470)
        scroller.set_child(self.slots_box)
        left.add(scroller)
        content.append(left)

        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        right.set_hexpand(True)
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.editor_title = label("Macro 1", "section-title")
        self.editor_title.set_hexpand(True)
        header.append(self.editor_title)
        self.save_button = button("Save macro", icon="document-save-symbolic", suggested=True)
        self.save_button.connect("clicked", lambda _b: self._save())
        header.append(self.save_button)
        right.append(header)
        self.editor_note = label("", "tiny muted")
        right.append(self.editor_note)

        steps_scroller = Gtk.ScrolledWindow()
        steps_scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        steps_scroller.set_min_content_height(330)
        self.steps_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        steps_scroller.set_child(self.steps_box)
        right.append(steps_scroller)
        self.empty_steps = label(
            "This macro is empty. Add a tap, some text, or a delay below.",
            "muted small", wrap=True,
        )
        right.append(self.empty_steps)

        adds = Section("Add a step")
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        for title, kind in (("Tap key", "tap"), ("Press key", "down"), ("Release key", "up")):
            btn = button(title, flat=True)
            btn.connect("clicked", lambda _b, k=kind: self._add_key(k))
            row.append(btn)
        delay = button("Delay", flat=True)
        delay.connect("clicked", lambda _b: self._add_delay())
        row.append(delay)
        text = button("Text", flat=True)
        text.connect("clicked", lambda _b: self._add_text())
        row.append(text)
        adds.add(row)
        adds.add(label(
            "A key tap is a press and release; use Press/Release for holds. "
            "Text is typed literally (ASCII).",
            "tiny muted", wrap=True,
        ))
        right.append(adds)

        clear = button("Clear this slot", flat=True)
        clear.connect("clicked", lambda _b: self._clear())
        right.append(clear)
        content.append(right)
        self.add(content)

    # -- data --------------------------------------------------------------
    def _count(self) -> int:
        return max(1, min(32, self.window.state.macro_count or 16))

    def _macros(self) -> list[bytes]:
        state = self.window.state
        if state.macros:
            return macros_codec.split(state.macros, self._count())
        return [b""] * self._count()

    def on_show(self) -> None:
        self._load()

    def on_state(self, state) -> None:
        if state.connected and not state.macros:
            self._load()
        self._build_slots()
        self._render_steps()

    def _load(self, force: bool = False) -> None:
        state = self.window.state
        if not state.connected or self._loading:
            return
        if state.macros is not None and not force:
            self._build_slots()
            self._render_steps()
            return
        self._loading = True
        self.editor_note.set_text("Reading macros…")

        def done(updated):
            self._loading = False
            self.window.set_state_local(updated)
            self._build_slots()
            self._select_slot(self.slot)

        def error(exc):
            self._loading = False
            self.editor_note.set_text(f"Could not read macros: {exc}")

        self.window.worker.refresh_macros(callback=done)

    def _build_slots(self) -> None:
        while child := self.slots_box.get_first_child():
            self.slots_box.remove(child)
        self._slot_buttons = []
        macros = self._macros()
        for index, macro in enumerate(macros):
            steps = macros_codec.decode(macro)
            btn = Gtk.Button()
            btn.add_css_class("flat")
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
            box.set_margin_top(5)
            box.set_margin_bottom(5)
            title = label(f"Macro {index + 1}", "row-title", xalign=0)
            summary = label(macros_codec.steps_summary(steps), "row-sub", xalign=0,
                            ellipsize=True)
            box.append(title)
            box.append(summary)
            btn.set_child(box)
            btn.connect("clicked", lambda _b, i=index: self._select_slot(i))
            self.slots_box.append(btn)
            if index == self.slot:
                btn.add_css_class("active")
            self._slot_buttons.append(btn)

    def _select_slot(self, index: int) -> None:
        self.slot = max(0, min(self._count() - 1, index))
        macros = self._macros()
        self.steps = macros_codec.decode(macros[self.slot]) if self.slot < len(macros) else []
        self._build_slots()
        self._render_steps()

    def _render_steps(self) -> None:
        self.editor_title.set_text(f"Macro {self.slot + 1}")
        while child := self.steps_box.get_first_child():
            self.steps_box.remove(child)
        for index, step in enumerate(self.steps):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            row.add_css_class("list-row")
            row.append(label(f"{index + 1:02d}", "tiny muted"))
            description = step.summary
            if step.kind in ("tap", "down", "up"):
                description += f"  {keycodes.name(step.keycode)}"
            text = label(description, "row-sub", ellipsize=True)
            text.set_hexpand(True)
            row.append(text)
            remove = Gtk.Button()
            remove.set_child(Gtk.Image.new_from_icon_name("user-trash-symbolic"))
            remove.add_css_class("flat")
            remove.set_tooltip_text("Remove this step")
            remove.connect("clicked", lambda _b, i=index: self._remove_step(i))
            row.append(remove)
            self.steps_box.append(row)
            self.steps_box.append(separator())
        self.empty_steps.set_visible(not self.steps)
        try:
            size = len(macros_codec.encode(self.steps))
        except ValueError:
            size = 0
        self.editor_note.set_text(
            f"{len(self.steps)} steps · {size} bytes" if self.steps else "Empty"
        )

    # -- editing -----------------------------------------------------------
    def _add_key(self, kind: str) -> None:
        def selected(code: int) -> None:
            self.steps.append(macros_codec.MacroStep(kind, keycode=code))
            self._render_steps()

        KeycodeDialog(0, selected).present(self.window)

    def _add_delay(self) -> None:
        dialog = Adw.AlertDialog(heading="Add delay", body="Pause between steps.")
        spin = Gtk.SpinButton.new_with_range(0, 2000, 10)
        spin.set_value(80)
        dialog.set_extra_child(spin)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("add", "Add")
        dialog.set_response_appearance("add", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("add")
        dialog.set_close_response("cancel")

        def response(_dialog, response_id):
            if response_id == "add":
                self.steps.append(macros_codec.MacroStep("delay", delay_ms=int(spin.get_value())))
                self._render_steps()

        dialog.connect("response", response)
        dialog.present(self.window)

    def _add_text(self) -> None:
        dialog = Adw.AlertDialog(
            heading="Add text",
            body="The keyboard types this literally while the macro runs.",
        )
        entry = Gtk.Entry()
        entry.set_placeholder_text("e.g. gg")
        dialog.set_extra_child(entry)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("add", "Add")
        dialog.set_response_appearance("add", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("add")
        dialog.set_close_response("cancel")

        def response(_dialog, response_id):
            if response_id == "add" and entry.get_text():
                self.steps.append(macros_codec.MacroStep("text", text=entry.get_text()))
                self._render_steps()

        dialog.connect("response", response)
        dialog.present(self.window)

    def _remove_step(self, index: int) -> None:
        if 0 <= index < len(self.steps):
            del self.steps[index]
            self._render_steps()

    def _clear(self) -> None:
        if not self.window.state.writable:
            self.window.notify("The session is read-only.")
            return
        dialog = Adw.AlertDialog(
            heading=f"Clear macro {self.slot + 1}?",
            body="The slot is overwritten on the keyboard immediately.",
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("clear", "Clear")
        dialog.set_response_appearance("clear", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        def response(_dialog, response_id):
            if response_id == "clear":
                self.steps = []
                self._render_steps()
                self._save()

        dialog.connect("response", response)
        dialog.present(self.window)

    def _save(self) -> None:
        state = self.window.state
        if not state.writable:
            self.window.notify("The session is read-only.")
            return
        if not state.macros:
            self._load()
            self.window.notify("Read the macros first, then save again.")
            return
        try:
            encoded = macros_codec.encode(self.steps)
            buffer = macros_codec.rebuild(
                state.macros, self.slot, encoded, self._count()
            )
        except ValueError as exc:
            self.window.notify(f"Macro not saved: {exc}")
            return
        self.window.set_state_local(replace(state, macros=buffer))

        def job(device):
            device.write_macros(buffer)
            if device.read_macros() != buffer:
                raise ValueError(
                    "the macro buffer did not read back after writing"
                )

        def error(exc):
            self.window.notify(f"Macro not saved: {exc}")
            self.window.refresh()

        self.window.worker.submit(job, error=error, description="macro")
        self.window.notify(f"Macro {self.slot + 1} saved.")
        self._build_slots()
