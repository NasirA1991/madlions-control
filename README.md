# Madlions Control

<p align="center">
  <img src="data/icons/madlions-control-256.png" width="96" alt="Madlions Control icon">
</p>

<p align="center">
  <b>Native Linux configuration for MADLIONS magnetic-switch keyboards.</b><br>
  Tune actuation and rapid trigger per key, remap the board, control its lighting,
  and watch live analogue travel — without a browser, an account, or a background
  service.
</p>

<p align="center">
  <a href="https://github.com/NasirA1991/madlions-control/actions/workflows/ci.yml"><img src="https://github.com/NasirA1991/madlions-control/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/NasirA1991/madlions-control/releases"><img src="https://img.shields.io/github/v/release/NasirA1991/madlions-control" alt="Release"></a>
  <a href="https://aur.archlinux.org/packages/madlions-control"><img src="https://img.shields.io/aur/version/madlions-control?label=AUR" alt="AUR"></a>
  <a href="https://aur.archlinux.org/packages/madlions-control-git"><img src="https://img.shields.io/aur/version/madlions-control-git?label=AUR%20git" alt="AUR git"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT"></a>
</p>

<p align="center">
  <a href="docs/screenshots/per-key-0.3.3.png"><img src="docs/screenshots/per-key-0.3.3.png" width="48%" alt="Per-key editor showing actuation values on a MAD68 HE keyboard"></a>
  <a href="docs/screenshots/lighting.png"><img src="docs/screenshots/lighting.png" width="48%" alt="Lighting page showing effects, brightness, speed, colour and a keyboard preview"></a>
</p>
<p align="center">
  <sub><b>Per-key tuning:</b> actuation and rapid trigger for each key. &nbsp;·&nbsp;
  <b>Lighting:</b> firmware effects, colours, speed and per-key paint.</sub>
</p>

<p align="center">
  <a href="docs/screenshots/test.png"><img src="docs/screenshots/test.png" width="48%" alt="Live test page showing a travel heat map, selected-key gauge and graph"></a>
  <a href="docs/screenshots/keymap.png"><img src="docs/screenshots/keymap.png" width="48%" alt="Keymap editor showing layers, a selected key and the keycode picker"></a>
</p>
<p align="center">
  <sub><b>Live test:</b> see travel as you type. &nbsp;·&nbsp;
  <b>Keymap:</b> edit the board's onboard layers.</sub>
</p>

<p align="center"><sub>Screenshots use demo mode; no physical keyboard is opened.</sub></p>

