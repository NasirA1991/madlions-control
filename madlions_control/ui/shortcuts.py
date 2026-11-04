"""Read-only keyboard shortcut cheatsheet."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402

from .. import shortcuts
from .widgets import label


class ShortcutsDialog(Adw.Dialog):
    def __init__(self, state, on_open_keymap=None) -> None:
        super().__init__()
        self.set_title("Keyboard shortcuts")
        self.set_content_width(720)
        self.set_content_height(660)
        self._state = state
        self._on_open_keymap = on_open_keymap

        view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.set_show_start_title_buttons(False)
        header.set_title_widget(Adw.WindowTitle(
            title="Keyboard shortcuts",
            subtitle=f"Fn layer · {state.board.name}",
        ))
        close = Gtk.Button(label="Close")
        close.connect("clicked", lambda _b: self.close())
        header.pack_end(close)
        if on_open_keymap is not None:
            edit = Gtk.Button(label="Open Keymap")
            edit.add_css_class("flat")
            edit.connect("clicked", lambda _b: self._edit_keymap())
            header.pack_start(edit)
        view.add_top_bar(header)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        page = Adw.PreferencesPage()
        page.set_margin_top(4)
        page.set_margin_bottom(12)
        content.append(page)
        scroll.set_child(content)
        view.set_content(scroll)
        self.set_child(view)

        intro = label(
            "These combinations come from the layer Fn activates in the "
            "keyboard's current keymap, not from a hard-coded manual. Edit that "
            "layer in Keymap to change them. The Fn key is the key labelled Fn.",
            "info-box", wrap=True,
        )
        intro.set_margin_top(12)
        intro.set_margin_bottom(10)
        intro.set_margin_start(14)
        intro.set_margin_end(14)
        content.prepend(intro)

        items = shortcuts.build_shortcuts(state)
        if not items:
            empty = label(
                "The keymap is not loaded yet, so there is nothing to show.",
                "muted small", wrap=True,
            )
            content.append(empty)
            return

        groups = (
            ("Lighting", "Fn + the key printed on the cap. These are the "
                         "firmware's standard RGB controls."),
            ("Function keys", "The F-row and the top-left grave key."),
            ("Other", "Keys whose function is defined by the firmware but not "
                      "named by the public protocol."),
        )
        for title, subtitle in groups:
            group = Adw.PreferencesGroup(title=title, description=subtitle)
            added = 0
            for item in items:
                if item.category != title:
                    continue
                row = Adw.ActionRow(title=item.keys, subtitle=item.action)
                group.add(row)
                added += 1
            if added:
                page.add(group)

        if not any(item.category == "Lighting" for item in items):
            note = label(
                "No standard lighting keycodes are present on layer 1. "
                "Lighting can still be changed from the Lighting page.",
                "tiny muted", wrap=True,
            )
            content.append(note)

    def _edit_keymap(self) -> None:
        if self._on_open_keymap is not None:
            self._on_open_keymap()
        self.close()
