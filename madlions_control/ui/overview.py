"""Overview page: the state of the keyboard at a glance."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402

from .. import boards, keycodes, layout, profiles
from ..lighting import effect_name, rgb_to_hex
from .keyboard import KeyboardCanvas
from .widgets import Page, Section, Stat, button, label, row, separator, toast  # noqa: F401


class OverviewPage(Page):
    title = "Overview"
    subtitle = "Everything that matters, one screen."

    def __init__(self, window) -> None:
        super().__init__(window, max_width=1040)
        self._build()

    def _build(self) -> None:
        self.add(self.header())

        self.hero = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=22)
        self.hero.add_css_class("hero")
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        left.set_hexpand(True)
        self.hero_eyebrow = label("MADLIONS", "eyebrow")
        self.hero_title = label("Your keyboard, tuned.", "hero-title", wrap=True)
        self.hero_sub = label(
            "Per-key actuation, rapid trigger, lighting and keymaps — natively.",
            "hero-sub", wrap=True,
        )
        self.hero_meta = label("", "hero-meta")
        left.append(self.hero_eyebrow)
        left.append(self.hero_title)
        left.append(self.hero_sub)
        left.append(self.hero_meta)
        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        actions.set_margin_top(10)
        tune = button("Tune per key", suggested=True)
        tune.connect("clicked", lambda _b: self.window.go("perkey"))
        light = button("Lighting", icon="display-brightness-symbolic", flat=True)
        light.add_css_class("flat")
        light.connect("clicked", lambda _b: self.window.go("lighting"))
        test = button("Test keys", icon="utilities-system-monitor-symbolic", flat=True)
        test.add_css_class("flat")
        test.connect("clicked", lambda _b: self.window.go("test"))
        actions.append(tune)
        actions.append(light)
        actions.append(test)
        left.append(actions)
        self.hero.append(left)
        self.hero_canvas = KeyboardCanvas(height=188, interactive=False)
        self.hero_canvas.set_hexpand(False)
        self.hero_canvas.set_size_request(380, 188)
        self.hero.append(self.hero_canvas)
        self.add(self.hero)

        self.banner = Section(tight=True)
        self.banner.set_visible(False)
        self.add(self.banner)

        grid = Gtk.Grid(column_spacing=10, row_spacing=10, column_homogeneous=True)
        self.stat_actuation = Stat("—", "actuation range")
        self.stat_rt = Stat("—", "rapid trigger keys", accent=True)
        self.stat_layout = Stat("—", "matrix")
        self.stat_profile = Stat("—", "profiles")
        for index, stat in enumerate((self.stat_actuation, self.stat_rt,
                                      self.stat_layout, self.stat_profile)):
            stat.set_hexpand(True)
            grid.attach(stat, index, 0, 1, 1)
        self.add(grid)

        quick = Section("Quick actions", "No browser tab, no vendor service.")
        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        for text, icon, page in (
            ("Keymap", "view-list-symbolic", "keymap"),
            ("Advanced", "applications-engineering-symbolic", "advanced"),
            ("Profiles", "bookmark-new-symbolic", "profiles"),
        ):
            btn = button(text, icon=icon)
            btn.set_hexpand(True)
            btn.connect("clicked", lambda _b, target=page: self.window.go(target))
            buttons.append(btn)
        quick.add(buttons)
        self.add(quick)

        glance = Section("At a glance", "Live values read from the keyboard.")
        self.glance_values = {}
        for key, title in (
            ("nkro", "Rollover"),
            ("win_lock", "Windows key"),
            ("wasd", "WASD / arrows"),
            ("mac", "Platform"),
            ("game", "Game mode"),
            ("deadband", "Dead band"),
            ("light", "Lighting"),
            ("side", "Side light"),
        ):
            item = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            item.add_css_class("list-row")
            item.append(label(title, "row-sub"))
            value = label("—", "row-title", xalign=1.0)
            value.set_hexpand(True)
            value.set_xalign(1.0)
            item.append(value)
            self.glance_values[key] = value
            glance.add(item)
            glance.add(separator())
        last = glance.content.get_last_child()
        if isinstance(last, Gtk.Separator):
            glance.content.remove(last)
        self.add(glance)

        manage = button("Manage", icon="view-list-symbolic")
        profiles_card = Section(
            "Profiles",
            "Save tuning profiles, or create a full backup, and switch in one click.",
            trailing=manage,
        )
        manage.connect("clicked", lambda _b: self.window.go("profiles"))
        self.profile_rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        profiles_card.add(self.profile_rows)
        self.add(profiles_card)

    # -- state -------------------------------------------------------------
    def on_state(self, state) -> None:
        if not state.connected or not state.info:
            self.hero_canvas.set_state(state)
            self.hero_title.set_text("Keyboard not connected")
            self.hero_sub.set_text(
                "Plug in a MADLIONS keyboard. If it is already connected, check "
                "the USB cable and the permission note below."
            )
            self.hero_meta.set_text("")
            self.stat_actuation.set("—", "actuation range")
            self.stat_rt.set("—", "rapid trigger keys")
            self.stat_layout.set("—", "matrix")
            self.stat_profile.set("—", "profiles")
            if state.error:
                self._show_banner(state.error, error=not state.permission_error)
            else:
                self.banner.set_visible(False)
            return
        info = state.info
        self.hero_eyebrow.set_text(info.board.name.upper() + "  ·  " + info.usb_id)
        self.hero_title.set_text(self._headline(state))
        self.hero_sub.set_text(self._subline(state))
        self.hero_meta.set_text(
            f"{info.board.rows} × {info.board.cols} matrix  ·  {state.layers} layers  ·  "
            f"firmware protocol {info.protocol_label}"
            + ("  ·  read-only" if not info.writable else "")
        )
        self.hero_canvas.set_state(state)
        self.hero_canvas.set_mode("actuation")
        self.stat_actuation.set(
            f"{min(state.actuation):.2f}–{max(state.actuation):.2f}" if state.actuation else "—",
            "actuation range mm",
        )
        enabled = sum(1 for rt in state.rapid_trigger if rt.enabled)
        self.stat_rt.set(f"{enabled}", f"of {len(state.rapid_trigger)} keys with RT")
        self.stat_layout.set(f"{info.board.rows}×{info.board.cols}", f"{info.board.total_keys} matrix cells")
        saved = len(profiles.list_profiles())
        self.stat_profile.set(str(saved), "saved profiles")
        self._update_glance(state)
        self._update_profiles()
        if state.permission_error:
            self._show_banner(
                "The keyboard is visible but this user cannot open its HID node. "
                "Install the udev rule, then replug the keyboard.",
                permission=True,
            )
        elif not info.writable:
            self._show_banner(
                f"Read-only session. {info.read_only_reason}. Reading and the test "
                f"page are fully available.",
                warning=True,
            )
        elif state.warnings:
            self._show_banner("Some optional values could not be read: " + "; ".join(state.warnings[:2]), warning=True)
        else:
            self.banner.set_visible(False)

    def _headline(self, state) -> str:
        info = state.info
        if info is None:
            return "Your keyboard, tuned."
        if not state.actuation:
            return "Reading your keyboard…"
        enabled = sum(1 for rt in state.rapid_trigger if rt.enabled)
        if enabled == len(state.rapid_trigger):
            return "Every key is ready to fire."
        if enabled:
            return f"{enabled} keys are in rapid-trigger mode."
        if min(state.actuation) <= 0.8:
            return "Built for speed."
        return "A quieter, more deliberate feel."

    def _subline(self, state) -> str:
        if not state.actuation:
            return "Fetching actuation points and rapid-trigger settings."
        enabled = sum(1 for rt in state.rapid_trigger if rt.enabled)
        return (
            f"Actuation is set between {min(state.actuation):.2f} and "
            f"{max(state.actuation):.2f} mm. "
            + ("Rapid trigger is off everywhere." if not enabled else
               f"{enabled} keys use rapid trigger at {state.rt_of(0, 0).press_mm:.2f} mm.")
        )

    def _update_glance(self, state) -> None:
        values = {
            "nkro": "N-key rollover" if state.features.nkro else "6-key rollover",
            "win_lock": "Locked" if state.features.win_lock else "Active",
            "wasd": "Swapped" if state.features.wasd_swap else "Standard",
            "mac": "macOS" if state.features.mac_mode else "Windows",
            "game": "On" if state.game_mode else "Off",
            "deadband": f"{state.dead_band.top_mm:.2f} / {state.dead_band.bottom_mm:.2f} mm",
            "light": f"{effect_name(state.light.effect)} · {state.light.brightness}",
            "side": f"Mode {state.box_light.mode} · {state.box_light.brightness}",
        }
        for key, value in values.items():
            self.glance_values[key].set_text(value)

    def _update_profiles(self) -> None:
        while child := self.profile_rows.get_first_child():
            self.profile_rows.remove(child)
        saved = profiles.list_profiles()
        for profile in saved[:3]:
            widget = row(profile.name, profiles.profile_summary(profile),
                         trailing=button("Apply", flat=True))
            apply_btn = widget.get_last_child()
            apply_btn.connect("clicked", lambda _b, p=profile: self.window.apply_profile(p))
            self.profile_rows.append(widget)
        if not saved:
            empty = label("No profiles yet. Create one from the Profiles page.", "muted small")
            self.profile_rows.append(empty)
        elif len(saved) > 3:
            self.profile_rows.append(label(f"+ {len(saved) - 3} more in Profiles", "muted small"))

    def _show_banner(self, message: str, *, error: bool = False,
                     warning: bool = False, permission: bool = False) -> None:
        while child := self.banner.content.get_first_child():
            self.banner.content.remove(child)
        self.banner.set_visible(True)
        css = "error-box" if error else "warning-box" if warning else "info-box"
        text = label(message, css, wrap=True)
        self.banner.add(text)
        if permission:
            fix = button("How to fix permissions", icon="dialog-password-symbolic")
            fix.connect("clicked", lambda _b: self.window.show_permissions())
            self.banner.add(fix)
