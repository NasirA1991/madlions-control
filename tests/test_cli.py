import argparse
import unittest
from types import SimpleNamespace

from madlions_control import cli, demo, state as state_mod
from madlions_control.device import DeviceError


class ParserTests(unittest.TestCase):
    def test_actuation_requires_selector(self):
        with self.assertRaises(SystemExit):
            cli.build_parser().parse_args(["actuation", "0.5"])

    def test_actuation_rejects_nan(self):
        with self.assertRaises(SystemExit):
            cli.build_parser().parse_args(["actuation", "nan", "--all"])

    def test_actuation_rejects_out_of_range(self):
        with self.assertRaises(SystemExit):
            cli.build_parser().parse_args(["actuation", "5", "--all"])

    def test_rt_selector_and_range(self):
        cli.build_parser().parse_args(["rt", "on", "--press", "0.1", "--all"])
        with self.assertRaises(SystemExit):
            cli.build_parser().parse_args(["rt", "on", "--press", "nan", "--all"])
        with self.assertRaises(SystemExit):
            cli.build_parser().parse_args(["rt", "on", "--press", "4", "--all"])

    def test_light_effect_known(self):
        cli.build_parser().parse_args(["light", "--effect", "6"])
        with self.assertRaises(SystemExit):
            cli.build_parser().parse_args(["light", "--effect", "10"])

    def test_feature_conflicts(self):
        with self.assertRaises(SystemExit):
            cli.build_parser().parse_args(["features", "--nkro", "--six-key"])
        with self.assertRaises(SystemExit):
            cli.build_parser().parse_args(["features", "--mac", "--no-mac"])

    def test_reset_tuning_parser(self):
        args = cli.build_parser().parse_args(["reset-tuning"])
        self.assertEqual(args.func, cli.cmd_reset_tuning)
        args = cli.build_parser().parse_args(["reset-tuning", "--save"])
        self.assertTrue(args.save)

    def test_key_parser(self):
        self.assertEqual(cli._parse_key("2,1"), (2, 1))
        with self.assertRaises(argparse.ArgumentTypeError):
            cli._parse_key("2")
        with self.assertRaises(argparse.ArgumentTypeError):
            cli._parse_key("-1,2")


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.backend = demo.DemoBackend()
        self.state = state_mod.load_basic(self.backend)

    def test_invalid_coordinate_rejected(self):
        args = SimpleNamespace(key=[(9, 9)], all=False)
        with self.assertRaises(DeviceError):
            cli._selected(args, self.state)

    def test_empty_matrix_cell_rejected(self):
        args = SimpleNamespace(key=[(2, 12)], all=False)
        with self.assertRaises(DeviceError):
            cli._selected(args, self.state)

    def test_all_returns_physical_keys(self):
        args = SimpleNamespace(key=None, all=True)
        selected = cli._selected(args, self.state)
        self.assertEqual(len(selected), 68)
        self.assertIn((2, 1), selected)


if __name__ == "__main__":
    unittest.main()
