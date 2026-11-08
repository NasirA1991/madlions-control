# Changelog

## 0.3.3 — 2026-11-08

### Fixed

- Preset and reset actuation buttons now apply the selected travel value.
- Programmatic lighting refreshes no longer trigger side-light writes.
- Saving to the keyboard reports a lighting-save failure instead of claiming full success.
- Keymap and macro success messages wait for the worker and read-back check.
- Macro editing controls are disabled in read-only sessions.
- Backup/profile deletion uses the exact file path instead of matching by display name.
- Short DKS, telemetry, keycode and optional-value replies now raise instead of being read as zero.
- Dark/light keyboard canvas detection, hardcoded key-count labels and max-travel constants are consistent.
- The installed udev rule matches the generated rule; install/uninstall paths and cache refresh are more robust.

### Tests

- Added widget regression tests for programmatic scale updates and side-light suppression.
- Added short-reply regression tests for DKS and single telemetry reads.
- Added profile-path and partial-save tests.

## 0.3.2 — 2026-11-04

### Changed
- Restored the Test page to 60 Hz sampling and 60 fps rendering, because the
  smoother analogue view is more useful than the CPU saving for this screen.
- The idle-repaint skip from 0.3.1 remains: an open Test page with no key moving
  stays at roughly 0% CPU.
- Live views are the only CPU-heavy mode; the rest of the app remains idle-cheap.

## 0.3.1 — 2026-11-04

### Changed
- Live telemetry now samples at 30 Hz instead of 60 Hz.
- The Test page stops repainting while every key is idle, and updates the heat
  map/gauge at 20 Hz while keys are moving. Active live-view CPU dropped from
  roughly 48% to 20% of one core on the reference machine; idle dropped to
  about 1%.
- Pages are built lazily on first visit, cutting startup work and initial
  memory a little.

## 0.3.0 — 2026-11-04

### Added
- **Keyboard shortcuts cheatsheet**, available from the main menu. It reads
  layer 1 of the current keymap, so Fn combinations reflect the board rather
  than a generic manual.
- Known QMK lighting keycodes are labelled (Fn + Tab toggles RGB lighting,
  Fn + W/S cycles effects, Fn + Q/A adjusts brightness, and so on).
- The cheatsheet can open the Keymap editor directly.

## 0.2.0 — 2026-11-04

### Added
- **Reset tuning** on verified boards with an observed baseline. It resets
  actuation, rapid trigger, lighting, switches and dead band, creates a tuning
  snapshot first, and deliberately leaves keymap, macros, advanced keys,
  hold/click, DKS, per-key colours and calibration untouched.
- `madlionsctl reset-tuning`, with the same safety scope.

## 0.1.1 — 2026-11-04

Reliability and recovery hardening.

### Fixed
- Short or empty bulk replies from the keyboard now raise a protocol error
  instead of leaving a bulk read loop stuck forever.
- Full backups now capture per-key colours, keymap, macros and advanced keys.
  Tuning snapshots are labelled separately and no longer pretend to be full
  restores.
- Applying a full backup shows a preview and asks for confirmation before
  writing persistent sections.
- Profile import is limited to 1 MiB and validates versions, numbers, colours,
  coordinates, keymaps and slot counts; NaN and infinity are rejected.
- Profile and settings writes are atomic, and profile names that sanitise to the
  same filename no longer overwrite each other.
- Automatic snapshot filenames are collision-free.
- The permissions dialog now emits only the audited hidraw rule; the broad USB
  rule was removed.
- The CLI now requires an explicit key selector, validates coordinates and
  ranges, rejects conflicting switches, and reads back rapid-trigger, lighting,
  dead-band and switch writes.
- Lighting's nonfunctional per-key switch is gone, black per-key colours render
  correctly, and mutating controls are disabled in read-only sessions.
- The keyboard canvas supports arrow-key navigation and Space/Enter activation.
- Persistent-section writes are validated before any tuning values are changed.

### Changed
- README and Flatpak notes document the broad `--device=all` permission honestly.
- Release assets now include SHA-256 checksums.

## 0.1.0 — 2026-11-04

First public release.

- Native GTK4/libadwaita configuration for MADLIONS magnetic-switch keyboards.
- Per-key actuation and rapid-trigger editing, with multi-select and heat maps.
- Live analogue travel test with full-board heat map, gauge and history.
- Lighting effects, brightness, speed, colour and per-key RGB painting.
- Four-layer keymap editor with a searchable keycode picker.
- Macro editor with keys, text, delays and sixteen slots.
- Rapid snappy, SOCD, OKS, hold/click and dynamic keystroke bindings.
- NKRO, Win lock, WASD swap, macOS mode, game mode, bottom-out optimisation and
  dead band.
- Named profiles, presets, import/export and automatic backups.
- `madlionsctl` command line interface.
- AppImage, Flatpak, source tarball and AUR packages.
