"""Reusable GTK4/libadwaita widgets for the app."""

from __future__ import annotations

import math
from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")

from gi.repository import Adw, Gdk, GLib, Gtk, Pango  # noqa: E402


def label(text: str, css: str | None = None, *, wrap: bool = False,
          xalign: float = 0.0, ellipsize: bool = False) -> Gtk.Label:
    widget = Gtk.Label(label=text, xalign=xalign)
    if wrap:
        widget.set_wrap(True)
        widget.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
    if ellipsize:
        widget.set_ellipsize(Pango.EllipsizeMode.END)
        widget.set_hexpand(True)
    if css:
        for name in css.split():
            widget.add_css_class(name)
    return widget


def icon_button(icon: str, tooltip: str, *, css: str | None = None) -> Gtk.Button:
    button = Gtk.Button()
    button.set_child(Gtk.Image.new_from_icon_name(icon))
    button.set_tooltip_text(tooltip)
    button.add_css_class("flat")
    if css:
        button.add_css_class(css)
    return button


def button(text: str, *, icon: str | None = None, suggested: bool = False,
           flat: bool = False) -> Gtk.Button:
    widget = Gtk.Button(label=text) if not icon else Gtk.Button()
    if icon:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        box.append(Gtk.Image.new_from_icon_name(icon))
        box.append(label(text))
        widget.set_child(box)
    if suggested:
        widget.add_css_class("suggested-action")
    if flat:
        widget.add_css_class("flat")
    return widget


def pill(text: str, css: str = "") -> Gtk.Label:
    widget = label(text, "pill")
    if css:
        widget.add_css_class(css)
    return widget


def dot(css: str = "") -> Gtk.Box:
    widget = Gtk.Box()
    widget.set_size_request(8, 8)
    widget.add_css_class("status-dot")
    if css:
        widget.add_css_class(css)
    return widget


class StatusPill(Gtk.Box):
    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=7)
        self.add_css_class("connection-pill")
        self._dot = Gtk.Box()
        self._dot.set_size_request(7, 7)
        self._dot.add_css_class("status-dot")
        self.append(self._dot)
        self._label = label("Connecting", "tiny")
        self._label.add_css_class("connection-pill-label")
        self.append(self._label)
        self.set_state("waiting", "Connecting")

    def set_state(self, status: str, text: str) -> None:
        for css in ("online", "offline", "waiting"):
            self.remove_css_class(css)
        self.add_css_class(status)
        self._dot.remove_css_class("off")
        self._dot.remove_css_class("wait")
        if status == "offline":
            self._dot.add_css_class("off")
        elif status == "waiting":
            self._dot.add_css_class("wait")
        self._label.set_text(text)


class Stat(Gtk.Box):
    def __init__(self, value: str, caption: str, accent: bool = False) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.add_css_class("stat")
        self.value = label(value, "stat-value")
        self.caption = label(caption, "stat-label")
        self.append(self.value)
        self.append(self.caption)
        if accent:
            self.value.add_css_class("stat-accent")

    def set(self, value: str, caption: str | None = None) -> None:
        self.value.set_text(value)
        if caption is not None:
            self.caption.set_text(caption)


class Section(Gtk.Box):
    """A card-like section with a title and an optional trailing widget."""

    def __init__(self, title: str = "", subtitle: str = "", *,
                 tight: bool = False, trailing: Gtk.Widget | None = None) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.add_css_class("card")
        if tight:
            self.add_css_class("tight")
        self._content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.trailing = trailing
        if title or trailing:
            head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            titles = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
            titles.set_hexpand(True)
            if title:
                titles.append(label(title, "card-title"))
            if subtitle:
                titles.append(label(subtitle, "card-sub", wrap=True))
            head.append(titles)
            if trailing is not None:
                head.append(trailing)
            self.append(head)
        self.append(self._content)

    @property
    def content(self) -> Gtk.Box:
        return self._content

    def add(self, widget: Gtk.Widget) -> None:
        self._content.append(widget)


def row(title: str, subtitle: str = "", *, trailing: Gtk.Widget | None = None,
        css: str = "list-row") -> Gtk.Box:
    widget = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    widget.add_css_class(css)
    text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
    text_box.set_hexpand(True)
    text_box.append(label(title, "row-title"))
    if subtitle:
        text_box.append(label(subtitle, "row-sub", wrap=True))
    widget.append(text_box)
    if trailing is not None:
        widget.append(trailing)
    return widget


def separator() -> Gtk.Separator:
    widget = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
    widget.set_margin_top(2)
    widget.set_margin_bottom(2)
    return widget


