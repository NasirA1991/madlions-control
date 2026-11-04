import unittest

from madlions_control import boards, demo, keycodes, layout, lighting, macros_codec, profiles
from madlions_control import state as state_mod
from madlions_control.device import (
    DEFAULT_ACTUATION_MM,
    RapidTrigger,
    build_report,
    clamp_travel,
    travel_from_raw,
    travel_to_raw,
)
from madlions_control.transport import udev_rule


class LayoutTests(unittest.TestCase):
    def test_65_percent_has_68_keys(self):
        keys = layout.keys_for(boards.DEFAULT_BOARD)
        self.assertEqual(len(keys), 68)
        self.assertEqual(len({(key.row, key.col) for key in keys}), 68)
        self.assertEqual(layout.max_row_width(layout.layout_for(boards.DEFAULT_BOARD)), 16.0)

    def test_60_percent_has_61_keys(self):
        board = boards.lookup(0x1053)
        keys = layout.keys_for(board)
        self.assertEqual(len(keys), 61)
        self.assertEqual(layout.max_row_width(layout.layout_for(board)), 15.0)

    def test_key_lookup(self):
        key = layout.key_at(boards.DEFAULT_BOARD, 4, 6)
        self.assertIsNotNone(key)
        self.assertEqual(key.label, "Space")
        self.assertGreater(key.width, 6)


class KeycodeTests(unittest.TestCase):
    def test_basic_codes(self):
        self.assertEqual(keycodes.from_name("A"), 0x04)
        self.assertEqual(keycodes.from_name("Space"), 0x2C)
        self.assertEqual(keycodes.from_name("MO(1)"), 0x5221)
        self.assertEqual(keycodes.from_name("0x5221"), 0x5221)
        self.assertEqual(keycodes.label(0x5221), "MO 1")

    def test_labels_are_nonempty(self):
        for code in (0x00, 0x01, 0x04, 0x28, 0x2C, 0xE0, 0x5220, 0xFFFF):
            self.assertTrue(keycodes.label(code))


class ProtocolUnitTests(unittest.TestCase):
    def test_report_is_32_bytes(self):
        report = build_report(0x02, bytes([0x96, 0x0D]))
        self.assertEqual(len(report), 32)
        self.assertEqual(report[:3], bytes([0x02, 0x96, 0x0D]))

    def test_travel_round_trip(self):
        for value in (0.05, 0.10, 0.95, 1.50, 3.40):
            self.assertAlmostEqual(travel_from_raw(travel_to_raw(value)), value, places=2)
        self.assertEqual(clamp_travel(99), 3.40)
        self.assertEqual(clamp_travel(-1), 0.05)
        self.assertEqual(travel_to_raw(DEFAULT_ACTUATION_MM), 150)

    def test_udev_rule(self):
        text = udev_rule()
        self.assertIn('idVendor}=="373b"', text)
        self.assertIn("uaccess", text)


class MacroTests(unittest.TestCase):
    def test_round_trip(self):
        steps = [
            macros_codec.MacroStep("text", text="gg"),
            macros_codec.MacroStep("delay", delay_ms=120),
            macros_codec.MacroStep("tap", keycode=0x04),
            macros_codec.MacroStep("tap", keycode=0x5221),
        ]
        encoded = macros_codec.encode(steps)
        decoded = macros_codec.decode(encoded)
        self.assertEqual(len(decoded), 4)
        self.assertEqual(decoded[0].text, "gg")
        self.assertEqual(decoded[1].delay_ms, 120)
        self.assertEqual(decoded[2].keycode, 0x04)
        self.assertEqual(decoded[3].keycode, 0x5221)

    def test_rebuild_keeps_other_slots_and_tail(self):
        buffer = bytearray(64)
        buffer[0:3] = b"one"
        buffer[3] = 0
        buffer[4:7] = b"two"
        buffer[7] = 0
        buffer[8:14] = b"secret"
        rebuilt = macros_codec.rebuild(bytes(buffer), 0, b"new", 2)
        self.assertEqual(len(rebuilt), 64)
        self.assertEqual(macros_codec.split(rebuilt, 2)[0], b"new")
        self.assertEqual(macros_codec.split(rebuilt, 2)[1], b"two")
        self.assertIn(b"secret", rebuilt)

    def test_rejects_invalid_text(self):
        with self.assertRaises(ValueError):
            macros_codec.encode([macros_codec.MacroStep("text", text="\x00")])


class ProfileTests(unittest.TestCase):
    def test_capture_and_round_trip(self):
        backend = demo.DemoBackend()
        state = state_mod.load_basic(backend)
        profile = profiles.Profile.capture(state, "Demo", "test")
        data = profile.to_json()
        again = profiles.Profile.from_json(data)
        self.assertEqual(again.name, "Demo")
        self.assertAlmostEqual(again.actuation_default, profile.actuation_default, places=2)
        self.assertEqual(again.rt_default, profile.rt_default)
        self.assertEqual(again.light, profile.light)

    def test_fit_colors(self):
        colors = [(i, i, i) for i in range(75)]
        fitted = profiles.fit_colors(colors, 15, 5, 14)
        self.assertEqual(len(fitted), 70)
        self.assertEqual(fitted[0], (0, 0, 0))
        self.assertEqual(fitted[13], (13, 13, 13))
        self.assertEqual(fitted[14], (15, 15, 15))

    def test_presets(self):
        presets = profiles.presets()
        self.assertGreaterEqual(len(presets), 3)
        for preset in presets:
            self.assertIn("mm", profiles.profile_summary(preset))


class DemoStateTests(unittest.TestCase):
    def test_demo_state(self):
        backend = demo.DemoBackend()
        state = state_mod.load_basic(backend)
        self.assertTrue(state.connected)
        self.assertEqual(len(state.actuation), 75)
        self.assertEqual(len(state.rapid_trigger), 75)
        self.assertEqual(state.light.effect, 6)
        self.assertEqual(state.features.nkro, 1)
        keymap_state = state_mod.load_keymap(backend, state)
        self.assertEqual(len(keymap_state.keymap or b""), 600)
        self.assertEqual(keymap_state.keycode_at(0, 0, 0), 0x29)

    def test_lighting_effects(self):
        self.assertEqual(lighting.effect_name(0), "Off")
        self.assertEqual(lighting.effect_name(6), "Breathing")
        self.assertEqual(lighting.effective_color(0, 0, 0), (255, 255, 255))
        self.assertLess(lighting.heat_color(0)[2], lighting.heat_color(1)[0] + 1)


if __name__ == "__main__":
    unittest.main()
