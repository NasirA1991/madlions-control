# Development

Madlions Control is a Python 3 GTK4 / libadwaita application. It talks to the
keyboard over `/dev/hidraw` directly; there is no daemon, no libhidapi dependency
and no JavaScript bridge.

## Requirements

- Python 3.10+
- PyGObject, GTK 4.10+ (the colour dialog is used), libadwaita 1.5+
- pycairo
- A C compiler is not needed; the application is pure Python

On Arch / CachyOS:

```bash
sudo pacman -S python-gobject gtk4 libadwaita python-cairo hicolor-icon-theme
```

On Debian / Ubuntu:

```bash
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 python3-cairo hicolor-icon-theme
```

## Run

```bash
python3 -m madlions_control              # real keyboard
python3 -m madlions_control --demo       # simulated keyboard
python3 -m madlions_control --demo --page perkey
python3 -m madlions_control.cli --demo status
```

Demo mode does not open any device and is safe for screenshots and UI work.

## Tests

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q madlions_control
```

`tests/test_device.py` uses a fake transport and validates packet framing and
the write gate. `tests/test_core.py` covers layouts, keycodes, profiles, macros,
travel encoding and demo state.

## Hardware checks

The verified board is a MAD68 HE RGB (`373B:1058`, firmware protocol 9). Read
only first:

```bash
madlionsctl status
madlionsctl report --json
madlionsctl test --seconds 3
```

Writes are gated by protocol version and board verification. For a new board
that shares the 32-byte controller, use the CLI with `--allow-unverified` only
after taking a report and understanding the risk. The GUI deliberately stays
read-only on unverified boards.

Before changing writes on a new board, capture a full backup:

```python
from madlions_control import state as st
from madlions_control.device import MadlionsDevice
d = MadlionsDevice.open()
s = st.load_basic(d)
s = st.load_colors(d, s)
s = st.load_keymap(d, s)
s = st.load_macros(d, s)
s = st.load_advanced(d, s)
```

## Layout

```
madlions_control/
  transport.py       hidraw discovery, request/response, udev rule text
  device.py          packet layouts, writes, safety gate, telemetry
  boards.py          supported product IDs and matrix geometry
  layout.py          physical 60% / 65% / grid layouts
  keycodes.py        QMK keycode table and search
  state.py           UI state model and lazy loaders
  worker.py          single I/O thread, job queue, 60 Hz test stream
  profiles.py        JSON profiles, presets, backups, apply
  baseline.py        verified per-board tuning reset, with read-back checks
  macros_codec.py    VIA/Vial macro buffer codec
  lighting.py        effect metadata and colour helpers
  ui/                GTK pages and the Cairo keyboard widget
  app.py             Adw.Application entry point
  cli.py             madlionsctl
```

All device traffic is serialized on the worker thread. UI callbacks are posted
to the GLib main loop. Writes with `flash=FLASH_NORMAL` are volatile; only
`commit()` and `save_lighting()` persist.

## Screenshots

```bash
./tools/screenshots.sh
```

This uses `xvfb-run`, ImageMagick and python-xlib. It writes the images in
`docs/screenshots/` at a 1180 × 780 window size, with the demo keyboard seeded
with a varied setup.

## Packaging

```bash
version=$(python3 -c "from madlions_control.config import VERSION; print(VERSION)")
./packaging/appimage/build.sh "$version" dist
./packaging/flatpak/build.sh "$version" dist
makepkg -si
```

- AppImage: application only; the host provides GTK/PyGObject.
- Flatpak: uses the GNOME runtime; raw devices via `--device=all`.

## Releases

Releases are built by GitHub Actions from `v<version>` tags. Keep `VERSION` in
`madlions_control/config.py` and `pyproject.toml` in sync, and regenerate the
screenshots if the UI changed. Do not upload release assets by hand.
