# CLI reference

`madlionsctl` provides direct access to the same device features as the GUI, with
output that is suitable for scripts and status bars.

The CLI is installed by the AUR and source installs. The Flatpak and AppImage
provide the GUI only; there is no supported `flatpak run ... madlionsctl` or
AppImage CLI mode.

For a source checkout, the equivalent of the installed command is:

```bash
python3 -m madlions_control.cli --help
```

The examples below use `madlionsctl`.

## Quick start

```bash
madlionsctl scan
madlionsctl status
madlionsctl actuation 1.20 --key 2,1 --save
madlionsctl rt on --press 0.10 --release 0.10 --all --save
madlionsctl light --effect 2 --color '#ff4d6d' --brightness 150 --save
```

To explore without hardware, add `--demo` to any command:

```bash
madlionsctl --demo status
madlionsctl --demo actuation 1.00 --all
```

Demo mode creates a simulated keyboard. It never opens a real device. Profile
commands are not sandboxed by demo mode: `profile save` and `profile list` still
use your normal profiles directory.

## Device selection

By default the CLI uses the first supported keyboard it finds. If several
keyboards are connected, select one explicitly:

```bash
madlionsctl --device /dev/hidraw10 status
madlionsctl --device hidraw10 status
madlionsctl --device 373B:1058 status
```

`--device` accepts the full path, the hidraw name, or the USB ID. Matching is
exact; use `madlionsctl scan` to see the available values.

The device is opened exclusively. If the GUI or another CLI command is using the
same keyboard, the command fails with:

```text
error: /dev/hidraw10 is already in use by another process; close the other Madlions Control or madlionsctl session and retry
```

Close the other session and retry. Do not run two writers against one keyboard.

## Global options

| Option | Meaning |
|---|---|
| `--device DEVICE` | Select a keyboard by path, hidraw name, or USB ID. |
| `--demo` | Use a simulated keyboard. |
| `--allow-unverified` | Permit writes on an unverified board. This bypasses the default read-only protection and is intentionally dangerous. |
| `--version` | Print the CLI version. |

`--help` works before or after a subcommand:

```bash
madlionsctl --help
madlionsctl light --help
```

## Saving and volatile changes

The CLI follows the GUI's persistence rules:

| Command | Default | With `--save` |
|---|---|---|
| `actuation` | Volatile | `commit()` persists actuation and rapid trigger. |
| `rt` | Volatile | `commit()` persists actuation and rapid trigger. |
| `light` | Volatile | `save_lighting()` persists lighting. |
| `deadband` | Volatile | No save option; accepted at runtime only. |
| `features` | Volatile | No save option; accepted at runtime only. |
| `reset-tuning` | Volatile | `--save` calls `save_all()`; lighting failure is reported. |
| `profile apply` | Volatile tuning | `--save` persists tuning; `--persistent` restores full sections. |

When a command says “not saved”, the keyboard keeps the value until it loses
power or the firmware resets it. Use `--save` when the change should survive a
replug.

## `scan`

List MADLIONS vendor HID collections. The output includes the path, USB ID,
product title, and whether the board is supported or why it is read-only.

```bash
madlionsctl scan
```

Exit status is 0 when at least one collection is found, 1 otherwise. Unsupported
boards still appear in the list so a report can identify them.

## `status`

Show the connected keyboard and a summary of its current state.

```bash
madlionsctl status
madlionsctl status --json
```

The JSON form includes board identity, protocol, writable state, layer count,
actuation range, rapid-trigger count, lighting, switches, dead band, game mode,
bottom-out state, and side-light data. It is suitable for status bars and
monitoring scripts. The serial is not included.

## `actuation`

Set the actuation point in millimetres.

```bash
madlionsctl actuation MM (--key ROW,COL ... | --all) [--save]
```

- `MM` must be between 0.05 and 3.40. Values are clamped to 0.01 mm steps by the
  device.
- `--key ROW,COL` is zero-based matrix coordinates. Repeat it to select several
  keys.
- `--all` selects every physical key on the board.
- `--save` commits the result to flash.

Examples:

```bash
madlionsctl actuation 1.20 --key 2,1
madlionsctl actuation 1.50 --all
madlionsctl actuation 0.75 --key 3,2 --key 3,3 --save
```

The command reads the values back and returns exit status 2 if the keyboard
reports different values for any selected key.

## `rt`

Turn rapid trigger on or off and set its press/release sensitivity.

```bash
madlionsctl rt on|off [--press MM] [--release MM] (--key ROW,COL ... | --all) [--save]
```

