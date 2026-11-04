import unittest

from madlions_control import boards, shortcuts
from madlions_control.state import KeyboardState


class ShortcutTests(unittest.TestCase):
    def _state(self):
        board = boards.DEFAULT_BOARD
        state = KeyboardState(keymap=bytes(board.keymap_size))
        state = state.with_keycode(0, 4, 10, 0x5221)  # Fn = MO(1)
        state = state.with_keycode(1, 1, 0, 0x7820)   # Fn+Tab
        state = state.with_keycode(1, 1, 2, 0x7821)   # Fn+W
        state = state.with_keycode(1, 1, 1, 0x7827)   # Fn+Q
        state = state.with_keycode(1, 0, 0, 0x35)     # Fn+Esc
        state = state.with_keycode(1, 0, 1, 0x3A)     # Fn+1
        state = state.with_keycode(1, 4, 1, 0x7E03)   # Fn+Win
        return state

    def test_builds_from_layer_one(self):
        items = shortcuts.build_shortcuts(self._state())
        keys = {item.keys: item for item in items}
        self.assertIn("Fn + Tab", keys)
        self.assertEqual(keys["Fn + Tab"].action, "Toggle RGB lighting")
        self.assertEqual(keys["Fn + W"].action, "Next lighting effect")
        self.assertEqual(keys["Fn + Q"].action, "Increase brightness")
        self.assertEqual(keys["Fn + 1"].action, "F1")
        self.assertEqual(keys["Fn + Esc"].action, "` / ~")
        self.assertEqual(keys["Fn + Win"].category, "Other")

    def test_no_keymap_returns_empty(self):
        self.assertEqual(shortcuts.build_shortcuts(KeyboardState()), [])


if __name__ == "__main__":
    unittest.main()
