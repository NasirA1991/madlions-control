# Changelog

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
