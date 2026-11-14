# Installation

Madlions Control is a Python and GTK4 application. There is no C extension to
build, but GTK, libadwaita and their Python bindings must be available. The AUR
packages install everything for you; the Flatpak and AppImage reduce the setup
work but do not remove the need for a host udev rule.

## Choose a method

| Method | Installs the CLI | Installs the udev rule | Best for |
|---|---|---|---|
| AUR `madlions-control` | Yes | Yes, `/usr/lib/udev/rules.d` | Arch Linux users who want a packaged release. |
| AUR `madlions-control-git` | Yes | Yes, `/usr/lib/udev/rules.d` | Arch Linux users who want `main`. |
| Flatpak | No | No; save the rule, install it manually | A sandboxed GUI with the GNOME runtime. |
| AppImage | No | No; save the rule or use **Fix permissions** | A portable GUI with no package manager. |
| Source system install | Yes | Yes, `/usr/lib/udev/rules.d` | Development, packaging, or a normal install. |
| Source `--user` install | Yes | No; run `sudo ./install.sh --udev-only` | A home-directory install without root. |

All methods use the same application data format, so profiles can be copied
between them. Configuration and profiles live in your home directory; see
[Data locations](#data-locations).

## Requirements

- Linux with `hidraw` support (the standard kernel HID driver).
- Python **3.10 or newer** for the AppImage and source installs.
- GTK **4.10 or newer** and libadwaita **1.5 or newer**.
- PyGObject, PangoCairo, and pycairo bindings.
- A desktop icon theme; `hicolor-icon-theme` provides the application icon.

`install.sh` imports the GUI stack before it copies anything and prints the
matching package command if a dependency is missing. Install the host packages
for your distribution:

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

**openSUSE**

```bash
sudo zypper install python3-gobject python3-cairo typelib-1_0-Gtk-4_0 typelib-1_0-Adw-1 hicolor-icon-theme
```

The openSUSE package names are unverified; adjust if `zypper` reports a missing
package. The AUR package pulls in the equivalent dependencies automatically. For
packaging, `--skip-deps` disables the installer's import check. A desktop session
on Wayland or X11 is supported; a headless machine can use the CLI, but the GUI
needs a display.

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

The package rule is installed automatically. Unplug and replug the keyboard once
after installation so the new rule applies. Packages never write
`/etc/udev/rules.d/71-madlions.rules`; that location is reserved for
`sudo ./install.sh --udev-only` and the in-app **Fix permissions** action.

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

The host still needs the udev rule so your user can open the device. On first
run, open **Permissions** and choose **Save rule file**; the dialog writes the
rule to `~/Downloads` and shows the host commands. Flatpak never runs host
commands through `flatpak-spawn`. See [Permissions](#permissions).

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
install `madlionsctl`, a desktop entry, or the udev rule. If the keyboard cannot
be opened, use **Permissions → Save rule file** and run the host commands. With
polkit available, **Fix permissions** can install the rule after one prompt. You
can move the file anywhere you like; replacing it with a newer download is the
update process.

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

Run `./install.sh --help` to see all modes. The installer checks the Python/GTK
imports before copying, reloads udev when run
as root, and asks you to replug the keyboard. A system install without `DESTDIR`
requires root; use `sudo ./install.sh` or `./install.sh --user`.

Before changing a system install, the script asks `pacman`, `dpkg`, or `rpm`
whether another package owns the application directory or launcher. If one
does, it refuses and names the package, because overwriting package-owned files
can leave the package database inconsistent. Remove the package with your
package manager, or pass `--force` if you deliberately want to take the files
over. The same guard protects a system uninstall.

### Per-user install

```bash
./install.sh --user
```

This installs to `~/.local` and does **not** install the udev rule (that needs
root). Run the one-time rule install from the same checkout:

```bash
sudo ./install.sh --udev-only
```

A per-user install is convenient for development, but the app cannot open the
keyboard until the rule is present.

### Packaging

`install.sh` supports `PREFIX` and `DESTDIR`:

```bash
PREFIX=/usr DESTDIR="$pkgdir" ./install.sh
```

`DESTDIR` implies `--skip-deps` and does not apply the rule to the running
system; it writes the rule into the staged `${DESTDIR}${PREFIX}/lib/udev/rules.d`
tree for packaging. This is how the AUR packages stage the files. `uninstall.sh`
removes the installed program, desktop files, icons, metainfo, the package rule,
and (for a system uninstall) the `/etc` admin rule. It deliberately keeps your
profiles in `~/.local/share/madlions-control/`.

## Permissions

The app opens the keyboard's vendor HID collection through `/dev/hidraw*`. The
rule grants the active local user access and lives in the repository as
`data/udev/71-madlions.rules`. The app reads that file directly; it does not
embed a copy.

If a supported keyboard is visible but cannot be opened, the app shows
**Permission denied** and opens the **Permissions** dialog once per session. The
dialog also has **Save rule file** (writes `~/Downloads/71-madlions.rules`),
**Copy commands**, **Rescan**, and, outside Flatpak with polkit available,
**Fix permissions**. If access worked before and stopped after switching user
or seat, unplug and replug the keyboard.

- **AUR or system source install:** already installed in
  `/usr/lib/udev/rules.d/71-madlions.rules`. Replug the keyboard.
- **Source `--user` install:** run `sudo ./install.sh --udev-only` once.
- **Flatpak or AppImage:** open **Permissions**, choose **Save rule file**, and
  run the commands shown on the host. The commands are also shown below.

Use **Save rule file**, then run on the host:

```bash
sudo install -Dm644 "$HOME/Downloads/71-madlions.rules" \
  /etc/udev/rules.d/71-madlions.rules
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=hidraw
```

Then unplug and replug the keyboard. Check access:

```bash
ls -l /dev/hidraw*
madlionsctl scan
```

The `madlionsctl` command is available with the AUR and source installs. For a
Flatpak or AppImage, use the app's **Permissions** dialog instead.

`TAG+="uaccess"` is handled by systemd-logind. On a system without logind, the
rule file contains a commented `GROUP="input"` alternative; use that only if you
understand which users are in the `input` group. Do not make the device
world-writable.

The vendor ID `373b` is shared with other devices, including ATK mice. The
dialog and discovery code require the MADLIONS 32-byte vendor collection before
showing a device, so an ATK mouse is not listed as a keyboard. Never remove
`/etc/udev/rules.d/71-atk-control.rules`; it belongs to the separate ATK app.

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
- **Source:** `sudo ./uninstall.sh` for a system install, or
  `./uninstall.sh --user` for a per-user install (add `PREFIX`/`DESTDIR` if you
  used them). A system uninstall removes both the `/usr/lib` package rule and
  the `/etc` admin rule; a user uninstall removes only its own tree and never
  touches `/etc`. Neither touches `71-atk-control.rules`. Run
  `sudo ./uninstall.sh --udev-only` to remove only the `/etc` admin rule.

None of these removes your profiles automatically. Delete
`~/.local/share/madlions-control/` manually if you want a clean removal. For
Flatpak, also remove `~/.var/app/io.github.madlionscontrol.MadlionsControl/`.

## Next steps

- [Using Madlions Control](USAGE.md) — pages, tuning, profiles, and save rules.
- [CLI reference](CLI.md) — every `madlionsctl` command.
- [Troubleshooting](TROUBLESHOOTING.md) — device and permission problems.
