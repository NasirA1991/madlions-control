# Contributing

Thank you for helping make MADLIONS keyboards work properly on Linux.

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
- Keep flash writes explicit. Volatile changes use `FLASH_NORMAL`; only
  `commit()` and `save_lighting()` persist.
- Add or update a unit test for packet changes and for profile/macro encoding.
- UI changes should be checked with `--demo` at 1180 × 780 and under a narrow
  window. Screenshots can be regenerated with `./tools/screenshots.sh`.

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q madlions_control
```

## Commit style

Short imperative subjects are enough. Mention the board or protocol area when
the change is hardware-specific.

## License

By contributing you agree that your changes are licensed under the MIT license.
