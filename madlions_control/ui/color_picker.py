"""A compact, app-styled colour picker."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402

from ..lighting import hsv_to_rgb, rgb_to_hsv, rgb_to_hex, hex_to_rgb

PALETTE = (
    "#ff4d6d", "#ff2e63", "#e8365d", "#ff7a45", "#ff9f1c", "#ffbf00",
    "#f5d020", "#c6e63a", "#74d680", "#33d17a", "#2ec27e", "#26c6da",
    "#22d3ee", "#4dabf7", "#3b82f6", "#6366f1", "#8b5cf6", "#a855f7",
    "#d946ef", "#ec4899", "#f472b6", "#ffffff", "#a1a1aa", "#3f3f46",
)


class ColorPreview(Gtk.DrawingArea):
    def __init__(self, width: int = 300, height: int = 54) -> None:
        super().__init__()
        self.set_content_height(height)
        self.set_size_request(width, height)
        self.color = (255, 77, 109)
        self.set_draw_func(self._draw)

    def set_color(self, color: tuple[int, int, int]) -> None:
        self.color = color
        self.queue_draw()

    def _draw(self, _area, cr, width, height):
        r, g, b = (component / 255 for component in self.color)
        cr.set_source_rgb(r, g, b)
        cr.rectangle(0, 0, width, height)
        cr.fill()


class ColorPickerDialog(Adw.Dialog):
    def __init__(self, current: tuple[int, int, int], on_select, *,
                 title: str = "Colour") -> None:
        super().__init__()
        self.set_title(title)
        self.set_content_width(380)
        self.set_content_height(500)
        self._on_select = on_select
        self._h, self._s, self._v = rgb_to_hsv(current)

        view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.set_show_back_button(False)
        header.set_show_start_title_buttons(False)
        header.set_title_widget(Adw.WindowTitle(title=title, subtitle="Applies immediately"))
        cancel = Gtk.Button(label="Cancel")
        cancel.connect("clicked", lambda _b: self.close())
        apply = Gtk.Button(label="Use colour")
        apply.add_css_class("suggested-action")
        apply.connect("clicked", lambda _b: self._apply())
        header.pack_start(cancel)
        header.pack_end(apply)
        view.add_top_bar(header)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(14)
        box.set_margin_bottom(18)
        box.set_margin_start(18)
        box.set_margin_end(18)

        self.preview = ColorPreview()
        box.append(self.preview)

        hex_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        hex_row.append(Gtk.Label(label="Hex", xalign=0))
        self.hex_entry = Gtk.Entry()
        self.hex_entry.set_hexpand(True)
        self.hex_entry.set_placeholder_text("#ff4d6d")
        self.hex_entry.connect("activate", self._hex_entered)
        hex_row.append(self.hex_entry)
        box.append(hex_row)

        palette = Gtk.Grid(column_spacing=6, row_spacing=6, column_homogeneous=True)
        for index, text in enumerate(PALETTE):
            button = Gtk.Button()
            button.add_css_class("color-swatch-button")
            button.set_size_request(30, 26)
            button.set_tooltip_text(text)
            provider = Gtk.CssProvider()
            r, g, b = hex_to_rgb(text)
            provider.load_from_data(
                f"button {{ background: rgb({r},{g},{b}); border-radius: 7px;"
                f" border: 1px solid alpha(white, 0.22); }}".encode()
            )
            button.get_style_context().add_provider(provider, 800)
            button.connect("clicked", lambda _b, value=text: self._hex_entered(None, value))
            palette.attach(button, index % 8, index // 8, 1, 1)
        box.append(palette)

        self.hue = self._scale("Hue", 0, 360, self._h, self._changed)
        self.saturation = self._scale("Saturation", 0, 100, self._s, self._changed)
        self.value = self._scale("Brightness", 0, 100, self._v, self._changed)
        for widget in (self.hue, self.saturation, self.value):
            box.append(widget)

        view.set_content(box)
        self.set_child(view)
        self._update_preview()

    def _scale(self, name: str, lower: float, upper: float, value: float, callback) -> Gtk.Box:
        row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        label = Gtk.Label(label=name, xalign=0)
        label.set_hexpand(True)
        label.add_css_class("scale-title")
        readout = Gtk.Label(label=f"{value:.0f}", xalign=1)
        readout.add_css_class("scale-value")
        head.append(label)
        head.append(readout)
        row.append(head)
        adjustment = Gtk.Adjustment(value=value, lower=lower, upper=upper,
                                    step_increment=1, page_increment=10)
        scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=adjustment)
        scale.set_draw_value(False)
        scale.set_hexpand(True)
        scale.connect("value-changed", lambda s: callback(s, readout))
        row.append(scale)
        row._scale = scale  # type: ignore[attr-defined]
        row._readout = readout  # type: ignore[attr-defined]
        return row

    def _changed(self, scale: Gtk.Scale, readout: Gtk.Label) -> None:
        readout.set_text(f"{scale.get_value():.0f}")
        self._h = self.hue._scale.get_value() if hasattr(self, "hue") else self._h
        self._s = self.saturation._scale.get_value() if hasattr(self, "saturation") else self._s
        self._v = self.value._scale.get_value() if hasattr(self, "value") else self._v
        self._update_preview()

    def _update_preview(self) -> None:
        color = hsv_to_rgb(self._h, self._s, self._v)
        self.preview.set_color(color)
        self.hex_entry.set_text(rgb_to_hex(color))

    def _hex_entered(self, _entry, text: str | None = None) -> None:
        try:
            color = hex_to_rgb(text if text is not None else self.hex_entry.get_text())
        except ValueError:
            return
        self._h, self._s, self._v = rgb_to_hsv(color)
        self.hue._scale.set_value(self._h)
        self.saturation._scale.set_value(self._s)
        self.value._scale.set_value(self._v)
        self._update_preview()

    def _apply(self) -> None:
        self._on_select(hsv_to_rgb(self._h, self._s, self._v))
        self.close()