- `--press` and `--release` default to **0.50 mm** when omitted.
- Both ranges are 0.01–3.40 mm.
- `--all` applies to every physical key.
- `--save` commits actuation and rapid trigger.

Examples:

```bash
madlionsctl rt on --press 0.10 --release 0.10 --key 2,1
madlionsctl rt on --press 0.15 --release 0.20 --all --save
madlionsctl rt off --all --save
```

Turning rapid trigger off clears the enabled flag; sensitivity values are ignored
while it is off. The command verifies the enabled flag and both distances for
every selected key.

## `light`

Change the firmware lighting effect, brightness, speed, or colour.

```bash
madlionsctl light [--effect N] [--brightness 0-210] [--speed 1-255]
                  [--color '#RRGGBB'] [--save]
```

At least one of `--effect`, `--brightness`, `--speed`, or `--color` is required.
Omitted values are left unchanged.

- **Brightness:** 0–210. Values above 210 are rejected by the argument parser;
  the firmware silently ignores them.
- **Speed:** 1–255. This is meaningful only for animated effects.
- **Colour:** `#RRGGBB` or `#RGB`, quoted so the shell does not interpret `#`.
- **Effect:** one of the numbers in the table below.
- `--save` calls `save_lighting()` to persist the result.

Examples:

```bash
madlionsctl light --effect 2 --brightness 150
madlionsctl light --color '#ff4d6d' --speed 40
madlionsctl light --effect 1 --save          # Custom; use per-key colours in the GUI
```

The command reads the effect and brightness back and returns exit status 2 if they
do not match. Some effects ignore colour by design.

### Effect numbers

| No. | Effect | No. | Effect |
|---:|---|---:|---|
| 0 | Off | 1 | Custom |
| 2 | Solid colour | 3 | Focus |
| 4 | Rainbow — vertical | 5 | Rainbow — horizontal |
| 6 | Breathing | 7 | Ribbon 1 |
| 8 | Ribbon 2 | 9 | Rotating belt 1 |
| 11 | Rotating belt 2 | 13 | Spectrum cycle |
| 19 | Colour swirl 1 | 23 | Colour swirl 2 |
| 25 | Christmas | 26 | Spectrum breathing |
| 28 | Spectrum floating | 30 | Digital rain |
| 31 | Lighting up | 36 | Crucifix |
| 39 | Fingertip rainbow |  |  |

Effect **1 (Custom)** is the only effect that shows per-key colours. Use the GUI
to paint individual keys; the CLI changes the active effect and its main colour.

If the current effect is Off, the firmware ignores colour and brightness writes.
The app and `madlionsctl light` stage a visible effect automatically. If you
build raw HID packets yourself, select a visible effect before writing colour or
brightness.

## `deadband`

Set the top and/or bottom dead band.

```bash
madlionsctl deadband [--top MM] [--bottom MM]
```

- Range: 0.00–0.50 mm for each side.
- At least one option is required.
- The change is volatile; there is no save option in this build.
- The command reads both values back and returns exit status 2 on a mismatch.

```bash
madlionsctl deadband --top 0.20 --bottom 0.20
```

## `features`

Change firmware switches, game mode, or bottom-out optimisation.

```bash
madlionsctl features [--nkro | --six-key]
                     [--win-lock | --no-win-lock]
                     [--wasd | --no-wasd]
                     [--mac | --no-mac]
                     [--game N] [--bottom N]
```

- `--nkro` enables N-key rollover; `--six-key` selects the 6-key boot report.
- `--win-lock` suppresses the Windows/Super key.
- `--wasd` swaps WASD with the arrow keys.
- `--mac` selects the macOS modifier arrangement.
- `--game N` and `--bottom N` accept 0–255. `1` is normally on and `0` normally
  off, but the firmware defines the meaning.
- At least one feature is required.
- The change is volatile; there is no save option in this build.

Examples:

```bash
madlionsctl features --nkro --no-win-lock
madlionsctl features --game 1 --bottom 1
```

The command verifies the switch state and any game/bottom values it changed.

## `reset-tuning`

Apply the observed baseline for the MAD68 HE RGB.

```bash
madlionsctl reset-tuning [--save]
```

This is available only for boards with a captured baseline; currently that is the
**MAD68 HE RGB**. The command:

1. captures a tuning snapshot;
2. applies actuation, rapid trigger, lighting, switches, dead band, game mode,
   and bottom-out optimisation;
3. leaves keymap, macros, advanced keys, hold/click, DKS, per-key colours, side
   light, and calibration untouched;
