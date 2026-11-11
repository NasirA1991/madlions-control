# Using Madlions Control

This guide walks through the application window and the rules that decide when a
change reaches the keyboard. For command-line usage, see the
[CLI reference](CLI.md).

## Starting the app

```bash
madlions-control
```

Open a specific page directly:

```bash
madlions-control --page perkey
```

The available pages are `overview`, `perkey`, `lighting`, `keymap`, `macros`,
`advanced`, `test`, and `profiles`. To explore without a keyboard:

```bash
madlions-control --demo
```

Demo mode uses simulated data and never opens a device. It is useful for trying
the interface or taking screenshots, but it cannot test real hardware.

## Window overview

The header shows the connected model, its USB ID, and a connection badge. The
main menu contains:

- **Fn shortcuts** — a generated cheatsheet for the layer Fn activates.
- **Refresh from keyboard** — re-read the current state.
- **Reset tuning…** — apply the verified baseline for the MAD68 HE RGB.
- **Device diagnostics** — a read-only report for bug reports.
- **Permissions** — the udev command and access checks.
- **Appearance** — follow the system theme or force light/dark.
- **About Madlions Control** — version and project links.

Use `Ctrl+1` … `Ctrl+8` to switch pages, `Ctrl+S` to save settings to the
keyboard, `Ctrl+R` to refresh, `Ctrl+?` for shortcuts, and `Ctrl+Q` to quit.
These shortcuts are active while the app window has focus.

## Saving rules

The app deliberately separates live edits from flash writes.

| What you change | Applied | Persisted |
|---|---|---|
| Actuation | Live on the keyboard | **Save to keyboard** |
| Rapid trigger | Live on the keyboard | **Save to keyboard** |
| Main lighting | Live on the keyboard | **Save lighting** |
| Side light (supported boards) | Live on the keyboard | No verified save command |
| Keymap | Written immediately | Onboard memory |
| Macros | Written when you press **Save macro** | Onboard memory |
| Advanced keys, hold/click, DKS | Written when you save the dialog | Onboard memory |
| Switches, dead band, game mode, bottom-out | Live on the keyboard | Not persisted in this build |
| Profiles and backups | Files on your computer | Until you delete them |

“Save to keyboard” is the header button. It commits actuation and rapid trigger,
then saves lighting. If the lighting save fails, the app reports a warning rather
than claiming complete success.

**Switches, dead band, game mode, and bottom-out optimisation are volatile.**
The firmware accepts them at runtime, but there is no verified flash command for
them in this app. If they matter to your setup, re-apply them after unplugging
the keyboard. Do not assume the header save button will preserve them.

Keymap, macro, and advanced-binding edits are different: those write to onboard
memory as soon as you confirm the edit. The related pages say so in their help
text. Profiles can restore those sections from a full backup.

## Per-key

The Per-key page edits the feel of individual switches.

1. Click a key to select it. Ctrl-click adds or removes keys; **Select all** and
   **Clear** operate on the whole board.
2. Choose **Actuation** or **Rapid trigger**.
3. Adjust the slider or pick a preset.
4. Press **Save to keyboard** when you want the tuning to survive a replug.

The heat map reflects the selected mode: actuation distance on the Actuation
tab, rapid-trigger sensitivity on the Rapid trigger tab. The scale runs from
0.05 mm to 3.40 mm.

### Actuation

Actuation is how far a key must travel before it registers. Shorter distances
feel faster but can cause accidental presses. Drag the slider or use the preset
row for common values:

- 0.10, 0.50, 1.00, 1.50, 2.00, or 3.00 mm.
- **Reset selection to 1.50 mm** returns the selected keys to the default.

The keyboard reports travel in 0.01 mm steps; the slider uses those steps.

### Rapid trigger

Rapid trigger resets a key as soon as it moves back up, rather than waiting for a
fixed release point.

- **Enable on selection** turns rapid trigger on for the selected keys.
- **Press sensitivity** is how far the key must move after a reset to trigger
  again.
- **Release sensitivity** is how far it must move back up to reset.

Lower sensitivity values make the key more responsive and more prone to noise.
Start around 0.10–0.20 mm and adjust from there.

Rapid trigger uses the same travel data as actuation. If a key feels
inconsistent, check both its actuation point and its press/release values.

### Selection behaviour

Small selections are written key by key. Larger selections use a bulk write,
which is faster but touches more of the keyboard's tuning buffer. Either way,
the change is volatile until you save.

## Lighting

The Lighting page controls the main RGB effect and, on supported boards, the
side light.

- Pick an effect from the firmware's effect list.
- Set **Brightness** from 0 to 210. The firmware silently drops values above
  210, so the app clamps the control.
