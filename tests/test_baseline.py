import unittest

from madlions_control import baseline, boards, demo, state as state_mod


class BaselineTests(unittest.TestCase):
    def test_verified_board_has_baseline(self):
        spec = baseline.require(boards.DEFAULT_BOARD)
        self.assertEqual(spec.product_id, 0x1058)
        self.assertIn("MAD68", spec.label)
        self.assertTrue(any("Actuation" in line for line in spec.preview_lines()))

    def test_other_board_has_no_baseline(self):
        self.assertIsNone(baseline.for_board(boards.lookup(0x1053)))
        with self.assertRaises(baseline.BaselineError):
            baseline.require(boards.lookup(0x1053))

    def test_apply_only_touches_volatile_tuning(self):
        backend = demo.DemoBackend()
        before = state_mod.load_basic(backend)
        before = state_mod.load_colors(backend, before)
        before = state_mod.load_keymap(backend, before)
        before = state_mod.load_macros(backend, before)
        before = state_mod.load_advanced(backend, before)

        spec = baseline.require(backend.board)
        actions = spec.apply(backend, backend.board)
        self.assertTrue(actions)

        after = state_mod.load_basic(backend)
        self.assertTrue(all(abs(v - 1.50) < 0.011 for v in after.actuation))
        self.assertTrue(all(rt.enabled for rt in after.rapid_trigger))
        self.assertTrue(all(abs(rt.press_mm - 0.50) < 0.011 for rt in after.rapid_trigger))
        self.assertEqual(after.light.effect, 0)
        self.assertEqual(after.light.brightness, 103)
        self.assertEqual(after.features, spec.features)
        self.assertAlmostEqual(after.dead_band.top_mm, 0.20, places=2)
        self.assertAlmostEqual(after.dead_band.bottom_mm, 0.20, places=2)
        self.assertEqual(after.game_mode, 0)
        self.assertEqual(after.bottom_optimize, 1)

        after = state_mod.load_colors(backend, after)
        after = state_mod.load_keymap(backend, after)
        after = state_mod.load_macros(backend, after)
        after = state_mod.load_advanced(backend, after)
        self.assertEqual(after.colors, before.colors)
        self.assertEqual(after.keymap, before.keymap)
        self.assertEqual(after.macros, before.macros)
        self.assertEqual(after.advanced_keys, before.advanced_keys)
        self.assertEqual(after.tap_dance, before.tap_dance)
        self.assertEqual(after.dks, before.dks)


if __name__ == "__main__":
    unittest.main()
