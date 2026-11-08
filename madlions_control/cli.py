"""Command line interface (``madlionsctl``)."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

from . import baseline, boards, config, layout, profiles, state as state_mod
from .demo import DemoBackend
from .device import (
    AdvancedKey,
    BoxLight,
    DeadBand,
    DeviceError,
    Features,
    LightInfo,
    MadlionsDevice,
    RapidTrigger,
    clamp_travel,
)
from .lighting import BRIGHTNESS_MAX, EFFECTS, clamp_speed, effect_name, hex_to_rgb
from .transport import discover, find_supported


def _select_device(selector: str | None):
    if not selector:
        return find_supported()
    needle = selector.strip()
    for info in discover():
        if needle in (info.path, info.hidraw, info.usb_id):
            if not info.supported:
                raise DeviceError(
                    f"{info.usb_id} matched {selector!r}, but {info.reason}"
                )
            return info
    raise DeviceError(
        f"no supported MADLIONS keyboard matched {selector!r}; "
        "run 'madlionsctl scan' to list devices"
    )


def _open_device(args) -> tuple[object, object]:
    if getattr(args, "demo", False):
        backend = DemoBackend()
        return backend, state_mod.load_basic(backend)
    info = _select_device(getattr(args, "device", None))
    device = MadlionsDevice.open(
        info=info,
        allow_unverified=getattr(args, "allow_unverified", False),
    )
    return device, state_mod.load_basic(device)


def _print_status(loaded, as_json: bool) -> None:
    info = loaded.info
    if as_json:
        payload = {
            "board": info.board.name,
            "usb_id": info.usb_id,
            "hidraw": info.hidraw,
            "protocol_version": info.protocol_version,
            "writable": info.writable,
            "layers": loaded.layers,
            "actuation_mm": {
                "min": min(loaded.actuation) if loaded.actuation else None,
                "max": max(loaded.actuation) if loaded.actuation else None,
                "default": loaded.actuation[0] if loaded.actuation else None,
            },
            "rapid_trigger": {
                "enabled": sum(1 for rt in loaded.rapid_trigger if rt.enabled),
                "total": len(loaded.rapid_trigger),
            },
            "light": loaded.light.to_json(),
            "features": loaded.features.to_json(),
            "dead_band": loaded.dead_band.to_json(),
            "game_mode": loaded.game_mode,
            "bottom_optimize": loaded.bottom_optimize,
            "box_light": loaded.box_light.__dict__,
        }
        print(json.dumps(payload, indent=2))
        return
    print(f"{info.title}  [{info.usb_id}]  {info.hidraw}")
    print(f"  protocol     {info.protocol_label}{' (verified)' if info.firmware_verified else ' (unverified)'}")
    print(f"  layout       {info.board.rows} x {info.board.cols}, {loaded.layers} layers, {info.board.total_keys} matrix cells")
    print(f"  writes       {'enabled' if info.writable else 'read-only: ' + info.read_only_reason}")
    if loaded.actuation:
        print(f"  actuation    {min(loaded.actuation):.2f} – {max(loaded.actuation):.2f} mm (default {loaded.actuation[0]:.2f})")
    print(f"  rapid trig.  {sum(1 for rt in loaded.rapid_trigger if rt.enabled)} / {len(loaded.rapid_trigger)} keys")
    print(f"  lighting     {effect_name(loaded.light.effect)} · brightness {loaded.light.brightness} · {loaded.light.hex}")
    print(f"  switches     NKRO {loaded.features.nkro}, Win lock {loaded.features.win_lock}, WASD swap {loaded.features.wasd_swap}, Mac {loaded.features.mac_mode}")
    print(f"  dead band    top {loaded.dead_band.top_mm:.2f} mm, bottom {loaded.dead_band.bottom_mm:.2f} mm")
    print(f"  game mode    {loaded.game_mode} · bottom-out {loaded.bottom_optimize}")


def _parse_key(text: str) -> tuple[int, int]:
    try:
        row, col = (int(part) for part in text.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid key {text!r}, expected ROW,COL") from exc
    if row < 0 or col < 0:
        raise argparse.ArgumentTypeError("row and column must be zero or greater")
    return row, col


def _finite_float(text: str) -> float:
    try:
        value = float(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid number: {text!r}") from exc
    if not math.isfinite(value):
        raise argparse.ArgumentTypeError("number must be finite")
    return value


def _range_float(lower: float, upper: float):
    def parse(text: str) -> float:
        value = _finite_float(text)
        if not lower <= value <= upper:
            raise argparse.ArgumentTypeError(
                f"value must be between {lower:g} and {upper:g}"
            )
        return value
    return parse


def _range_int(lower: int, upper: int):
    def parse(text: str) -> int:
        try:
            value = int(text, 0)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(f"invalid integer: {text!r}") from exc
        if not lower <= value <= upper:
            raise argparse.ArgumentTypeError(
                f"value must be between {lower} and {upper}"
            )
        return value
    return parse


def _effect_number(text: str) -> int:
    value = _range_int(0, 255)(text)
    if value not in {effect.number for effect in EFFECTS}:
        raise argparse.ArgumentTypeError(f"unknown lighting effect {value}")
    return value


def _colour(text: str) -> str:
    try:
        hex_to_rgb(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    return text


def _selectable_keys(loaded) -> set[tuple[int, int]]:
    return {(key.row, key.col) for key in layout.keys_for(loaded.board)}


def _selected(args, loaded) -> list[tuple[int, int]]:
    requested = getattr(args, "key", None) or []
    physical = _selectable_keys(loaded)
    if requested:
        for row, col in requested:
            if not (0 <= row < loaded.board.rows and 0 <= col < loaded.board.cols):
                raise DeviceError(
                    f"key {row},{col} is outside the {loaded.board.rows}x"
                    f"{loaded.board.cols} matrix"
                )
            if (row, col) not in physical:
                raise DeviceError(
                    f"matrix position {row},{col} has no physical key on "
                    f"{loaded.board.name}"
                )
        return requested
    if getattr(args, "all", False):
        return sorted(physical)
    raise DeviceError("choose keys with --key ROW,COL or --all")


def _flatten(loaded, values_by_key, default) -> list:
    out = list(default)
    for (row, col), value in values_by_key.items():
        index = row * loaded.board.cols + col
        if 0 <= index < len(out):
            out[index] = value
    return out


def cmd_status(args) -> int:
    device, loaded = _open_device(args)
    try:
        _print_status(loaded, args.json)
        return 0
    finally:
        device.close()


def cmd_scan(args) -> int:
    nodes = discover()
    if not nodes:
        print("No MADLIONS vendor HID collection found.")
        return 1
    for node in nodes:
        flag = "supported" if node.supported else f"unsupported ({node.reason})"
        print(f"{node.path:20} {node.usb_id}  {node.title:22} {flag}")
    return 0


def cmd_actuation(args) -> int:
    device, loaded = _open_device(args)
    try:
        if not loaded.writable:
            raise DeviceError(loaded.info.read_only_reason or "read-only session")
        value = clamp_travel(args.mm)
        changes = {key: value for key in _selected(args, loaded)}
        targets = _flatten(loaded, changes, loaded.actuation)
        device.write_actuation(targets)
        if args.save:
            device.commit()
        current = device.read_actuation()
        if len(current) < loaded.board.total_keys:
            raise DeviceError("the keyboard returned an incomplete actuation read-back")
        mismatches = [
            (key, value) for key, value in changes.items()
            if abs(current[key[0] * loaded.board.cols + key[1]] - value) > 0.011
        ]
        if mismatches:
            print(f"wrote {len(changes)} key(s), but {len(mismatches)} did not read back", file=sys.stderr)
            return 2
        print(f"actuation {value:.2f} mm applied to {len(changes)} key(s)"
              + (" and saved" if args.save else " (not saved)"))
        return 0
    finally:
        device.close()


def cmd_rt(args) -> int:
    device, loaded = _open_device(args)
    try:
        if not loaded.writable:
            raise DeviceError(loaded.info.read_only_reason or "read-only session")
        enabled = args.state == "on"
        press = args.press if args.press is not None else 0.50
        release = args.release if args.release is not None else 0.50
        changes = {
            key: RapidTrigger(enabled, clamp_travel(press), clamp_travel(release))
            for key in _selected(args, loaded)
        }
        targets = _flatten(loaded, changes, loaded.rapid_trigger)
        device.write_rapid_trigger(targets)
        if args.save:
            device.commit()
        current = device.read_rapid_trigger()
        mismatches = []
        for (row, col), target in changes.items():
            index = row * loaded.board.cols + col
            actual = current[index]
            if (actual.enabled != target.enabled
                    or abs(actual.press_mm - target.press_mm) > 0.011
                    or abs(actual.release_mm - target.release_mm) > 0.011):
                mismatches.append((row, col))
        if mismatches:
            print(f"wrote {len(changes)} key(s), but {len(mismatches)} did not read back",
                  file=sys.stderr)
            return 2
        print(f"rapid trigger {'on' if enabled else 'off'} ({press:.2f}/{release:.2f} mm) "
              f"for {len(changes)} key(s)" + (" and saved" if args.save else " (not saved)"))
        return 0
    finally:
        device.close()


def cmd_light(args) -> int:
    device, loaded = _open_device(args)
    try:
        if not loaded.writable:
            raise DeviceError(loaded.info.read_only_reason or "read-only session")
        if (args.effect is None and args.color is None
                and args.brightness is None and args.speed is None):
            raise DeviceError("choose at least one of --effect, --color, --brightness or --speed")
        light = loaded.light
        if args.effect is not None:
            light = LightInfo(effect=args.effect, speed=light.speed, r=light.r,
                              g=light.g, b=light.b, brightness=light.brightness)
        if args.color:
            r, g, b = hex_to_rgb(args.color)
            light = LightInfo(effect=light.effect, speed=light.speed, r=r, g=g, b=b,
                              brightness=light.brightness)
        if args.brightness is not None:
            light = LightInfo(effect=light.effect, speed=light.speed, r=light.r,
                              g=light.g, b=light.b,
                              brightness=min(args.brightness, BRIGHTNESS_MAX))
        if args.speed is not None:
            light = LightInfo(effect=light.effect, speed=clamp_speed(args.speed),
                              r=light.r, g=light.g, b=light.b,
                              brightness=light.brightness)
        device.write_light(light)
        if args.save:
            device.save_lighting()
        actual = device.read_light()
        if (actual.effect != light.effect or actual.brightness != light.brightness
                or (light.speed and actual.speed != light.speed)):
            print("lighting was written but the keyboard read back different values",
                  file=sys.stderr)
            return 2
        print(f"lighting: {effect_name(light.effect)} · brightness {light.brightness} · {light.hex}")
        return 0
    finally:
        device.close()


def cmd_deadband(args) -> int:
    device, loaded = _open_device(args)
    try:
        if not loaded.writable:
            raise DeviceError(loaded.info.read_only_reason or "read-only session")
        if args.top is None and args.bottom is None:
            raise DeviceError("choose --top and/or --bottom")
        band = DeadBand(
            top_mm=args.top if args.top is not None else loaded.dead_band.top_mm,
            bottom_mm=args.bottom if args.bottom is not None else loaded.dead_band.bottom_mm,
        )
        device.write_dead_band(band)
        actual = device.read_dead_band()
        if (abs(actual.top_mm - band.top_mm) > 0.011
                or abs(actual.bottom_mm - band.bottom_mm) > 0.011):
            print("dead band was written but did not read back", file=sys.stderr)
            return 2
        print(f"dead band top {band.top_mm:.2f} mm, bottom {band.bottom_mm:.2f} mm")
        return 0
    finally:
        device.close()


def cmd_features(args) -> int:
    device, loaded = _open_device(args)
    try:
        if not loaded.writable:
            raise DeviceError(loaded.info.read_only_reason or "read-only session")
        if not any((args.nkro, args.six_key, args.win_lock, args.no_win_lock,
                    args.wasd, args.no_wasd, args.mac, args.no_mac,
                    args.game is not None, args.bottom is not None)):
            raise DeviceError("choose at least one feature to change")
        current = loaded.features
        features = Features(
            rgb_area=current.rgb_area,
            wasd_swap=1 if args.wasd else 0 if args.no_wasd else current.wasd_swap,
            mac_mode=1 if args.mac else 0 if args.no_mac else current.mac_mode,
            win_lock=1 if args.win_lock else 0 if args.no_win_lock else current.win_lock,
            nkro=0 if args.six_key else 1 if args.nkro else current.nkro,
        )
        game = None
        bottom = None
        if args.game is not None:
            game = int(args.game)
        if args.bottom is not None:
            bottom = int(args.bottom)
        device.write_features(features)
        if game is not None:
            device.write_game_mode(game)
        if bottom is not None:
            device.write_bottom_optimize(bottom)
        actual = device.read_features()
        if actual != features:
            print("features were written but did not read back", file=sys.stderr)
            return 2
        if game is not None and device.read_game_mode() != game:
            print("game mode was written but did not read back", file=sys.stderr)
            return 2
        if bottom is not None and device.read_bottom_optimize() != bottom:
            print("bottom-out optimisation was written but did not read back",
                  file=sys.stderr)
            return 2
        print(f"switches: NKRO {features.nkro}, Win lock {features.win_lock}, "
              f"WASD swap {features.wasd_swap}, Mac {features.mac_mode}")
        if game is not None:
            print(f"game mode: {game}")
        if bottom is not None:
            print(f"bottom-out optimisation: {bottom}")
        return 0
    finally:
        device.close()


def cmd_reset_tuning(args) -> int:
    device, loaded = _open_device(args)
    try:
        spec = baseline.require(loaded.board)
        snapshot = profiles.auto_backup(
            loaded,
            description="Tuning snapshot taken automatically before a CLI baseline reset",
        )
        if snapshot is None:
            print("error: no tuning state to snapshot; reset cancelled", file=sys.stderr)
            return 1
        actions = spec.apply(device, loaded.board)
        warning = None
        if args.save:
            warning = device.save_all()
        print(f"applied {spec.label}: {', '.join(actions)}")
        print(f"snapshot: {snapshot}")
        if warning:
            print(
                "tuning saved, but lighting was not: "
                f"{warning}; try the save again",
                file=sys.stderr,
            )
        if not args.save:
            print("volatile baseline applied (not saved)")
        elif warning:
            print("volatile baseline applied; tuning saved, lighting not saved")
        else:
            print("volatile baseline applied and saved")
        return 1 if warning else 0
    finally:
        device.close()


def cmd_profile(args) -> int:
    if args.profile_action == "list":
        for profile in profiles.list_profiles():
            kind = "full" if profile.is_full else "tuning"
            print(f"{profile.name:28} {kind:6} {profiles.section_summary(profile)}")
        for _path, profile in profiles.list_backups():
            kind = "full" if profile.is_full else "snapshot"
            print(f"{profile.name:28} {kind:6} {profiles.section_summary(profile)}  [backup]")
        return 0
    if args.profile_action == "presets":
        for profile in profiles.presets():
            print(f"{profile.name:28} {profiles.profile_summary(profile)}")
        return 0

    device, loaded = _open_device(args)
    try:
        if args.profile_action == "save":
            if args.full:
                profile = profiles.Profile.capture_device(
                    device, args.name, "Full backup from the command line", full=True,
                )
            else:
                profile = profiles.Profile.capture(
                    loaded, args.name, "Saved from the command line", full=False,
                )
            path = profile.save(config.backups_dir() if args.full else None)
            print(f"saved {path} ({'full' if profile.is_full else 'tuning'})")
            return 0
        if args.profile_action == "backup":
            if args.full:
                profile, path = profiles.full_backup(device)
                print(f"saved {path} (full)")
            else:
                path = profiles.auto_backup(loaded)
                print(f"saved {path} (tuning)" if path else "nothing to back up")
            return 0
        if args.profile_action == "apply":
            matches = [p for p in profiles.list_profiles() if p.name.lower() == args.name.lower()]
            if not matches:
                matches = [p for _path, p in profiles.list_backups()
                           if p.name.lower() == args.name.lower()]
            if not matches:
                matches = [p for p in profiles.presets() if p.name.lower() == args.name.lower()]
            if not matches:
                print(f"no profile named {args.name!r}", file=sys.stderr)
                return 1
            profile = matches[0]
            if profile.has_persistent_sections and not args.persistent:
                print(
                    f"{profile.name!r} contains persistent sections "
                    f"({profiles.section_summary(profile)}). Pass --persistent "
                    f"to apply them; this writes keymap, macros or advanced bindings.",
                    file=sys.stderr,
                )
                return 1
            snapshot = None
            if args.persistent and profile.has_persistent_sections:
                _snapshot_profile, snapshot = profiles.full_backup(
                    device, name=f"Before restore: {profile.name}",
                )
            actions = profile.apply(
                device, loaded,
                include_keymap=bool(args.persistent and profile.keymap_hex),
                include_macros=bool(args.persistent and profile.macros_hex),
                include_advanced=bool(
                    args.persistent and (profile.advanced_keys is not None
                                         or profile.tap_dance is not None
                                         or profile.dks is not None)
                ),
            )
            if args.save:
                profile.save_to_keyboard(device, loaded)
            note = (
                " (persistent sections written immediately)"
                if profile.has_persistent_sections and args.persistent
                else " (saved)" if args.save else " (volatile)"
            )
            print(f"applied {profile.name}: "
                  f"{', '.join(actions) if actions else 'no changes'}{note}")
            if snapshot is not None:
                print(f"pre-restore snapshot: {snapshot}")
            return 0
    finally:
        device.close()
    return 2


def cmd_report(args) -> int:
    device, _loaded = _open_device(args)
    try:
        report = device.read_report()
        if args.json:
            print(json.dumps(report, indent=2, default=str))
        else:
            for key, value in report.items():
                print(f"{key}: {value}")
        return 0
    finally:
        device.close()


def cmd_test(args) -> int:
    import time

    device, loaded = _open_device(args)
    try:
        if not args.json:
            print("Live travel (Ctrl+C to stop)…")
        deadline = time.monotonic() + args.seconds if args.seconds else None
        while deadline is None or time.monotonic() < deadline:
            values = device.read_travel()
            if args.json:
                print(json.dumps([round(value, 2) for value in values]))
            else:
                active = [
                    (index, value) for index, value in enumerate(values) if value > 0
                ]
                text = "  ".join(f"{index}:{value:.2f}" for index, value in active[:16])
                print("\r" + (text or "—").ljust(100), end="", flush=True)
            time.sleep(0.05)
        if not args.json:
            print()
        return 0
    except KeyboardInterrupt:
        return 0
    finally:
        device.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="madlionsctl",
        description="Command line access to MADLIONS magnetic-switch keyboards.",
    )
    parser.add_argument("--demo", action="store_true", help="use a simulated keyboard")
    parser.add_argument("--allow-unverified", action="store_true",
                        help="allow writes on an unverified board (dangerous)")
    parser.add_argument("--device", default=None,
                        help="select a device by /dev/hidrawN, hidrawN or USB ID")
    parser.add_argument("--version", action="version", version=f"%(prog)s {config.VERSION}")
    sub = parser.add_subparsers(dest="command", required=True)

    status = sub.add_parser("status", help="show the connected keyboard")
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=cmd_status)

    scan = sub.add_parser("scan", help="list MADLIONS HID collections")
    scan.set_defaults(func=cmd_scan)

    actuation = sub.add_parser("actuation", help="set the actuation point in millimetres")
    actuation.add_argument("mm", type=_range_float(0.05, 3.40))
    actuation_group = actuation.add_mutually_exclusive_group(required=True)
    actuation_group.add_argument("--key", action="append", type=_parse_key,
                                 help="ROW,COL (repeatable)")
    actuation_group.add_argument("--all", action="store_true")
    actuation.add_argument("--save", action="store_true", help="persist to keyboard flash")
    actuation.set_defaults(func=cmd_actuation)

    rt = sub.add_parser("rt", help="set rapid trigger")
    rt.add_argument("state", choices=("on", "off"))
    rt.add_argument("--press", type=_range_float(0.01, 3.40), default=None)
    rt.add_argument("--release", type=_range_float(0.01, 3.40), default=None)
    rt_group = rt.add_mutually_exclusive_group(required=True)
    rt_group.add_argument("--key", action="append", type=_parse_key)
    rt_group.add_argument("--all", action="store_true")
    rt.add_argument("--save", action="store_true")
    rt.set_defaults(func=cmd_rt)

    light = sub.add_parser("light", help="change lighting")
    light.add_argument("--effect", type=_effect_number)
    light.add_argument("--brightness", type=_range_int(0, BRIGHTNESS_MAX))
    light.add_argument("--speed", type=_range_int(1, 255))
    light.add_argument("--color", type=_colour)
    light.add_argument("--save", action="store_true")
    light.set_defaults(func=cmd_light)

    deadband = sub.add_parser("deadband", help="set the top/bottom dead band")
    deadband.add_argument("--top", type=_range_float(0.0, 0.50))
    deadband.add_argument("--bottom", type=_range_float(0.0, 0.50))
    deadband.set_defaults(func=cmd_deadband)

    features = sub.add_parser("features", help="keyboard switches and game mode")
    nkro = features.add_mutually_exclusive_group()
    nkro.add_argument("--nkro", action="store_true")
    nkro.add_argument("--six-key", action="store_true")
    win = features.add_mutually_exclusive_group()
    win.add_argument("--win-lock", action="store_true")
    win.add_argument("--no-win-lock", action="store_true")
    wasd = features.add_mutually_exclusive_group()
    wasd.add_argument("--wasd", action="store_true")
    wasd.add_argument("--no-wasd", action="store_true")
    mac = features.add_mutually_exclusive_group()
    mac.add_argument("--mac", action="store_true")
    mac.add_argument("--no-mac", action="store_true")
    features.add_argument("--game", type=_range_int(0, 255))
    features.add_argument("--bottom", type=_range_int(0, 255))
    features.set_defaults(func=cmd_features)

    reset = sub.add_parser("reset-tuning", help="reset volatile tuning to the board baseline")
    reset.add_argument("--save", action="store_true", help="persist the reset to keyboard flash")
    reset.set_defaults(func=cmd_reset_tuning)

    profile = sub.add_parser("profile", help="manage profiles")
    profile_sub = profile.add_subparsers(dest="profile_action", required=True)
    profile_list = profile_sub.add_parser("list")
    profile_list.set_defaults(func=cmd_profile, name="")
    profile_presets = profile_sub.add_parser("presets")
    profile_presets.set_defaults(func=cmd_profile, name="")
    profile_save = profile_sub.add_parser("save")
    profile_save.add_argument("name")
    profile_save.add_argument("--full", action="store_true",
                              help="capture a full backup, including persistent sections")
    profile_save.set_defaults(func=cmd_profile)
    profile_apply = profile_sub.add_parser("apply")
    profile_apply.add_argument("name")
    profile_apply.add_argument("--save", action="store_true")
    profile_apply.add_argument("--persistent", action="store_true",
                               help="also restore keymap, macros and advanced bindings")
    profile_apply.set_defaults(func=cmd_profile)
    profile_backup = profile_sub.add_parser("backup")
    profile_backup.add_argument("--full", action="store_true")
    profile_backup.set_defaults(func=cmd_profile, name="")

    report = sub.add_parser("report", help="read-only diagnostics")
    report.add_argument("--json", action="store_true")
    report.set_defaults(func=cmd_report)

    test = sub.add_parser("test", help="print live key travel")
    test.add_argument("--seconds", type=_range_float(0, 3600), default=0)
    test.add_argument("--json", action="store_true")
    test.set_defaults(func=cmd_test)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args) or 0)
    except (DeviceError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
