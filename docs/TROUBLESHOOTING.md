# Troubleshooting

Start with the app's **Device diagnostics** and **Permissions** dialogs, or run:

```bash
madlionsctl scan
madlionsctl status
```

`madlionsctl` is included in the AUR and source installs. Flatpak and AppImage
users can use the GUI dialogs or the commands in this guide.

## The keyboard is not detected

1. Check that the keyboard is connected with a data-capable USB cable, not a
   charge-only cable.
2. Try a direct USB port. Hubs, KVMs, and some docking stations do not pass the
   vendor HID collection through.
3. Check that Linux sees the device:

   ```bash
   lsusb | grep -i 373b
   ls -l /dev/hidraw*
   ```

   A supported board normally appears as `373b:1058` (MAD68 HE RGB) or another
   373B product ID.
4. Run `madlionsctl scan` (AUR/source) to see whether the vendor collection is
   present and supported.
5. Unplug and replug the keyboard, then refresh the app.

If the keyboard works as a normal keyboard but the app cannot see it, the
vendor collection may be missing from the current connection. Try another
cable/port before opening a report.

## Permission denied or read-only

The app opens `/dev/hidraw*` directly. Your user needs access through the udev
rule:

```udev
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="373b", MODE="0660", TAG+="uaccess"
```

Install it if it is missing:

```bash
printf '%s\n' 'SUBSYSTEM=="hidraw", ATTRS{idVendor}=="373b", MODE="0660", TAG+="uaccess"' \
  | sudo tee /usr/lib/udev/rules.d/71-madlions.rules
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=hidraw
```

Then unplug and replug the keyboard. Check the ACL:

```bash
getfacl /dev/hidrawX
```

You should see your user with read/write access. `TAG+="uaccess"` is applied by
systemd-logind to the active local session. If you are on a system without
logind, the packaged rule includes a commented `GROUP="input"` alternative; use
it only if you understand the security implications. Do not `chmod 666` the
device.

A keyboard can also be read-only because the model is unverified. `status` says
why:

```bash
madlionsctl status
```

