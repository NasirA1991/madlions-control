"""Permission flow, discovery and command construction without hardware."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from madlions_control import config, permissions, transport
from madlions_control.device import DeviceNotFound
from madlions_control.worker import DeviceWorker

VALID_DESCRIPTOR = b"\x06\x60\xff\x09\x61\xa1\x01\x95\x20\x75\x08"
OTHER_DESCRIPTOR = b"\x06\x00\xff\x09\x02"


class DiscoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tempdir.cleanup)
        self.temp = Path(self._tempdir.name)
        self.sysfs = self.temp / "sys"
        self.sysfs.mkdir()
        self.patch = mock.patch.object(transport, "SYSFS", self.sysfs)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def add_node(
        self,
        name: str = "hidraw0",
        *,
        vid: str = "373B",
        pid: str = "1058",
        descriptor: bytes = VALID_DESCRIPTOR,
    ) -> Path:
        device = self.sysfs / name / "device"
        device.mkdir(parents=True)
        (device / "uevent").write_text(
            f"HID_ID=0003:0000{vid}:0000{pid}\nHID_NAME=Test keyboard\n",
            encoding="utf-8",
        )
        (device / "report_descriptor").write_bytes(descriptor)
        (device / "idVendor").write_text(vid.lower(), encoding="utf-8")
        (device / "product").write_text("MAD68 HE RGB", encoding="utf-8")
        return device

    def test_known_madlions_with_vendor_collection_is_supported(self):
        self.add_node()
        info = transport.inspect_node("hidraw0")
        self.assertIsNotNone(info)
        assert info is not None
        self.assertTrue(info.supported)
        self.assertEqual(info.usb_id, "373B:1058")
        self.assertEqual(transport.supported_devices(), [info])

    def test_373b_without_vendor_collection_is_not_a_keyboard(self):
        self.add_node(pid="10C0", descriptor=OTHER_DESCRIPTOR)
        info = transport.inspect_node("hidraw0")
        self.assertIsNotNone(info)
        assert info is not None
        self.assertFalse(info.supported)
        self.assertIn("0xFF60", info.reason)
        self.assertEqual(transport.supported_devices(), [])
        with self.assertRaises(transport.UnsupportedDevice):
            transport.find_supported()

    def test_other_vendor_is_rejected(self):
        self.add_node(vid="1234")
        self.assertIsNone(transport.inspect_node("hidraw0"))
        self.assertEqual(transport.discover(), [])

    def test_permission_error_is_permission_denied(self):
        info = transport.HidInfo(
            path="/dev/hidraw-test",
            hidraw="hidraw-test",
            name="Test",
            product_name="MAD68 HE RGB",
            product_id=0x1058,
            vendor_id=0x373B,
            serial="",
            descriptor=VALID_DESCRIPTOR,
        )
        node = transport.HidrawTransport(info)
        with mock.patch.object(transport.os, "open", side_effect=PermissionError):
            with self.assertRaises(transport.PermissionDenied) as caught:
                node.open()
        self.assertIn("Permission denied", str(caught.exception))
        self.assertEqual(node.fd, -1)

    def test_permission_error_updates_worker_state(self):
        worker = DeviceWorker()
        worker._handle_connect_error(transport.PermissionDenied("Permission denied opening /dev/hidraw0"))
        self.assertTrue(worker.state.permission_error)
        self.assertNotIn("No MADLIONS", worker.state.error)

        worker._handle_connect_error(DeviceNotFound("No MADLIONS keyboard was found."))
        self.assertFalse(worker.state.permission_error)


class FlatpakTests(unittest.TestCase):
    def test_flatpak_info_file_is_detected(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch("madlions_control.config.Path.exists", return_value=True):
                self.assertTrue(config.is_flatpak())

    def test_non_flatpak_is_not_detected(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch("madlions_control.config.Path.exists", return_value=False):
                self.assertFalse(config.is_flatpak())


class PermissionCommandTests(unittest.TestCase):
    def test_fix_command_is_an_argument_list_using_the_given_path(self):
        rule = Path("/tmp/madlions-rule-test/71-madlions.rules")
        cmd = permissions.fix_command(rule)
        self.assertIsInstance(cmd, list)
        self.assertEqual(cmd[:4], ["pkexec", "sh", "-c", permissions.FIX_SCRIPT])
        self.assertEqual(cmd[-2:], ["sh", str(rule)])
        self.assertIn("/etc/udev/rules.d/71-madlions.rules", cmd[3])
        self.assertNotIn("/usr/lib/udev", cmd[3])

    def test_stage_rule_uses_a_temp_copy_not_the_packaged_path(self):
        text = "SUBSYSTEM==\"hidraw\", TAG+=\"uaccess\"\n"
        temp_dir, rule = permissions.stage_rule(text)
        self.addCleanup(shutil.rmtree, temp_dir, True)
        self.assertEqual(rule.read_text(encoding="utf-8"), text)
        self.assertEqual(rule.name, transport.RULE_NAME)
        self.assertNotEqual(rule, transport.udev_rule_path())
        self.assertNotEqual(rule.parent, transport.udev_rule_path().parent)


if __name__ == "__main__":
    unittest.main()
