import json
import math
import tempfile
import unittest
from pathlib import Path

from madlions_control import demo, profiles
from madlions_control import state as state_mod


class ProfileValidationTests(unittest.TestCase):
    def _base(self):
        return {
            "profile_version": 3,
            "name": "Valid",
            "actuation": {"default_mm": 1.5, "overrides": {}},
            "rapid_trigger": {"default": {"enabled": False, "press_mm": 0.5,
                                          "release_mm": 0.5}, "overrides": {}},
        }

    def test_rejects_unknown_version(self):
        data = self._base()
        data["profile_version"] = 99
        with self.assertRaises(profiles.ProfileValidationError):
            profiles.Profile.from_json(data)

    def test_rejects_nan_and_infinity(self):
        for value in (float("nan"), float("inf")):
            data = self._base()
            data["actuation"]["default_mm"] = value
            with self.assertRaises(profiles.ProfileValidationError):
                profiles.Profile.from_json(data)

    def test_rejects_out_of_range(self):
        cases = [
            ("actuation", "default_mm", -1),
            ("light", None, {"effect": 0, "brightness": 999}),
            ("dead_band", None, {"top_mm": 3}),
        ]
        for section, key, value in cases:
            data = self._base()
            if key is None:
                data[section] = value
            else:
                data[section][key] = value
            with self.assertRaises(profiles.ProfileValidationError):
                profiles.Profile.from_json(data)

    def test_rejects_bad_keymap(self):
        data = self._base()
        data["keymap_hex"] = "xyz"
        with self.assertRaises(profiles.ProfileValidationError):
            profiles.Profile.from_json(data)

    def test_rejects_bad_coordinates(self):
        data = self._base()
        data["actuation"]["overrides"] = {"9,99": 1.5}
        with self.assertRaises(profiles.ProfileValidationError):
            profiles.Profile.from_json(data)

    def test_size_limit(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "huge.json"
            path.write_text("{" + '"x": 1,' * 100000 + "}", encoding="utf-8")
            with self.assertRaises(profiles.ProfileValidationError):
                profiles.Profile.load(path)

    def test_atomic_save_and_collision(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            first = profiles.Profile(name="a/b")
            second = profiles.Profile(name="a?b")
            p1 = first.save(directory)
            p2 = second.save(directory)
            self.assertNotEqual(p1, p2)
            self.assertEqual(profiles.Profile.load(p1).name, "a/b")
            self.assertEqual(profiles.Profile.load(p2).name, "a?b")
            self.assertFalse(any(path.name.endswith(".tmp") for path in directory.iterdir()))


class FullBackupTests(unittest.TestCase):
    def test_capture_full_includes_sections(self):
        backend = demo.DemoBackend()
        state = state_mod.load_basic(backend)
        state = state_mod.load_colors(backend, state)
        state = state_mod.load_keymap(backend, state)
        state = state_mod.load_macros(backend, state)
        state = state_mod.load_advanced(backend, state)
        profile = profiles.Profile.capture(state, "Full", full=True)
        self.assertTrue(profile.is_full)
        self.assertIn("keymap", profile.captured_sections)
        self.assertIn("macros", profile.captured_sections)
        self.assertIn("advanced_keys", profile.captured_sections)
        data = profile.to_json()
        again = profiles.Profile.from_json(data)
        self.assertEqual(again.kind, "full")
        self.assertTrue(again.keymap_hex)
        self.assertTrue(again.macros_hex)

    def test_tuning_capture_omits_persistent_sections(self):
        backend = demo.DemoBackend()
        state = state_mod.load_basic(backend)
        state = state_mod.load_keymap(backend, state)
        profile = profiles.Profile.capture(state, "Tuning")
        self.assertFalse(profile.is_full)
        self.assertIsNone(profile.keymap_hex)
        self.assertNotIn("keymap", profile.captured_sections)

    def test_apply_full_to_demo(self):
        backend = demo.DemoBackend()
        state = state_mod.load_basic(backend)
        state = state_mod.load_colors(backend, state)
        state = state_mod.load_keymap(backend, state)
        state = state_mod.load_macros(backend, state)
        state = state_mod.load_advanced(backend, state)
        profile = profiles.Profile.capture(state, "Full", full=True)
        actions = profile.apply(
            backend, state, include_keymap=True, include_macros=True,
            include_advanced=True,
        )
        self.assertIn("keymap (persistent)", actions)
        self.assertIn("macros (persistent)", actions)

    def test_auto_backup_names_are_unique(self):
        backend = demo.DemoBackend()
        state = state_mod.load_basic(backend)
        with tempfile.TemporaryDirectory() as folder:
            first = profiles.auto_backup(state, Path(folder))
            second = profiles.auto_backup(state, Path(folder))
            self.assertNotEqual(first, second)


class ProfileRoundTripTests(unittest.TestCase):
    def test_old_profile_loads(self):
        data = {
            "profile_version": 1,
            "name": "Old",
            "actuation": {"default_mm": 1.0},
            "rapid_trigger": {"default": {"enabled": True, "press_mm": 0.1,
                                          "release_mm": 0.2}},
        }
        profile = profiles.Profile.from_json(data)
        self.assertEqual(profile.name, "Old")
        self.assertTrue(profile.rt_default.enabled)
        self.assertIn("actuation", profile.captured_sections)


if __name__ == "__main__":
    unittest.main()


class _BadKeymapRead(demo.DemoBackend):
    def read_keymap(self) -> bytes:
        return b"\x00" * self.board.keymap_size


class _BadMacroRead(demo.DemoBackend):
    def read_macros(self) -> bytes:
        return b"\x00" * (len(self._macros) + 1)


class PersistentReadbackTests(unittest.TestCase):
    def _full_profile(self):
        backend = demo.DemoBackend()
        state = state_mod.load_basic(backend)
        state = state_mod.load_colors(backend, state)
        state = state_mod.load_keymap(backend, state)
        state = state_mod.load_macros(backend, state)
        state = state_mod.load_advanced(backend, state)
        return profiles.Profile.capture(state, "Full", full=True), state

    def test_keymap_readback_mismatch_raises(self):
        profile, state = self._full_profile()
        backend = _BadKeymapRead()
        with self.assertRaises(profiles.ProfileValidationError):
            profile.apply(backend, state, include_keymap=True)

    def test_macro_readback_mismatch_raises(self):
        profile, state = self._full_profile()
        backend = _BadMacroRead()
        with self.assertRaises(profiles.ProfileValidationError):
            profile.apply(backend, state, include_macros=True)
