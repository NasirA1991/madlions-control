import unittest

from madlions_control.settings import (
    MAX_WINDOW_HEIGHT,
    MAX_WINDOW_WIDTH,
    MIN_WINDOW_HEIGHT,
    MIN_WINDOW_WIDTH,
    AppSettings,
)


class SettingsValidationTests(unittest.TestCase):
    def test_bad_types_fall_back_to_defaults(self):
        settings = AppSettings.from_json({
            "window_width": "not-a-number",
            "window_height": True,
            "last_page": ["x"],
            "theme": "purple",
        })
        self.assertEqual(settings.window_width, 1180)
        self.assertEqual(settings.window_height, 780)
        self.assertEqual(settings.last_page, "overview")
        self.assertEqual(settings.theme, "system")

    def test_sizes_are_clamped(self):
        settings = AppSettings.from_json({
            "window_width": 10**9,
            "window_height": -2,
        })
        self.assertEqual(settings.window_width, MAX_WINDOW_WIDTH)
        self.assertEqual(settings.window_height, MIN_WINDOW_HEIGHT)
        self.assertGreaterEqual(settings.window_width, MIN_WINDOW_WIDTH)
        self.assertLessEqual(settings.window_width, MAX_WINDOW_WIDTH)
        self.assertGreaterEqual(settings.window_height, MIN_WINDOW_HEIGHT)
        self.assertLessEqual(settings.window_height, MAX_WINDOW_HEIGHT)

    def test_valid_page_and_theme_survive(self):
        settings = AppSettings.from_json({"last_page": "test", "theme": "dark"})
        self.assertEqual(settings.last_page, "test")
        self.assertEqual(settings.theme, "dark")

    def test_non_object_root_is_rejected(self):
        self.assertEqual(AppSettings.from_json(["not", "an", "object"]), AppSettings())


if __name__ == "__main__":
    unittest.main()
