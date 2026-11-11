# Installation

Madlions Control is a Python and GTK4 application. There is no C extension to
build, but GTK, libadwaita and their Python bindings must be available. The AUR
packages install everything for you; the Flatpak and AppImage reduce the setup
work but do not remove the need for a host udev rule.

## Choose a method

| Method | Installs the CLI | Installs the udev rule | Best for |
|---|---|---|---|
| AUR `madlions-control` | Yes | Yes | Arch Linux users who want a packaged release. |
| AUR `madlions-control-git` | Yes | Yes | Arch Linux users who want `main`. |
| Flatpak | No | No (manual rule) | A sandboxed GUI with the GNOME runtime. |
| AppImage | No | No (manual rule) | A portable GUI with no package manager. |
| Source | Yes | System install only | Development, packaging, or a `--user` install. |

All methods use the same application data format, so profiles can be copied
between them. Configuration and profiles live in your home directory; see
[Data locations](#data-locations).

## Requirements

- Linux with `hidraw` support (the standard kernel HID driver).
- Python **3.10 or newer** for the AppImage and source installs.
- GTK **4.10 or newer** and libadwaita **1.5 or newer**.
- PyGObject, PangoCairo, and pycairo bindings.
- A desktop icon theme; `hicolor-icon-theme` provides the application icon.

Install the host packages for your distribution:

**Arch Linux**

```bash
sudo pacman -S --needed python-gobject gtk4 libadwaita python-cairo hicolor-icon-theme
```

**Debian / Ubuntu**

```bash
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 python3-cairo hicolor-icon-theme
```

**Fedora**

```bash
sudo dnf install python3-gobject gtk4 libadwaita python3-cairo hicolor-icon-theme
```

The AUR package pulls in the equivalent dependencies automatically. A desktop
session on Wayland or X11 is supported; a headless machine can use the CLI, but
the GUI needs a display.

Distributions that still ship GTK older than 4.10 or libadwaita older than 1.5
are not supported for AppImage or source installs. Use the Flatpak, which
provides the matching runtime, or a newer distribution release.

## Arch Linux (AUR)

Install the latest tagged release:

```bash
paru -S madlions-control
```

Or track `main`:

```bash
paru -S madlions-control-git
```

`yay -S ...` works the same way. The package installs:

- `/usr/bin/madlions-control` and `/usr/bin/madlionsctl`;
- the Python package under `/usr/lib/madlions-control`;
- the desktop entry, icons, and AppStream metadata;
- `/usr/lib/udev/rules.d/71-madlions.rules`.

The udev rule is installed automatically. Unplug and replug the keyboard once
after installation so the new rule applies.

The stable package verifies the release tarball's SHA-256. The `-git` package
builds from the current `main` commit and does not use a fixed checksum.

## Flatpak

Download `madlions-control-<version>-x86_64.flatpak` from the
[releases page](https://github.com/NasirA1991/madlions-control/releases), then:

```bash
flatpak install --user ./madlions-control-*-x86_64.flatpak
flatpak run io.github.madlionscontrol.MadlionsControl
```

The bundle uses the GNOME 50 runtime (`org.gnome.Platform`). If the runtime is
not installed, Flatpak downloads it from your configured remote. The app runs
with `--device=all` because Flatpak cannot yet limit device access to one
`/dev/hidraw` node. The Flatpak provides the GUI only; it does not include
`madlionsctl`.

The host still needs the udev rule so your user can open the device. See
[Permissions](#permissions).

Update or remove it with:

```bash
flatpak update io.github.madlionscontrol.MadlionsControl
flatpak uninstall io.github.madlionscontrol.MadlionsControl
```

Flatpak data is stored under `~/.var/app/io.github.madlionscontrol.MadlionsControl/`.
Uninstalling the app leaves that directory in place; delete it manually if you
also want to remove settings and profiles.

## AppImage

Download `madlions-control-<version>-x86_64.AppImage`, make it executable, and
run it:

```bash
chmod +x madlions-control-*-x86_64.AppImage
./madlions-control-*-x86_64.AppImage
```

The AppImage uses the host's Python and GTK installation, so install the
[host packages](#requirements) first. It provides the GUI only and does not
install `madlionsctl`, a desktop entry, or the udev rule. You can move the file
anywhere you like; replacing it with a newer download is the update process.

If FUSE is unavailable, extract and run it instead:

```bash
./madlions-control-*-x86_64.AppImage --appimage-extract-and-run
```

## From source

Clone the repository and try the demo mode first:

```bash
git clone https://github.com/NasirA1991/madlions-control.git
cd madlions-control
./madlions-control --demo
```

### System install

```bash
sudo ./install.sh
```

This installs to `/usr`:

- `/usr/lib/madlions-control`;
- `/usr/bin/madlions-control` and `/usr/bin/madlionsctl`;
- the desktop entry, icons, and metainfo;
- `/usr/lib/udev/rules.d/71-madlions.rules`.

The installer reloads udev when run as root. Replug the keyboard afterwards.

### Per-user install

```bash
./install.sh --user
```

This installs to `~/.local` and does **not** install the udev rule (that needs
root). It prints the exact commands for installing the rule system-wide. A
per-user install is convenient for development, but the app cannot open the
keyboard until the rule is present.

### Packaging

`install.sh` supports `PREFIX` and `DESTDIR`:

```bash
PREFIX=/usr DESTDIR="$pkgdir" ./install.sh
```

This is how the AUR packages stage the files. `uninstall.sh` removes the
installed program, desktop files, icons, metainfo, and udev rule. It deliberately
keeps your profiles in `~/.local/share/madlions-control/`.

## Permissions

The app opens the keyboard's vendor HID collection through `/dev/hidraw*`. On a
normal desktop, the included udev rule grants the active local user access:

```udev
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="373b", MODE="0660", TAG+="uaccess"
```

If you installed from the AUR or used a system source install, this rule is
already in place. For a Flatpak, AppImage, or `--user` install, add it manually:

```bash
printf '%s\n' 'SUBSYSTEM=="hidraw", ATTRS{idVendor}=="373b", MODE="0660", TAG+="uaccess"' \
  | sudo tee /usr/lib/udev/rules.d/71-madlions.rules
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=hidraw
```

Replug the keyboard after installing the rule. Then check access:

```bash
ls -l /dev/hidraw*
madlionsctl scan
```

The `madlionsctl` command is available with the AUR and source installs. For a
Flatpak or AppImage, use the app's **Permissions** dialog and the Troubleshooting
guide instead.

`TAG+="uaccess"` is handled by systemd-logind. On a system without logind, the
rule file contains a commented `GROUP="input"` alternative; use that only if you
understand which users are in the `input` group. Do not make the device
world-writable.

If you use the CLI as root, it can open the device without the rule, but running
a desktop app as root is not recommended. Fix the rule for your normal user
instead.

## Data locations

| Data | Path |
|---|---|
| Settings | `${XDG_CONFIG_HOME:-~/.config}/madlions-control/settings.json` |
| Profiles | `${XDG_DATA_HOME:-~/.local/share}/madlions-control/profiles/` |
| Automatic tuning snapshots and full backups | the `backups/` subdirectory of the profiles directory |

`MADLIONS_CONTROL_PROFILES` overrides the profiles directory, which is useful for
testing or for keeping separate profile sets. Flatpak stores the same files
inside its sandbox under `~/.var/app/io.github.madlionscontrol.MadlionsControl/`.

Profiles are plain JSON and can be copied between installs. Export and import
from the Profiles page; see [Using Madlions Control](USAGE.md#profiles-and-backups).

## Updating

- **AUR stable:** `paru -Syu madlions-control`
- **AUR git:** `paru -Syu madlions-control-git`
- **Flatpak:** `flatpak update io.github.madlionscontrol.MadlionsControl`
- **AppImage:** download the new file and replace the old one.
- **Source:** `git pull`, then rerun `./install.sh` (or `./install.sh --user`).

Profiles use a versioned JSON schema. The app validates profile files on import
and refuses incompatible or malformed data rather than partially applying it.

## Uninstalling

- **AUR:** `paru -Rns madlions-control` (or `madlions-control-git`)
- **Flatpak:** `flatpak uninstall io.github.madlionscontrol.MadlionsControl`
- **AppImage:** delete the AppImage file.
- **Source:** `sudo ./uninstall.sh` (add `PREFIX`/`DESTDIR` if you used them).

None of these removes your profiles automatically. Delete
`~/.local/share/madlions-control/` manually if you want a clean removal. For
Flatpak, also remove `~/.var/app/io.github.madlionscontrol.MadlionsControl/`.

## Next steps

- [Using Madlions Control](USAGE.md) — pages, tuning, profiles, and save rules.
- [CLI reference](CLI.md) — every `madlionsctl` command.
- [Troubleshooting](TROUBLESHOOTING.md) — device and permission problems.
