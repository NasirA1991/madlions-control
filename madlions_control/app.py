"""GTK application entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

from . import config, settings
from .ui.window import MainWindow
from .worker import DeviceWorker


class MadlionsApplication(Adw.Application):
    def __init__(self, *, demo: bool = False, page: str | None = None) -> None:
        super().__init__(
            application_id=config.APP_ID,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        self.demo = demo
        self.start_page = page
        self.window: MainWindow | None = None
        self.worker: DeviceWorker | None = None
        GLib.set_application_name(config.APP_NAME)
        GLib.set_prgname(config.APP_SLUG)
        self.connect("startup", self._on_startup)
        self.connect("activate", self._on_activate)
        self.connect("shutdown", self._on_shutdown)

    # -- startup -----------------------------------------------------------
    def _on_startup(self, _app) -> None:
        display = Gdk.Display.get_default()
        if display is not None:
            Gtk.Window.set_default_icon_name(config.APP_ID)
            theme = Gtk.IconTheme.get_for_display(display)
            icon_root = config.data_dir() / "icons"
            if icon_root.is_dir():
                theme.add_search_path(str(icon_root))
            provider = Gtk.CssProvider()
            css = Path(__file__).parent / "ui" / "style.css"
            try:
                provider.load_from_path(str(css))
                Gtk.StyleContext.add_provider_for_display(
                    display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
                )
            except GLib.Error as exc:
                print(f"Could not load the stylesheet: {exc}", file=sys.stderr)
        self._apply_theme()
        self.worker = DeviceWorker(
            demo=self.demo,
            post=lambda fn, args: GLib.idle_add(fn, *args),
            on_event=self._on_worker_event,
        )
        self.worker.start()
        for action, accel in (
            ("win.save", "<Control>s"),
            ("win.refresh", "<Control>r"),
            ("win.shortcuts", "<Control>question"),
            ("app.quit", "<Control>q"),
        ):
            self.set_accels_for_action(action, [accel])
        for number in range(1, 9):
            self.set_accels_for_action(f"win.page-{number}", [f"<Control>{number}"])

    def _apply_theme(self) -> None:
        style = Adw.StyleManager.get_default()
        theme = settings.load().theme
        if theme == "dark":
            style.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        elif theme == "light":
            style.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
        else:
            style.set_color_scheme(Adw.ColorScheme.DEFAULT)

    def _on_activate(self, _app) -> None:
        if self.window is None:
            assert self.worker is not None
            self.window = MainWindow(self, self.worker, demo=self.demo)
        self.window.present()
        if self.start_page:
            self.window.go(self.start_page)
            self.start_page = None

    def _on_worker_event(self, name: str, payload) -> None:
        if self.window is not None:
            self.window.on_worker_event(name, payload)

    def _on_shutdown(self, _app) -> None:
        if self.worker is not None:
            self.worker.stop()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="madlions-control",
        description="Native configuration for MADLIONS magnetic-switch keyboards.",
    )
    parser.add_argument("--demo", action="store_true", help="run with a simulated keyboard")
    parser.add_argument(
        "--page", default=None,
        choices=("overview", "perkey", "lighting", "keymap", "macros", "advanced", "test", "profiles"),
        help="open a specific page",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {config.VERSION}")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args, remaining = parser.parse_known_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    app = MadlionsApplication(demo=args.demo, page=args.page)
    return app.run([sys.argv[0]] + remaining)


if __name__ == "__main__":
    raise SystemExit(main())
