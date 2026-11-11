# Contributing

Thank you for helping make MADLIONS keyboards work properly on Linux.

## Documentation

The user-facing documentation is split by task:

- [README](README.md) — overview, features, quick install.
- [Installation](docs/INSTALLATION.md) — methods, dependencies, permissions.
- [Usage](docs/USAGE.md) — pages, saving rules, profiles.
- [CLI reference](docs/CLI.md) — commands and examples.
- [Troubleshooting](docs/TROUBLESHOOTING.md) — common problems.
- [Development](docs/DEVELOPMENT.md) — architecture, tests, protocol work.

Update the relevant guide when behavior, commands, or limitations change. Keep
the README as an entry point rather than duplicating detailed instructions.

## Device reports are the most useful contribution

If you own a MADLIONS keyboard that is not the verified MAD68 HE RGB, please
open a **Device report** issue. Run:

```bash
madlionsctl scan
madlionsctl status
madlionsctl report --json
```

Review the JSON locally; it contains the product ID, firmware protocol, layout
and current settings, and nothing is uploaded automatically.

## Code contributions

- Keep the write gate intact. Unverified boards must stay read-only by default;
  never add a write that bypasses `MadlionsDevice._guard`.
- Do not add firmware flashing, DFU, calibration or factory reset. They are
  intentionally out of scope and are the operations most likely to leave a board
  in a bad state.
- Keep flash writes explicit. Tuning writes with `FLASH_NORMAL` stay volatile
  until `commit()`; lighting stays volatile until `save_lighting()`. Keymap,
  macro, and advanced-binding writes are immediate.
- Add or update a unit test for packet changes and for profile/macro encoding.
- UI changes should be checked with `--demo` at 1180 × 780 and under a narrow
  window. Screenshots can be regenerated with `./tools/screenshots.sh`.

```bash
python3 -m unittest discover -s tests -v
xvfb-run -a python3 -m unittest tests.test_widgets -v
python3 -m compileall -q madlions_control
```

## Commit style

Short imperative subjects are enough. Mention the board or protocol area when
the change is hardware-specific.

## License

By contributing you agree that your changes are licensed under the MIT license.