- **Animation speed** is available for animated effects.
- Choose the main **Colour** with the colour picker.

### Per-key colours

Per-key colours are visible only with the **Custom** effect (effect 1). Select
**Use Custom effect** first, then click a key and choose its colour. Painting a
key writes its RGB value; it does not change actuation or the keymap.

Some effects ignore the main colour by design. If a colour change appears to do
nothing, switch to a colour-aware effect such as Solid colour or Breathing.

### Side light

On boards with an edge strip, the Side light section provides:

- **Mode** — Off or modes 1–5, as named by the firmware.
- **Multi-colour** — cycle colours instead of using one colour.
- **Brightness** and **Speed**, both 0–255.

Side-light changes are applied live. The main lighting has a verified save
command; the app has no verified side-light save command, so treat side-light
settings as volatile. The reference board has no side strip, so this path is
untested on hardware.

### Lighting persistence

**Save lighting** is separate from the tuning save. If you only change lighting,
you do not need to commit actuation or rapid trigger. If you change both, the
header **Save to keyboard** saves both in one action.

## Keymap

The Keymap page edits the layers reported by the board.

1. Select a layer.
2. Click a key.
3. Search the keycode picker or browse its categories.
4. Choose a keycode. The change is written to onboard memory immediately.

The picker includes basic keys, modifiers, media keys, layer actions, and other
firmware keycodes. **Transparent** passes the key through to the layer below;
**Clear** disables it.

Fn on these boards is usually `MO(1)`: holding Fn activates layer 1. The layer
buttons show how many layers the connected board actually reports. If Fn does
not behave as expected, inspect layer 1 rather than assuming the keymap is
broken.

### Fn shortcuts

The header's keyboard button opens a read-only cheatsheet. It reads the layer Fn
activates and groups the shortcuts into lighting, function keys, and other
bindings. The sheet includes an **Open Keymap** button so you can jump to the
layer it describes. Vendor-specific actions that cannot be named reliably are
left unlabelled rather than guessed.

## Macros

The Macros page edits the keyboard's shared macro buffer. The MAD68 HE RGB
provides sixteen slots; the actual slot count is read from the keyboard.

Each macro is a sequence of steps:

- **Tap key** — press and release.
- **Press key** / **Release key** — hold and release separately.
- **Delay** — 0–2000 ms.
- **Text** — typed literally in ASCII.

Click **Save macro** to encode the sequence and write the slot. Changes are
written to onboard memory immediately; there is no separate keyboard save.
Macros can contain at most what fits in the device's macro buffer, and the size
line shows the encoded byte count before you save.

When a macro contains an opcode this app does not recognise, the step is shown as
**Unsupported step (preserved)**. Editing and saving the macro keeps the raw
bytes intact so a round-trip through the editor does not destroy vendor data.

## Advanced

The Advanced page has three groups. Read the page's own notes carefully: the
save rules are not identical.

### Switches

- **N-key rollover** — report every key independently.
- **Lock the Windows key** — suppress the Windows/Super key.
- **Swap WASD with arrows** — useful in games that only accept arrows.
- **macOS layout** — swap the modifier arrangement.
- **Game mode** — the firmware's competitive preset.
- **Bottom-out optimisation** — treat a key that reaches the bottom as pressed.

These switches apply immediately. They are **volatile** in the current build;
the header save button does not persist them.

### Dead band

Top and bottom dead band range from 0.00 to 0.50 mm. They tell the firmware to
ignore movement at the very start or end of travel. Changes are debounced and
applied live. They are also volatile in the current build.

### Advanced keys and DKS

Advanced keys let the keyboard evaluate a behaviour itself:

- **Rapid snappy** — a fast re-trigger for a key.
- **SOCD** variants — last input wins, key 1 wins, key 2 wins, or neutral.
- **OKS** — release to activate.
- **Hold / click** — tap sends one key, holding sends another.
- **DKS** — up to four keystrokes selected by how far the key is pressed.

Bindings are written to the keyboard immediately when you save the dialog. Each
slot can be rebound. Hold/click is limited to the first eight slots; the dialog
refuses that behaviour for later slots instead of silently aliasing it.

DKS status fields are hexadecimal masks from `000` to `3ff`. The dialog validates
the value and shows an inline error instead of disabling the binding silently.

### Calibration

Calibration is deliberately **not** started from this app. An interrupted
calibration can leave a Hall-effect board feeling wrong. The page shows the
keyboard's calibration status and directs you to the official web driver if you
need to recalibrate. There is no factory reset because no verified reset command
exists.