4. with `--save`, calls `save_all()` to persist actuation, rapid trigger, and
   main lighting. The switches, dead band, game mode, and bottom-out values
   applied by the reset stay volatile in this build.

```bash
madlionsctl reset-tuning
madlionsctl reset-tuning --save
```

If the snapshot cannot be written, the reset is cancelled. If lighting fails to
save, tuning is still saved and the command reports a warning with exit status 1.
The output includes the snapshot path.

## `profile`

Manage tuning profiles, full backups, and presets.

```bash
madlionsctl profile list
madlionsctl profile presets
madlionsctl profile save NAME [--full] [--force]
madlionsctl profile apply NAME [--save] [--persistent]
madlionsctl profile backup [--full]
```

### `profile list`

Lists saved tuning profiles, followed by full backups and automatic snapshots;
backup entries are marked `[backup]`.

### `profile presets`

Lists the built-in **Rapid fire**, **Balanced**, and **Typing** presets with
their summaries.

### `profile save NAME`

Capture the current state as a tuning profile.

```bash
madlionsctl profile save "FPS"
madlionsctl profile save "FPS" --force
```

- Tuning profiles go to the profiles directory.
- Existing names are not overwritten unless `--force` is passed.
- `--full` captures every section and stores the result in the backups directory
  instead.

### `profile apply NAME`

Apply a profile, full backup, or preset by case-insensitive name.

```bash
madlionsctl profile apply "FPS"
madlionsctl profile apply "FPS" --save
```

- A tuning profile applies volatile tuning. Add `--save` to persist actuation,
  rapid trigger, and main lighting. Switches, dead band, game mode, and bottom-out
  remain volatile in this build.
- A full backup refuses to apply unless `--persistent` is passed, because that
  writes keymap, macros, and advanced bindings immediately.
- With `--persistent`, the CLI first saves a complete “Before restore: …”
  snapshot.
- Ambiguous names are rejected with a list of candidates.
- Presets can be applied by name.

Full restore:

```bash
madlionsctl profile apply "Before restore: FPS" --persistent --save
```

### `profile backup`

Create an automatic-style backup.

```bash
madlionsctl profile backup
madlionsctl profile backup --full
```

The plain form captures tuning and uses the same automatic naming and ten-file
retention as the GUI. `--full` creates a full backup and keeps it until you
delete it. Full backups are not pruned automatically.

## `report`

Print a read-only device report for a support request.

```bash
madlionsctl report
madlionsctl report --json
```

The serial is replaced with `"redacted"` by default. Pass `--serial` only when
you deliberately want it included:

```bash
madlionsctl report --json --serial
```

The report is the preferred attachment for a device-support issue. Review it
before posting; it describes the device and firmware but does not contain your
macros or keymap.

## `test`

Print live analogue travel values.

```bash
madlionsctl test
madlionsctl test --seconds 5
madlionsctl test --json
madlionsctl test --json --seconds 2
```

- Without `--seconds`, it runs until Ctrl+C.
- `--seconds` accepts a value from 0 to 3600; 0 means no limit.
- The plain form prints active matrix indices and travel values, overwriting one
  line.
- `--json` prints one JSON array per sample, one array per line, which is easy to
  pipe into a script.

```bash
madlionsctl test --json --seconds 10 > travel.jsonl
```

The CLI polls at roughly 20 Hz for terminal output. The GUI's Test page is the
60 fps view; use the CLI when you need machine-readable samples rather than
smooth animation.

## Exit status

| Status | Meaning |
|---:|---|
| 0 | Success. |
| 1 | Device, permission, validation, or runtime error. |
| 2 | Argument error, or a write that did not read back. |
| 130 | Interrupted with Ctrl+C outside `test`; `test` exits 0 after Ctrl+C. |

Errors are printed to standard error as `error: ...`. Normal command output goes
to standard output, so it can be captured safely.

## Scripting examples

### Status-bar widget

```bash
madlionsctl status --json | jq -r '.board + " — " + .usb_id'
```

### Toggle rapid trigger for one key

```bash
madlionsctl rt on --press 0.10 --release 0.10 --key 2,1 --save
madlionsctl rt off --key 2,1 --save
```

### Apply a lighting preset and persist it

```bash
madlionsctl light --effect 6 --color '#ff4d6d' --brightness 150 --save
```

### Back up before a firmware experiment

```bash
madlionsctl profile save "Before experiment" --full
```

### Watch travel while typing

```bash
madlionsctl test --seconds 30
```

## Related documentation

- [Installation](INSTALLATION.md)
- [Using Madlions Control](USAGE.md)
- [Troubleshooting](TROUBLESHOOTING.md)