class LabeledScale(Gtk.Box):
    def __init__(
        self,
        title: str,
        lower: float,
        upper: float,
        step: float,
        *,
        value: float | None = None,
        unit: str = "",
        subtitle: str = "",
        digits: int = 2,
        on_change: Callable[[float], None] | None = None,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        self.add_css_class("scale-row")
        self._on_change = on_change
        self._digits = digits
        self._updating = False
        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._title = label(title, "scale-title")
        self._title.set_hexpand(True)
        head.append(self._title)
        self._value = label("", "scale-value")
        head.append(self._value)
        self.append(head)
        if subtitle:
            self.append(label(subtitle, "tiny muted", wrap=True))
        adjustment = Gtk.Adjustment(value=value if value is not None else lower,
                                    lower=lower, upper=upper,
                                    step_increment=step, page_increment=step * 10)
        self.scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL,
                               adjustment=adjustment)
        self.scale.set_draw_value(False)
        self.scale.set_round_digits(digits)
        self.scale.set_hexpand(True)
        self.scale.add_mark(lower, Gtk.PositionType.BOTTOM, None)
        self.scale.add_mark(upper, Gtk.PositionType.BOTTOM, None)
        self.scale.connect("value-changed", self._changed)
        self.append(self.scale)
        self._unit = unit
        self._render(adjustment.get_value())

    def _render(self, value: float) -> None:
        self._value.set_text(f"{value:.{self._digits}f}{self._unit}")

    def _changed(self, scale: Gtk.Scale) -> None:
        value = scale.get_value()
        self._render(value)
        if self._updating or self._on_change is None:
            return
        self._on_change(value)

    def set_value(self, value: float) -> None:
        self._updating = True
        try:
            self.scale.set_value(value)
        finally:
            self._updating = False
        self._render(value)

    def set_sensitive(self, sensitive: bool) -> None:
        super().set_sensitive(sensitive)


class SwitchRow(Gtk.Box):
    def __init__(self, title: str, subtitle: str = "",
                 on_toggle: Callable[[bool], None] | None = None) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.add_css_class("list-row")
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        text.set_hexpand(True)
        text.append(label(title, "row-title"))
        if subtitle:
            text.append(label(subtitle, "row-sub", wrap=True))
        self.append(text)
        self.switch = Gtk.Switch()
        self.switch.set_valign(Gtk.Align.CENTER)
        self._on_toggle = on_toggle
        self._updating = False
        if on_toggle:
            self.switch.connect("state-set", self._toggled)
        self.append(self.switch)

    def _toggled(self, switch: Gtk.Switch, state: bool) -> bool:
        if not self._updating and self._on_toggle:
            self._on_toggle(bool(state))
        return False

    def set_active(self, active: bool) -> None:
        self._updating = True
        try:
            self.switch.set_active(bool(active))
        finally:
            self._updating = False


class Debouncer:
    """Call ``callback`` once, a short time after the last trigger."""

    def __init__(self, delay_ms: int, callback: Callable[[], None]) -> None:
        self._delay = delay_ms
        self._callback = callback
        self._source = 0

    def trigger(self) -> None:
        if self._source:
            GLib.source_remove(self._source)
        self._source = GLib.timeout_add(self._delay, self._fire)

    def _fire(self) -> bool:
        self._source = 0
        self._callback()
        return False


def copy_text(text: str) -> None:
    """Put UTF-8 text on the default clipboard without deprecated APIs."""
    display = Gdk.Display.get_default()
    if display is None:
        return
    clipboard = display.get_clipboard()
    provider = Gdk.ContentProvider.new_for_bytes(
        "text/plain;charset=utf-8", GLib.Bytes.new(text.encode("utf-8"))
    )
    clipboard.set_content(provider)


def toast(overlay: Adw.ToastOverlay, text: str, *, timeout: int = 3) -> None:
    toast_widget = Adw.Toast.new(text)
    toast_widget.set_timeout(timeout)
    overlay.add_toast(toast_widget)


class Page(Gtk.ScrolledWindow):
    """A consistently padded page with an Adw.Clamp content column."""

    title = ""
    subtitle = ""

    def __init__(self, window, *, max_width: int = 980, spacing: int = 16) -> None:
        super().__init__()
        self.window = window
        self.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.add_css_class("page-scroll")
        self.set_vexpand(True)
        self.body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=spacing)
        self.body.add_css_class("page-body")
        clamp = Adw.Clamp()
        clamp.set_maximum_size(max_width)
        clamp.set_tightening_threshold(720)
        clamp.set_child(self.body)
        self.set_child(clamp)

    def add(self, widget: Gtk.Widget) -> None:
        self.body.append(widget)

    def header(self, actions: Gtk.Widget | None = None) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        text.set_hexpand(True)
        text.append(label(self.title, "page-title"))
        if self.subtitle:
            text.append(label(self.subtitle, "page-subtitle", wrap=True))
        box.append(text)
        if actions is not None:
            actions.set_valign(Gtk.Align.CENTER)
            box.append(actions)
        return box

    # -- lifecycle hooks ---------------------------------------------------
    def on_state(self, state) -> None:  # noqa: ANN001 - page protocol
        pass

    def on_show(self) -> None:
        pass

    def on_hide(self) -> None:
        pass

    def notify(self, text: str) -> None:
        self.window.notify(text)


class KeyValueRow(Gtk.Box):
    def __init__(self, key: str, value: str = "") -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.add_css_class("list-row")
        self.append(label(key, "row-sub"))
        self._value = label(value, "row-title", xalign=1.0)
        self._value.set_hexpand(True)
        self._value.set_xalign(1.0)
        self.append(self._value)

    def set(self, value: str) -> None:
        self._value.set_text(value)