## Test

The Test page shows the keyboard's own linearised travel data.

1. Press **Start**.
2. Click a key on the board to follow it, or watch the whole-board heat map.
3. Press the physical key and watch the gauge, threshold line, and five-second
   history graph.

The page displays the current travel in millimetres, pressed/released state, the
actuation and rapid-trigger thresholds, and the measured scan rate. It does not
change any setting.

The live view targets 60 Hz updates and 60 fps drawing for smooth motion. It
stops repainting while all keys are idle, so an idle Test page does not burn CPU.
The graph holds the last 300 samples, about five seconds at 60 Hz.

## Profiles and backups

The Profiles page has two related but different tools.

### Tuning profiles

A tuning profile stores the parts of the setup you are likely to switch between:

- Actuation and rapid trigger.
- Lighting and per-key colours.
- Switches.
- Dead band.
- Game mode and bottom-out optimisation.
- Side light.

Save one with **Save tuning profile**, give it a name, and apply it later. Applying
a tuning profile is volatile: use **Save to keyboard** if you want it to survive
a replug. Profiles are readable JSON and can be exported and imported.

Three presets are included:

| Preset | Actuation | Rapid trigger | Lighting |
|---|---|---|---|
| **Rapid fire** | 0.50 mm | 0.10 / 0.10 mm | Breathing, #ff4d6d, brightness 170 |
| **Balanced** | 1.50 mm | Off | Breathing, #ff4d6d, brightness 150 |
| **Typing** | 2.00 mm | Off | Solid colour, #ffbe46, brightness 120 |

Presets never write persistent onboard data.

### Full backups

A **full backup** adds the persistent sections:

- Keymap.
- Macros.
- Advanced keys.
- Hold/click bindings.
- DKS bindings.

It also includes the tuning sections and per-key colours. A full backup is the
right recovery point before experimenting with keymap or macro edits.

Restoring a full backup writes the persistent sections immediately after a
confirmation dialog. The app first takes a complete snapshot of the current
keyboard, named “Before restore: …”, so the restore itself can be undone.

### Automatic snapshots

The app saves one automatic tuning snapshot when it first connects during each
launch. Only the newest ten `backup-*.json` snapshots are kept. Full backups are
not pruned automatically; delete them from the Backups list when you no longer
need them.

Creating a snapshot or resetting tuning does not require a full backup. A snapshot
is automatically taken before a baseline reset and before a full-backup restore.

### Reset tuning

**Reset tuning…** applies the observed baseline for the MAD68 HE RGB and saves
a tuning snapshot first. It is available only on the **MAD68 HE RGB**, the only
board for which a verified baseline has been captured.

The reset covers actuation, rapid trigger, lighting, switches, dead band, game
mode, and bottom-out optimisation. It deliberately does **not** touch:

- the keymap;
- macros;
- advanced keys, hold/click, or DKS;
- per-key colours;
- side light;
- calibration.

The actuation, rapid-trigger, and lighting parts are volatile until you use
**Save to keyboard**. Switches, dead band, game mode, and bottom-out optimisation
remain volatile in this build even after that save. This is a scoped tuning
reset, not a factory reset.

### Import, export, and deletion

- **Export** writes a selected profile or backup as JSON.
- **Import** validates the file before applying it. Malformed, oversized, or
  incompatible profiles are rejected; the app does not partially apply them.
- Deleting a profile removes that exact file; deleting a backup removes only that
  backup.
- Saving a profile with an existing name asks for confirmation before replacing
  it.

Profiles live in the paths listed in
[Installation](INSTALLATION.md#data-locations). You can copy them between
machines, but a profile is only meaningful if its keymap size and board
assumptions match. The app warns when a full backup was made for a different
model.

## Diagnostics and reports

**Device diagnostics** shows a read-only report of the connection, firmware,
matrix, and feature state. The USB serial is redacted by default. Use the CLI's
`madlionsctl report --serial` only when you deliberately want it included.

The report is the best attachment for a device-support issue. Do not post raw
HID captures that contain personal data; see [SECURITY.md](../SECURITY.md).

## Where settings are stored

- Settings: `${XDG_CONFIG_HOME:-~/.config}/madlions-control/settings.json`
- Profiles: `${XDG_DATA_HOME:-~/.local/share}/madlions-control/profiles/`
- Backups: the `backups/` subdirectory

Flatpak keeps the same files inside its sandbox. See
[Installation](INSTALLATION.md#data-locations) for details.

## Related documentation

- [Installation](INSTALLATION.md)
- [CLI reference](CLI.md)
- [Troubleshooting](TROUBLESHOOTING.md)
