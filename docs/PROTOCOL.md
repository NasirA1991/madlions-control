# MADLIONS 32-byte vendor HID protocol

This is the subset used by Madlions Control. It was verified on a **MAD68 HE
RGB** (`373B:1058`, firmware protocol 9) against physical hardware, including
writes and read-back. Other models in `boards.py` share the controller but are
not individually verified here.

## Interface

- USB vendor `0x373B` (Shenzhen Yizhita / MADLIONS / FGG).
- Vendor HID collection: usage page `0xFF60`, usage `0x61`.
- 32-byte reports, no report ID, 32-byte IN and OUT endpoints.
- Discovered by scanning `/sys/class/hidraw` for the descriptor signature
  `06 60 FF 09 61 ... 95 20 75 08`; interface numbers differ between boards.

The kernel's hidraw write takes the 32 bytes directly on this interface. Reads
return 32 bytes. Some firmware builds use a leading report-ID byte; the transport
only retries the alternative form for the initial read probe.

## Commands

| Byte | VIA command |
|---|---|
| `0x01` | get protocol version (reply `01 00 09` on the verified board) |
| `0x02` | get keyboard value |
| `0x03` | set keyboard value |
| `0x04` / `0x05` | dynamic keymap get / set keycode |
| `0x09` | custom save |
| `0x0C` / `0x0D` | macro count / buffer size |
| `0x0E` / `0x0F` | macro buffer get / set |
| `0x11` | layer count |
| `0x12` / `0x13` | dynamic keymap buffer get / set |
| `0x07` / `0x08` | custom set / get (lighting) |
| `0xFE` | Vial prefix (hold/click) |

Vendor reads/writes are `0x02|0x03, 0x96, sub, ...`.

## Hall-effect values

Bulk (buffer) requests and writes use:

```
02 96 SUB 00 00 OFF_HI OFF_LO COUNT ...   (read)
03 96 SUB 00 00 OFF_HI OFF_LO COUNT FLASH DATA...  (write)
```

- `OFF` is a linear key index `row * cols + col`.
- `SUB 0x0D` actuation, 2 bytes per key, uint16 BE, 0.01 mm.
- `SUB 0x0E` rapid trigger, 5 bytes per key: enabled, release u16, press u16.
- `SUB 0x16` raw ADC per key, u16 BE; empty matrix positions read 4096.
- `SUB 0x17` live linearised travel per key, u16 BE, 0.01 mm, 0 at rest.
- `FLASH 0x00` applies without persisting; `0x03` erases/writes flash.
- Verified limit for the UI: 0.05–3.40 mm.

Single-key reads exist (`0x03` actuation, `0x07` RT, `0x0A` trip, `0x09` ADC).
The single-trip reply data starts at raw byte 5.

The matrix is 5 × 15 for the 68-key board. Empty positions are exactly the
gaps in the physical layout: `(2,12)`, `(3,1)`, and `(4,3)`, `(4,4)`, `(4,5)`,
`(4,7)`, `(4,8)`. The ADC buffer reports 4096 on those positions. The populated
matrix cells are 68.

## Keymap

- Big-endian 16-bit QMK keycodes, 4 layers × 5 × 15 × 2 = 600 bytes.
- `GET_KEYCODE` reply: `04 layer row col key_hi key_lo`; `SET_KEYCODE` payload is
  `05 layer row col key_hi key_lo`. Verified by reading the dynamic keymap
  buffer back (a full-buffer write is the safest way to restore a keymap).
- The verified board's right column is **Ins, Del, PgUp, PgDn**, not the common
  65% Del/PgUp/PgDn/End arrangement.
- Default layer 0 also confirms the arrow cluster, Fn = MO(1), and the two empty
  rows.

## Macros

- The verified board reports 16 macro slots and a **7148-byte** buffer.
- Same VIA buffer framing as keymaps (`0x0E`/`0x0F`, 28 bytes per packet).
- NUL-separated slots; `0x01` escape; opcodes 1/2/3 tap/down/up, 4 delay, 5/6/7
  Vial 16-bit keycodes. `macros_codec.py` implements the codec and preserves the
  unmanaged tail of the buffer.

## Lighting

- Global light: `CUSTOM_GET/SET` (`0x08`/`0x07`) with sub `0x41`.
  Reply: effect at raw[2], speed raw[4], RGB raw[5:8], brightness raw[8].
  Brightness above 210 is silently dropped by the firmware.
- Per-key colour: get sub `0x45` (`row, col, count`), set sub `0x42`.
  Replies start at raw[5]; up to 9 colours per packet.
- Save lighting: `03 96 12`.
- **Colour read-back is gamma-corrected and may not equal the value written.**
  Write the requested colour; do not fight the read-back.
- When the effect is `Off`, the firmware keeps the old colour/brightness values
  until an effect that uses them is selected. Stage a colour with a solid effect
  if an exact restore matters.
- `box light` (`0x21`) reads all zeros and does not change on write on 0x1058;
  the verified board has no side light, so the UI hides it. The command is still
  harmless on boards that do not implement it.

## Other features

- Features `03 96 11 rgb_area wasd mac winlock nkro` — verified.
- Dead band `03 96 0B top_u16 bottom_u16` (0.01 mm) — verified.
- Game mode `03 96 1E`, bottom-out optimisation `03 96 1D` — verified.
- Advanced keys `03 96 20 ...` with `SubField.GET/SET`; SOCD modes
  `2..5`, OKS `6`, RS `1`. The vendor folds IDs >= 0x1A by −0x1A.
- DKS `03 96 0F` (4 × 4-byte actions: status u16, keycode u16).
- Hold/click uses the Vial prefix: `FE 0D 02 index tap_u16 hold_u16 timer_u16`.
- Calibration status `0x1F` returns all zeros on the verified firmware; the app
  falls back to the physical layout instead of treating that as "uncalibrated".

## Safety

- Reads are always safe.
- The app refuses writes when the firmware protocol is not the verified version
  or the board model is not verified, unless the CLI is explicitly run with
  `--allow-unverified`.
- Firmware flashing, DFU, sensor calibration, EEPROM reset and bootloader jumps
  are not implemented.

## Provenance

The packet layouts and vendor sub-command numbers were recovered from the
official FGG/MADLIONS WebHID configurator. The verification above was done
against the physical keyboard; no vendor code is included in this project.