Open a [device report](https://github.com/NasirA1991/madlions-control/issues/new?template=device-report.yml)
rather than forcing writes. `--allow-unverified` exists for development but can
write the wrong layout to an unknown board.

## “Already in use by another process”

Only one process can hold the device at a time. Close the other GUI or CLI
session, then retry:

```bash
madlionsctl status
```

The error is intentional; it prevents two writers from interleaving reports and
corrupting replies. Do not run the GUI and a CLI command against the same
keyboard simultaneously.

## The keyboard disconnects while idle

The app checks the device node every two seconds while connected. If the board
is unplugged, the session switches to disconnected and stops pretending the old
state is live. Replug it, then use **Refresh from keyboard** or reopen the app.

If it disconnects repeatedly:

- try a different cable and port;
- avoid unpowered hubs;
- check `dmesg` for USB reset or power errors;
- test the board on another computer to separate a cable/hub problem from a
  firmware problem.

## Flatpak cannot see the keyboard

The Flatpak manifest requests `--device=all`, but the host udev rule still
matters. Verify both:

```bash
flatpak info --show-permissions io.github.madlionscontrol.MadlionsControl
ls -l /dev/hidraw*
```

The permissions should include device access. Install the host rule from the
[Permissions](#permission-denied-or-read-only) section, replug, and restart the
app:

```bash
flatpak run io.github.madlionscontrol.MadlionsControl
```

If you previously denied a permission, inspect or reset the override:

```bash
flatpak override --user --show io.github.madlionscontrol.MadlionsControl
flatpak override --user --device=all io.github.madlionscontrol.MadlionsControl
```

Remember that Flatpak provides the GUI only; `madlionsctl` is not available
inside the sandbox.

## AppImage does not start

Make the file executable:

```bash
chmod +x madlions-control-*-x86_64.AppImage
```

If FUSE is unavailable, run it extracted:

```bash
./madlions-control-*-x86_64.AppImage --appimage-extract-and-run
```

The AppImage uses the host's Python and GTK stack. Install the packages from
[Installation](INSTALLATION.md#requirements) if it exits with an import error.
Run it from a terminal once to see the actual error message.

## Lighting changes are ignored

The firmware has a few quirks:

- **The effect is Off.** Colour and brightness writes are ignored while the
  effect is Off. Select a visible effect first. The GUI and CLI stage a visible
  effect automatically, but a manually built sequence must do the same.
- **The effect ignores colour.** Some firmware effects are rainbow or
  multi-colour by design. Try Solid colour, Breathing, or Focus.
- **Per-key colours need Custom.** Per-key painting is visible only with effect
  **1 (Custom)**. Click **Use Custom effect** first.
- **Brightness is capped.** The firmware ceiling is 210; higher values are
  dropped. The app clamps the control.
- **The change was not saved.** Main lighting is volatile until **Save lighting**
  or the header **Save to keyboard**.

The side light has its own brightness range (0–255), separate from the main
lighting ceiling. It has no verified save command; treat side-light changes as
volatile.

## Changes disappear after unplugging

This is usually expected. Check the save rules:

| Change | Persists without an explicit save? |
|---|---|
| Actuation / rapid trigger | No — use **Save to keyboard**. |
| Main lighting | No — use **Save lighting**. |
| Side light (supported boards) | No — no verified save command; treat as volatile. |
| Keymap | Yes, written immediately. |
| Macros | Yes, when you press **Save macro**. |
| Advanced keys / hold-click / DKS | Yes, written when you save the dialog. |
| Switches / dead band / game mode / bottom-out | No — volatile in this build. |

Switches, dead band, game mode, and bottom-out optimisation have no flash-save
path in the current app. Re-apply them after a power cycle if you need them.
Do not assume the header save button covers them.

## Reset tuning is unavailable

Only the **MAD68 HE RGB** has a verified tuning baseline. The reset button is
disabled on other boards, including models that are otherwise writable. There is
no factory reset command because no verified reset sequence exists.

## A profile will not apply

Common causes:

- **The backup was made for another board.** Full backups include a keymap size;
  the app stops before writing if it does not match.
- **The profile is malformed.** Import validates the file and rejects bad data
  instead of applying part of it.
- **You selected a full backup without persistent restore.** The GUI asks for
  confirmation before restoring keymap/macros; the CLI requires `--persistent`.
- **The name is ambiguous.** Two profiles or backups can share a name. The CLI
  prints the candidates; rename or remove one, or select the exact file from the
  GUI.

A restore takes a complete “Before restore: …” snapshot first. If something goes
wrong, restore that snapshot; do not start deleting profile files.

## Macros behave unexpectedly

- The macro buffer is finite. The editor shows the encoded byte count; a macro
  that does not fit is rejected rather than truncated.
- Text steps are typed literally in ASCII.
- A tap is press + release. Use **Press** and **Release** for holds.
- Unknown vendor opcodes are preserved as **Unsupported step**; editing the macro
  round-trips the raw bytes instead of dropping them.
- Macro slots are written to the keyboard when you press **Save macro**. There is
  no separate keyboard save button.

## Fn does not do what I expect

Fn is usually `MO(1)`, which activates layer 1 while held. Check layer 1 in the
Keymap page, and open **Fn shortcuts** to see what the app currently reads from
that layer. If the board reports a different layer count, trust the live map
rather than the manual.

## The Test page shows nothing

- Press **Start**.
- Click a key on the board; the gauge follows the selected key.
- Check that the app can open the device and the badge says **Connected**.
- Make sure the keyboard is connected and not being held by another process.

The graph needs time to fill. The heat map should react immediately when a key
moves. If the scan counter stays idle, the keyboard is not sending travel data;
reconnect it and check `dmesg`.

## High CPU or sluggish animation

The Test page intentionally draws at 60 fps while keys are moving. That can use
about half of one CPU core; it is the smoothness trade-off. When every key is
idle, repainting stops.

If idle CPU is high:

- close the Test page;
- check that no key is stuck or noisy (the heat map will show it);
- compare with `--demo` to separate a device problem from a rendering problem.

The 60 fps target is deliberate. Close the Test page when you do not need live
data, or fix the noisy key or USB connection rather than hiding it.

## Window does not resize

The app sets a minimum window size, but some KDE/KWin scripts can override window
geometry. If resizing snaps back or the window is stuck, check:

- `kzonesEnabled` (KZones);
- `rememberwindowpositionsEnabled` (Remember Window Positions);
- `sticky-window-snappingEnabled` (Sticky Window Snapping).

Disable or exclude Madlions Control in those scripts, then restart the app. This
is a compositor interaction, not a device write.

## Reporting a device problem

Include:

1. the output of `madlionsctl report` (or the diagnostics dialog);
2. `lsusb | grep -i 373b`;
3. your distribution, desktop, and whether you use Wayland or X11;
4. the exact steps that failed and any error text.

The report redacts the USB serial by default. Review it before posting. Do not
post raw captures that may contain personal data; see [SECURITY.md](../SECURITY.md).

## Still stuck?

- [Installation](INSTALLATION.md)
- [Using Madlions Control](USAGE.md)
- [CLI reference](CLI.md)
- [Open an issue](https://github.com/NasirA1991/madlions-control/issues)
