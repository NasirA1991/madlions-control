import unittest

try:
    import gi

    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk  # noqa: E402

    from madlions_control.ui.lighting import LightingPage
    from madlions_control.ui.widgets import LabeledScale

    GTK_AVAILABLE = True
except (ImportError, ValueError):  # GTK is installed only in the UI CI job
    Gtk = None
    LabeledScale = None
    LightingPage = None
    GTK_AVAILABLE = False


@unittest.skipUnless(GTK_AVAILABLE, "GTK 4 is not available")
class LabeledScaleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Gtk.init()

    def test_state_updates_are_silent(self):
        changes = []
        scale = LabeledScale("Travel", 0, 3.4, 0.01, value=1.5, on_change=changes.append)
        scale.set_value(0.5)
        self.assertEqual(changes, [])
        self.assertEqual(scale.scale.get_value(), 0.5)

    def test_explicit_notify_applies_value(self):
        changes = []
        scale = LabeledScale("Travel", 0, 3.4, 0.01, value=1.5, on_change=changes.append)
        scale.set_value(0.5, notify=True)
        self.assertEqual(changes, [0.5])
        self.assertEqual(scale.scale.get_value(), 0.5)


class _FakeDebouncer:
    def __init__(self):
        self.triggers = 0

    def trigger(self):
        self.triggers += 1


@unittest.skipUnless(GTK_AVAILABLE, "GTK 4 is not available")
class SideLightSignalTests(unittest.TestCase):
    def test_programmatic_state_update_is_ignored(self):
        page = type("FakePage", (), {
            "_suppress": True,
            "_side_debounce": _FakeDebouncer(),
        })()
        LightingPage._side_changed(page, None)
        self.assertEqual(page._side_debounce.triggers, 0)

    def test_user_change_triggers_debounce(self):
        page = type("FakePage", (), {
            "_suppress": False,
            "_side_debounce": _FakeDebouncer(),
        })()
        LightingPage._side_changed(page, None)
        self.assertEqual(page._side_debounce.triggers, 1)


if __name__ == "__main__":
    unittest.main()