**On this page:** [What it is](#what-it-is) · [Features](#features) ·
[Supported keyboards](#supported-keyboards) · [Install](#install) ·
[Saving changes](#saving-changes) · [Troubleshooting](#troubleshooting) ·
[Documentation](#documentation)

## What it is

Madlions Control is a GTK4 / libadwaita application that configures supported
MADLIONS keyboards directly over their HID interface. The keyboard continues to
work as a normal USB keyboard without the app; the app is only needed when you
want to change how it behaves.

It is built around the feature that makes these boards interesting: adjusting
the feel of every individual key. The reference board is the **MAD68 HE RGB**
(`373B:1058`). The same controller family is used by several 60% and 65% models;
see [Supported keyboards](#supported-keyboards).

## Features

### Hall-effect tuning

- Set actuation from **0.05 mm to 3.40 mm** in 0.01 mm steps.
- Enable rapid trigger per key, with independent **press** and **release**
  sensitivity.
- Select one key, Ctrl-click several keys, or edit the whole board.
- Read the colour heat map at a glance, use a quick preset, or reset the
  selection to 1.50 mm.
- Changes are applied live; **Save to keyboard** commits actuation and rapid
  trigger to flash.

### Live analogue testing

- Per-key travel read from the keyboard's sensor stream.
- Full-board heat map, selected-key gauge, threshold line, and a rolling
  five-second graph.
- Useful for checking a threshold, spotting a noisy switch, or simply seeing
  how your typing is registered.

### Lighting and RGB

- Use the firmware's effects, including breathing, ribbons, rotating belts,
  spectrum, digital rain, and fingertip rainbow.
- Adjust brightness, speed, and colour.
- Paint individual keys with the **Custom** effect.
- Configure the side light on models that expose one.

### Keymaps, macros, and advanced bindings

- Edit the board's onboard keymap layers with a searchable keycode picker.
- Build macros from taps, presses, releases, delays, and typed text.
- Configure rapid snappy, SOCD (simultaneous opposite cardinal directions),
  OKS (release to activate), hold/click, and DKS (dynamic keystroke) bindings.
- Adjust NKRO, Windows-key lock, WASD/arrow swap, macOS layout, game mode,
  bottom-out optimisation, and dead band.

### Profiles, backups, and tools

- Save local tuning profiles for different games or typing setups.
- Create a full backup that also captures the keymap, macros, advanced keys,
  hold/click and DKS bindings, and per-key colours.
- Apply the ready-made **Rapid fire**, **Balanced**, and **Typing** presets.
- Reset tuning to the observed **MAD68 HE RGB** baseline without touching
  persistent data.
- Import and export profiles without sending them anywhere.
- Open an **Fn shortcut cheatsheet** generated from the layer Fn activates.
- Use the `madlionsctl` command line for scripts, keybinds, and status bars.
- Explore the complete UI without hardware with `--demo`.

## Supported keyboards

The **MAD68 HE RGB** is the reference board used for hardware testing. The
**MAD60 HE** has write support enabled from community hardware testing. Other
listed boards are recognised but remain read-only until a device report confirms
their firmware and layout.

The two IDs with write support enabled by default are shown in full. Group rows
omit the common `373B` vendor prefix for width; every listed ID is a `373B`
product.

| Model / family | Product ID(s) | Recognition | Write support | Verification basis |
|---|---|---|---|---|
| **MAD68 HE RGB** | `373B:1058` | **Hardware-verified** | **Enabled** | Reference board, protocol 9; the only tuning baseline |
| **MAD60 HE** | `373B:1053` | **Community-tested** | **Enabled** | Community hardware testing; no tuning baseline |
| MAD68 / FIRE68 / Z68 / MAG68 / MAD Light 68 family (65%) | `1057` `1059` `105A` `10A3` `10A4` `10A7` `10A9` `10AA` `10AB` `10D6` `1123` `1136` `1139` `1144` | Recognised | Read-only | No verified write reports |
| MAD60 / MAD63 / Z60 / MAD Light 60 family (60%) | `1054` `1055` `1056` `105D` `10AD` `10F6` `110B` `1120` `112A` | Recognised | Read-only | No verified write reports |
| MAD Smart | `107D` | Recognised | Read-only | No verified write reports |
| Other MADLIONS board with the same vendor collection | — | Generic fallback | Read-only | Unknown product ID and layout |

**Recognition is not a write endorsement.** "Hardware-verified" means the
reference write path was exercised on that board; "community-tested" means write
support is enabled from community reports. Neither promises every control on
every unit. Write-enabled boards still need firmware protocol 9; a board
reporting another protocol stays read-only even if its model is listed. The GUI
keeps unverified models read-only. CLI users can explicitly attempt writes with
`--allow-unverified`, but that does not make the model verified and cannot
bypass the protocol check.

Only the **MAD68 HE RGB** has a captured tuning baseline, so **Reset tuning** is
available only on that board. Reset is scoped: it does not touch the keymap,
macros, advanced bindings, hold/click, DKS, per-key colours, side light, or
calibration.

If a board exposes the same 32-byte vendor collection but has an unknown product
ID, the GUI detects it with a generic 5 × 15 layout and opens it read-only. A
[device report](https://github.com/NasirA1991/madlions-control/issues/new?template=device-report.yml)
is the fastest way to add proper support.

## Install

Every build needs Linux with `hidraw`. Source and AppImage installs also need
Python 3.10+, GTK 4.10+, and libadwaita 1.5+; the Flatpak uses the GNOME runtime.
Prebuilt Flatpak and AppImage files are on the
[releases page](https://github.com/NasirA1991/madlions-control/releases).

| Method | CLI | udev rule | Libraries |
|---|---|---|---|
| AUR stable or `-git` | Yes | Installed by the package | Distro Python/GTK packages |
| Flatpak | No | Install manually | GNOME runtime (downloaded) |
| AppImage | No | Install manually | Host Python/GTK stack |
| Source, `sudo ./install.sh` | Yes | Installed by the script | Host Python/GTK packages |
| Source, `./install.sh --user` | Yes | Install manually | Host Python/GTK packages |

"Install manually" means adding the host udev rule described in
[Installation](docs/INSTALLATION.md#permissions). AUR and system source installs
add it for you.

### Arch Linux, CachyOS, EndeavourOS

```bash
paru -S madlions-control       # latest tagged release
paru -S madlions-control-git   # latest main
```

Use `yay` in place of `paru` if that is your AUR helper. The packages install
the app, CLI, desktop entry, icons, AppStream metadata, and the udev rule.

### Flatpak

```bash
flatpak install --user ./madlions-control-*-x86_64.flatpak
flatpak run io.github.madlionscontrol.MadlionsControl
```

The Flatpak uses the GNOME runtime and requests `--device=all`, because Flatpak
cannot currently restrict access to a single `/dev/hidraw` node.

### AppImage

```bash
chmod +x madlions-control-*-x86_64.AppImage
./madlions-control-*-x86_64.AppImage
```

The AppImage uses the host's Python and GTK stack.

### From source

```bash
git clone https://github.com/NasirA1991/madlions-control.git
cd madlions-control
sudo ./install.sh              # /usr; installs the udev rule and desktop entry
# or: ./install.sh --user      # ~/.local; no root, no udev rule
```

See [Installation](docs/INSTALLATION.md) for dependency lists, permissions,
update instructions, and uninstall steps. `madlionsctl` is included in the AUR
and source installs; the Flatpak and AppImage provide the GUI only.

### Try without hardware

The demo is available in every build and from a source checkout:

```bash
madlions-control --demo                         # AUR or source install
flatpak run io.github.madlionscontrol.MadlionsControl --demo   # Flatpak
./madlions-control-*-x86_64.AppImage --demo    # AppImage
./madlions-control --demo                      # source checkout
```

Demo mode uses simulated keyboard data and never opens or modifies a physical
HID device. It is the quickest way to explore the interface before installing.
Source-checkout dependencies are listed under
[requirements](docs/INSTALLATION.md#requirements).

## Using it

The main window has eight pages:

| Page | What it is for |
|---|---|
| **Overview** | Keyboard state, tuning summary, and quick actions. |
| **Per-key** | Actuation and rapid-trigger editing on the board. |
| **Lighting** | Effects, brightness, speed, colours, per-key paint, and side light where supported. |
| **Keymap** | The board's layers and the searchable keycode picker. |
| **Macros** | The board's macro slots and the sequence editor. |
| **Advanced** | Switches, dead band, game mode, and smart-key bindings. |
| **Test** | Live travel values and the analogue graph. |
| **Profiles** | Tuning profiles, presets, backups, import/export, and reset. |

Use the keyboard icon in the header for **Fn shortcuts**, or open the main menu
for refresh, reset, diagnostics, permissions, appearance, and About. See
[Using Madlions Control](docs/USAGE.md) for the full walkthrough.

### Saving changes

The app separates live edits, onboard writes, and locally stored settings.

| Setting | Applied | Persisted |
|---|---|---|
| Actuation | Live on the keyboard | **Save to keyboard** (flash) |
| Rapid trigger | Live on the keyboard | **Save to keyboard** (flash) |
| Main lighting | Live on the keyboard | **Save lighting** (flash) |
| Side light | Live on the keyboard | No verified save command |
| Keymap | Written when you confirm a key | Onboard memory |
| Macros | Written on **Save macro** | Onboard memory |
| Advanced keys, hold/click, DKS | Written when you save the dialog | Onboard memory |
| Switches, dead band, game mode, bottom-out | Live on the keyboard | Not persisted in this build |
| Profiles and backups | Plain JSON on your computer | Until you delete them |

**Save to keyboard** is not a global "write everything" button. It commits
actuation and rapid trigger, then saves main lighting. It does not persist
keymap, macros, advanced bindings, switches, dead band, game mode, bottom-out,
side light, or profiles. If the lighting save fails, the app reports a warning
instead of claiming complete success.

Keymap, macro, and advanced-binding edits are written to onboard memory when
confirmed. Switches, dead band, game mode, bottom-out, and side light must be
reapplied after reconnecting unless a future firmware command makes them
persistent.

Profiles are plain JSON files on your computer. Automatic tuning snapshots keep
the last ten; full backups include persistent sections and are kept until you
delete them.

## Documentation

| Document | Contents |
|---|---|
| [Installation](docs/INSTALLATION.md) | Supported methods, dependencies, udev permissions, updates, uninstall. |
| [Using Madlions Control](docs/USAGE.md) | Every page, profiles, backups, and saving rules. |
| [CLI reference](docs/CLI.md) | `madlionsctl` commands, options, and examples. |
| [Troubleshooting](docs/TROUBLESHOOTING.md) | Common device, permission, Flatpak, and desktop issues. |
| [Development](docs/DEVELOPMENT.md) | Architecture, tests, screenshots, packaging, and releases. |
| [Protocol notes](docs/PROTOCOL.md) | The verified vendor HID command set. |
| [Contributing](CONTRIBUTING.md) | Device reports, code contributions, and test expectations. |
| [Changelog](CHANGELOG.md) | Release history. |
| [Security policy](SECURITY.md) | Private vulnerability reporting. |

## Limitations and safety

- **Linux only.** The app requires a kernel with `hidraw` support; the Flatpak
  and AppImage builds do not change that.
- **Compatibility is hardware-specific.** The MAD68 HE RGB is the reference;
  the MAD60 HE has community write testing. Recognition alone does not enable
  writes, and reset is available only on the reference board.
- **No firmware update, DFU, or Hall-sensor calibration.** A bad calibration can
  make a magnetic board feel wrong, so those operations are left to the official
  tool. There is also no factory reset because no verified reset command exists.
- **No onboard profile slots or report-rate control.** Profiles live on the
  computer. The current tuning can be saved to the keyboard, but the app does not
  manage the keyboard's own profile slots.
- **No cloud features, accounts, or telemetry.** Device access is local, and the
  app does not make network requests.
- **Flatpak uses `--device=all`.** Flatpak cannot yet restrict access to one
  `/dev/hidraw` node. The app only opens the vendor HID collection, but this is a
  real sandbox trade-off.
- **Reset tuning is scoped, not a factory reset.** It restores the observed
  MAD68 HE RGB baseline and leaves persistent keymap, macro, and advanced data
  alone.
- **Back up before experimenting.** Profiles and full backups are your recovery
  path; keep a copy before changing persistent bindings.

Madlions Control is an independent community project. It is not affiliated with
MADLIONS, FGG, or Shenzhen Yizhita.

## Troubleshooting

- **Keyboard not found:** run `madlionsctl scan` (AUR/source) or open the app's
  Permissions dialog. Use a direct USB port instead of a hub or KVM, and unplug
  and replug the keyboard.
- **Permission denied / read-only:** install the udev rule and replug. The rule
  is in [Installation](docs/INSTALLATION.md#permissions).
- **Board shown as read-only:** that model has not been verified yet. Open a
  device report if you want it supported.
- **Changes disappear after unplugging:** use **Save to keyboard** for actuation
  and rapid trigger. Advanced switches, dead band, game mode, bottom-out, and
  side light are volatile in the current build.
- **Multiple keyboards connected:** the GUI warns and uses the first detected
  board; the CLI can select one with `--device`.

See [Troubleshooting](docs/TROUBLESHOOTING.md) for the full list, including
Flatpak device access, lighting colour differences, and the KDE window-resize
workaround.

## Performance

Measured in demo mode under Xvfb at 1180×780, with software rendering. Treat
these as indicative figures, not a benchmark of every desktop.

- Window ready in about **0.4 s**.
- **0–0.2% CPU** idle; about **0.5–1%** with the Test page open but no key
  moving.
- The Test page redraws at **60 fps** and uses roughly **50% of one core** while
  the heat map is actively moving. That is the deliberate smoothness trade-off;
  repainting stops while every key is idle.
- About **150 MB PSS** (proportional set size) idle, or **170 MB** with the Test
  page open (GTK4 and Python shared libraries included).
- The AppImage download is about **1.1 MB**; the Flatpak application payload is
  about **0.2 MB**. These are not total installation sizes: the AppImage uses
  the host's GTK/Python stack, and Flatpak downloads the GNOME runtime separately.

Memory is the one area where this is a normal GTK/Python application rather than
a tiny native utility; CPU and disk use are small, and the app is only resident
while open.

## Contributing and device reports

Device reports are the most useful contribution. From an AUR or source install,
run `madlionsctl report`, review the read-only JSON, and open a
[device report](https://github.com/NasirA1991/madlions-control/issues/new?template=device-report.yml).
In GUI-only builds, use **Device diagnostics → Copy JSON** instead. Reports
redact the USB serial by default; pass `--serial` only if you deliberately want
to include it.

Code contributions should keep the write gate, volatile-first tuning, and
explicit persistence rules intact. See [CONTRIBUTING.md](CONTRIBUTING.md) and
[Development](docs/DEVELOPMENT.md).

## Security

Please report vulnerabilities privately; see [SECURITY.md](SECURITY.md).

## License

MIT. See [LICENSE](LICENSE).
