"""Main window: header, sidebar navigation, pages and global actions."""

from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

from .. import baseline, config, profiles, settings, transport
from ..state import KeyboardState
from ..worker import DeviceWorker
from .advanced import AdvancedPage
from .keymap import KeymapPage
from .lighting import LightingPage
from .macros_page import MacrosPage
from .overview import OverviewPage
from .perkey import PerKeyPage
from .profiles_page import ProfilesPage
from .shortcuts import ShortcutsDialog
from .test import TestPage
from .widgets import StatusPill, copy_text, label, toast


class NavRow(Gtk.ListBoxRow):
    def __init__(self, name: str, title: str, icon: str) -> None:
        super().__init__()
        self.name = name
        self.add_css_class("nav-row")
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=11)
        box.set_margin_top(7)
        box.set_margin_bottom(7)
        box.set_margin_start(10)
        box.set_margin_end(10)
        image = Gtk.Image.new_from_icon_name(icon)
        image.set_pixel_size(17)
        box.append(image)
        self._label = label(title, "nav-label")
        self._label.set_hexpand(True)
        box.append(self._label)
        self.set_child(box)

    def set_active(self, active: bool) -> None:
        if active:
            self.add_css_class("active")
        else:
            self.remove_css_class("active")


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app, worker: DeviceWorker, demo: bool = False) -> None:
        super().__init__(application=app)
        self.app = app
        self.worker = worker
        self.demo = demo
        self.state = worker.state
        self.state_version = 0
        self._pages: dict[str, object] = {}
        self._nav_rows: dict[str, NavRow] = {}
        self._current_page = ""
        self._auto_backed_up = False
        self._reset_busy = False
        self._page_specs: dict[str, tuple[str, str, type]] = {}
        self._settings = settings.load()
        self.set_default_size(self._settings.window_width, self._settings.window_height)
        self.set_title(config.APP_NAME)
        self.set_icon_name(config.APP_ID)

        self.toasts = Adw.ToastOverlay()
        self.set_content(self.toasts)
        self.toolbar = Adw.ToolbarView()
        self.toasts.set_child(self.toolbar)

        self._build_header()
        self._build_body()
        self.connect("close-request", self._on_close)
        self._build_pages()
        self.go(self._settings.last_page if self._settings.last_page in self._page_specs else "overview")
        self.on_state(worker.state)

    # -- construction ------------------------------------------------------
    def _build_header(self) -> None:
        header = Adw.HeaderBar()
        header.set_show_back_button(False)
        header.set_show_start_title_buttons(False)
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        title_box.set_valign(Gtk.Align.CENTER)
        self.title_label = label(config.APP_NAME, "header-title")
        self.title_label.set_xalign(0.5)
        self.subtitle_label = label("MADLIONS keyboard", "header-subtitle")
        self.subtitle_label.set_xalign(0.5)
        title_box.append(self.title_label)
        title_box.append(self.subtitle_label)
        header.set_title_widget(title_box)

        self.status_pill = StatusPill()
        pill_wrap = Gtk.Box()
        pill_wrap.set_margin_end(6)
        pill_wrap.append(self.status_pill)
        header.pack_end(pill_wrap)

        shortcuts = Gtk.Button()
        shortcuts.set_child(Gtk.Image.new_from_icon_name("input-keyboard-symbolic"))
        shortcuts.set_tooltip_text("Keyboard shortcuts")
        shortcuts.add_css_class("flat")
        shortcuts.connect("clicked", lambda _b: self.show_shortcuts())
        header.pack_start(shortcuts)

        save = Gtk.Button()
        save.set_child(Gtk.Image.new_from_icon_name("document-save-symbolic"))
        save.set_tooltip_text("Save settings to the keyboard")
        save.add_css_class("flat")
        save.connect("clicked", lambda _b: self.save_to_keyboard())
        header.pack_start(save)

        menu = Gio.Menu()
        menu.append("Keyboard shortcuts", "win.shortcuts")
        menu.append("Refresh from keyboard", "win.refresh")
        menu.append("Reset tuning…", "win.reset-tuning")
        menu.append("Device diagnostics", "win.diagnostics")
        menu.append("Permissions", "win.permissions")
        menu.append("Appearance", "win.appearance")
        menu.append("About Madlions Control", "win.about")
        menu_button = Gtk.MenuButton()
        menu_button.set_icon_name("open-menu-symbolic")
        menu_button.set_tooltip_text("Main menu")
        menu_button.set_menu_model(menu)
        header.pack_end(menu_button)

        for name, callback in (
            ("refresh", lambda: self.refresh()),
            ("shortcuts", lambda: self.show_shortcuts()),
            ("reset-tuning", lambda: self.reset_tuning()),
            ("diagnostics", lambda: self.show_diagnostics()),
            ("permissions", lambda: self.show_permissions()),
            ("appearance", lambda: self.show_appearance()),
            ("about", lambda: self.show_about()),
        ):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", lambda _a, _p, cb=callback: cb())
            self.add_action(action)
        self.toolbar.add_top_bar(header)

    def _build_body(self) -> None:
        body = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        body.set_vexpand(True)

        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        sidebar.add_css_class("sidebar")
        sidebar.set_size_request(218, -1)
        brand = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        brand.add_css_class("brand-box")
        icon_file = config.data_dir() / "icons" / "madlions-control-256.png"
        if icon_file.is_file():
            image = Gtk.Image.new_from_file(str(icon_file))
            image.set_pixel_size(34)
        else:
            image = Gtk.Image.new_from_icon_name("input-keyboard-symbolic")
            image.set_pixel_size(24)
        image.set_valign(Gtk.Align.CENTER)
        brand.append(image)
        brand_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        brand_text.append(label("MADLIONS", "brand-name"))
        brand_text.append(label("CONTROL", "brand-sub"))
        brand.append(brand_text)
        sidebar.append(brand)

        self.nav_list = Gtk.ListBox()
        self.nav_list.add_css_class("nav-list")
        self.nav_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self.nav_list.connect("row-activated", self._nav_activated)
        sidebar.append(self.nav_list)

        spacer = Gtk.Box()
        spacer.set_vexpand(True)
        sidebar.append(spacer)

        footer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        footer.add_css_class("sidebar-footer")
        self.mini_device = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.mini_device.add_css_class("mini-device")
        self.mini_title = label("No keyboard", "mini-device-title")
        self.mini_sub = label("Plug in a device", "mini-device-sub")
        self.mini_device.append(self.mini_title)
        self.mini_device.append(self.mini_sub)
        footer.append(self.mini_device)
        footer.append(label(f"v{config.VERSION}" + (" · demo" if self.demo else ""), "tiny muted"))
        sidebar.append(footer)
        body.append(sidebar)

        self.stack = Gtk.Stack()
        self.stack.set_hhomogeneous(False)
        self.stack.set_vhomogeneous(False)
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_transition_duration(160)
        self.stack.set_hexpand(True)
        body.append(self.stack)
        self.toolbar.set_content(body)

    def _build_pages(self) -> None:
        # Pages are constructed on first visit.  Building all eight pages at
        # startup costs tens of megabytes for widgets that may never be opened.
        specs = (
            ("overview", "Overview", "go-home-symbolic", OverviewPage),
            ("perkey", "Per-key", "input-keyboard-symbolic", PerKeyPage),
            ("lighting", "Lighting", "display-brightness-symbolic", LightingPage),
            ("keymap", "Keymap", "view-list-symbolic", KeymapPage),
            ("macros", "Macros", "view-list-bullet-symbolic", MacrosPage),
            ("advanced", "Advanced", "applications-engineering-symbolic", AdvancedPage),
            ("test", "Test", "utilities-system-monitor-symbolic", TestPage),
            ("profiles", "Profiles", "bookmark-new-symbolic", ProfilesPage),
        )
        for name, title, icon, page_class in specs:
            self._page_specs[name] = (title, icon, page_class)
            nav = NavRow(name, title, icon)
            self._nav_rows[name] = nav
            self.nav_list.append(nav)

    def _ensure_page(self, name: str):
        page = self._pages.get(name)
        if page is not None:
            return page
        _title, _icon, page_class = self._page_specs[name]
        page = page_class(self)
        self._pages[name] = page
        self.stack.add_named(page, name)
        try:
            page.on_state(self.state)
        except Exception:
            pass
        return page

    # -- navigation --------------------------------------------------------
    def _nav_activated(self, _listbox: Gtk.ListBox, row: NavRow) -> None:
        self.go(row.name)

    def go(self, name: str) -> None:
        if name not in self._page_specs:
            return
        if self._current_page == name:
            return
        current = self._pages.get(self._current_page)
        if current is not None:
            current.on_hide()
        page = self._ensure_page(name)
        self._current_page = name
        self.stack.set_visible_child_name(name)
        for page_name, row in self._nav_rows.items():
            row.set_active(page_name == name)
        page.on_show()
        try:
            page.on_state(self.state)
        except Exception:
            pass
        self._settings.last_page = name

    # -- state -------------------------------------------------------------
    def on_worker_event(self, name: str, payload) -> None:
        if name in ("connected", "ready", "disconnected"):
            self.on_state(payload)
        elif name == "connecting":
            self.status_pill.set_state("waiting", "Connecting")
        elif name == "connect_error":
            self.on_state(payload)
        elif name == "stream_error":
            page = self._pages.get("test")
            if page is not None:
                page.stream_error(str(payload))

    def on_state(self, state: KeyboardState) -> None:
        self.state = state
        self.state_version += 1
        if (not self.demo and not self._auto_backed_up and state.connected
                and state.actuation):
            self._auto_backed_up = True
            try:
                profiles.auto_backup(state)
            except Exception:  # noqa: BLE001 - a backup must never break the app
                pass
        if state.connected and state.info:
            self.status_pill.set_state("online", "Connected")
            self.title_label.set_text(config.APP_NAME)
            self.subtitle_label.set_text(f"{state.info.board.name} · {state.info.usb_id}")
            self.mini_title.set_text(state.info.title)
            bits = [f"firmware {state.info.protocol_label}"]
            if not state.info.writable:
                bits.append("read-only")
            self.mini_sub.set_text(" · ".join(bits))
        elif state.error:
            self.status_pill.set_state("offline", "Not connected")
            self.title_label.set_text(config.APP_NAME)
            self.subtitle_label.set_text("No keyboard")
            self.mini_title.set_text("No keyboard")
            self.mini_sub.set_text(state.error[:70])
        else:
            self.status_pill.set_state("waiting", "Waiting")
            self.mini_title.set_text("Searching…")
            self.mini_sub.set_text("Plug in a MADLIONS keyboard")
        for page in self._pages.values():
            try:
                page.on_state(state)
            except Exception as exc:  # noqa: BLE001 - a broken page must not stop the app
                print(f"page error: {exc}")

    def set_state_local(self, state: KeyboardState) -> None:
        """Apply an optimistic update while a write is in flight."""
        self.state = state
        for page in self._pages.values():
            try:
                page.on_state(state)
            except Exception:
                pass

    def refresh(self) -> None:
        if self.demo:
            self.worker.refresh(callback=lambda state: None)
            return
        self.worker.refresh(callback=lambda state: self.notify("Refreshed from the keyboard"))

    # -- global actions ----------------------------------------------------
    def notify(self, text: str) -> None:
        toast(self.toasts, text)

    def save_to_keyboard(self) -> None:
        if not self.state.connected:
            self.notify("No keyboard connected.")
            return
        if not self.state.writable:
            self.show_permissions()
            return

        def job(device):
            device.commit()
            try:
                device.save_lighting()
            except Exception:
                pass

        def done(_result):
            self.notify("Saved to the keyboard.")

        def error(exc):
            self.notify(f"Could not save: {exc}")

        self.worker.submit(job, callback=done, error=error, description="save")
        self.notify("Saving to keyboard…")

    def save_lighting(self) -> None:
        if not self.state.writable:
            self.show_permissions()
            return
        self.worker.submit(
            lambda device: device.save_lighting(),
            callback=lambda _r: self.notify("Lighting saved."),
            error=lambda exc: self.notify(f"Lighting not saved: {exc}"),
            description="save lighting",
        )

    def show_shortcuts(self) -> None:
        if not self.state.connected:
            self.notify("Connect a keyboard to read its Fn layer.")
            return
        if self.state.keymap:
            ShortcutsDialog(
                self.state, on_open_keymap=lambda: self.go("keymap")
            ).present(self)
            return
        self.notify("Reading the keyboard's Fn layer…")

        def done(loaded):
            if loaded.keymap:
                ShortcutsDialog(
                    loaded, on_open_keymap=lambda: self.go("keymap")
                ).present(self)
            else:
                self.notify("The keyboard returned no keymap.")

        self.worker.refresh_keymap(callback=done)

    def reset_tuning(self) -> None:
        """Apply the verified volatile baseline for this board, after a snapshot."""
        if self._reset_busy:
            self.notify("A baseline reset is already running.")
            return
        if not self.state.connected:
            self.notify("No keyboard connected.")
            return
        if not self.state.writable:
            self.notify("The session is read-only. Fix permissions first.")
            return
        baseline_spec = baseline.for_board(self.state.board)
        if baseline_spec is None:
            self.notify(
                f"No verified tuning baseline is available for {self.state.board.name}."
            )
            return
        body = (
            "\n".join(baseline_spec.preview_lines())
            + "\n\nThis does not touch the keymap, macros, advanced keys, "
              "hold/click, DKS or per-key colours."
            + "\nA tuning snapshot is saved automatically before the reset."
            + "\nChanges are volatile until you use Save to keyboard."
        )
        dialog = Adw.AlertDialog(heading="Reset tuning to baseline?", body=body)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("reset", "Reset")
        dialog.set_response_appearance("reset", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        def response(_dialog, response_id):
            if response_id == "reset":
                self._reset_tuning_now(baseline_spec)

        dialog.connect("response", response)
        dialog.present(self)

    def _reset_tuning_now(self, baseline_spec) -> None:
        if self._reset_busy:
            return
        try:
            snapshot = profiles.auto_backup(
                self.state,
                description="Tuning snapshot taken automatically before a baseline reset",
            )
        except (OSError, ValueError) as exc:
            self.notify(f"Could not create a safety snapshot: {exc}")
            return
        if snapshot is None:
            self.notify("No tuning state to snapshot; reset cancelled.")
            return
        self._reset_busy = True
        board = self.state.board

        def job(device):
            return baseline_spec.apply(device, board)

        def done(_actions):
            self._reset_busy = False
            self.notify(
                "Baseline applied. Tuning snapshot saved. "
                "Changes are volatile until Save to keyboard."
            )
            self.refresh()

        def error(exc):
            self._reset_busy = False
            self.notify(f"Reset did not complete: {exc}")
            self.refresh()

        self.worker.submit(job, callback=done, error=error, description="reset tuning")

    def apply_profile(self, profile) -> None:
        if not self.state.connected:
            self.notify("No keyboard connected.")
            return
        if not self.state.writable:
            self.notify("The session is read-only. Fix permissions first.")
            return
        persistent = profile.has_persistent_sections
        body = (
            f"{profile.description or 'No description.'}\n\n"
            + profiles.apply_preview(profile)
        )
        if profile.keymap_hex:
            try:
                keymap_bytes = len(bytes.fromhex(profile.keymap_hex))
            except ValueError:
                keymap_bytes = -1
            if keymap_bytes != self.state.board.keymap_size:
                body += (
                    f"\n\nWARNING: this backup's keymap is {keymap_bytes} bytes, "
                    f"but {self.state.board.name} expects "
                    f"{self.state.board.keymap_size}. Apply will stop before "
                    f"writing anything."
                )
        if persistent:
            body += (
                "\n\nThis is a full backup. Keymap, macros and advanced bindings "
                "are written to onboard memory immediately and cannot be undone "
                "from this dialog."
            )
        else:
            body += "\n\nTuning changes are volatile; use Save to keyboard to persist them."
        dialog = Adw.AlertDialog(heading=f"Apply “{profile.name}”?", body=body)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("apply", "Apply")
        dialog.set_response_appearance("apply", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("apply")
        dialog.set_close_response("cancel")

        def response(_dialog, response_id):
            if response_id == "apply":
                self._apply_profile_now(profile, persistent)

        dialog.connect("response", response)
        dialog.present(self)

    def _apply_profile_now(self, profile, persistent: bool) -> None:
        base_state = self.state
        include_keymap = bool(persistent and profile.keymap_hex)
        include_macros = bool(persistent and profile.macros_hex)
        include_advanced = bool(
            persistent and (profile.advanced_keys is not None
                            or profile.tap_dance is not None
                            or profile.dks is not None)
        )

        def job(device):
            return profile.apply(
                device,
                base_state,
                include_keymap=include_keymap,
                include_macros=include_macros,
                include_advanced=include_advanced,
            )

        def done(actions):
            self.notify(
                f"Applied “{profile.name}”" + (f": {', '.join(actions)}" if actions else " (no changes)")
            )
            self.refresh()

        def error(exc):
            self.notify(f"Could not apply “{profile.name}”: {exc}")

        self.worker.submit(job, callback=done, error=error, description="apply profile")

    # -- dialogs -----------------------------------------------------------
    def show_permissions(self) -> None:
        dialog = Adw.AlertDialog(
            heading="Keyboard access",
            body=(
                "The vendor HID collection is owned by root. The AUR and system "
                "packages install the rule for you. For AppImage, Flatpak or a "
                "source run, copy the command below once, then unplug and replug "
                "the keyboard."
            ),
        )
        rule = transport.udev_rule()
        command = (
            "sudo tee /etc/udev/rules.d/71-madlions.rules >/dev/null <<'EOF'\n"
            + rule
            + "EOF\n"
            "sudo udevadm control --reload-rules && sudo udevadm trigger\n"
        )
        text = Gtk.TextView()
        text.set_editable(False)
        text.set_monospace(True)
        text.get_buffer().set_text(command)
        text.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_min_content_height(210)
        scroller.set_min_content_width(560)
        scroller.set_child(text)
        dialog.set_extra_child(scroller)
        dialog.add_response("copy", "Copy command")
        dialog.add_response("close", "Close")
        dialog.set_response_appearance("copy", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("copy")
        dialog.set_close_response("close")

        def response(_dialog, response_id):
            if response_id == "copy":
                copy_text(command)
                self.notify("Command copied. Replug the keyboard afterwards.")

        dialog.connect("response", response)
        dialog.present(self)

    def show_about(self) -> None:
        about = Adw.AboutDialog(
            application_name=config.APP_NAME,
            application_icon=config.APP_ID,
            developer_name="Nasir A.",
            version=config.VERSION,
            website=config.PROJECT_URL,
            issue_url=config.ISSUES_URL,
            license_type=Gtk.License.MIT_X11,
            comments=(
                "Native configuration for MADLIONS magnetic-switch keyboards. "
                "Everything stays on your computer."
            ),
            developers=["Nasir A."],
        )
        about.present(self)

    def show_appearance(self) -> None:
        dialog = Adw.AlertDialog(heading="Appearance", body="Choose how Madlions Control looks.")
        group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        style = Adw.StyleManager.get_default()
        for label_text, scheme in (
            ("Follow system", Adw.ColorScheme.DEFAULT),
            ("Dark", Adw.ColorScheme.FORCE_DARK),
            ("Light", Adw.ColorScheme.FORCE_LIGHT),
        ):
            btn = Gtk.Button(label=label_text)
            btn.connect("clicked", lambda _b, s=scheme, d=dialog: self._set_scheme(s, d))
            group.append(btn)
        dialog.set_extra_child(group)
        dialog.add_response("close", "Close")
        dialog.present(self)

    def _set_scheme(self, scheme, dialog) -> None:
        Adw.StyleManager.get_default().set_color_scheme(scheme)
        self._settings.theme = (
            "system" if scheme == Adw.ColorScheme.DEFAULT
            else "dark" if scheme == Adw.ColorScheme.FORCE_DARK else "light"
        )
        settings.save(self._settings)
        dialog.close()

    def show_diagnostics(self) -> None:
        def got(report):
            text = Gtk.TextView()
            text.set_editable(False)
            text.set_monospace(True)
            text.get_buffer().set_text(json.dumps(report, indent=2, default=str))
            scroller = Gtk.ScrolledWindow()
            scroller.set_min_content_height(360)
            scroller.set_min_content_width(620)
            scroller.set_child(text)
            dialog = Adw.AlertDialog(
                heading="Device diagnostics",
                body="Read-only information you can attach to an issue. Nothing is uploaded.",
            )
            dialog.set_extra_child(scroller)
            dialog.add_response("copy", "Copy JSON")
            dialog.add_response("close", "Close")
            dialog.set_response_appearance("copy", Adw.ResponseAppearance.SUGGESTED)
            dialog.connect(
                "response",
                lambda _d, r: copy_text(json.dumps(report, indent=2, default=str))
                if r == "copy" else None,
            )
            dialog.present(self)

        def error(exc):
            self.notify(f"Diagnostics failed: {exc}")

        if not self.state.connected:
            self.notify("No keyboard connected.")
            return
        self.worker.submit(lambda device: device.read_report(), callback=got, error=error,
                           description="diagnostics")

    # -- shutdown ----------------------------------------------------------
    def _on_close(self, *_args) -> bool:
        self._settings.window_width = self.get_width()
        self._settings.window_height = self.get_height()
        settings.save(self._settings)
        self.worker.stop()
        return False
