import unittest

from madlions_control import boards
from madlions_control.device import (
    LightInfo,
    MadlionsDevice,
    RapidTrigger,
    WriteBlocked,
)
from madlions_control.transport import HidInfo, ProtocolError


class FakeTransport:
    def __init__(self, version: int = 9) -> None:
        self.version = version
        self.writes: list[bytes] = []
        self.closed = False

    def close(self) -> None:
        self.closed = True

    def request(self, report, *, match=None, timeout=None, attempts=1, drain=True):
        self.writes.append(bytes(report))
        reply = self._reply(report)
        if match is not None and not match(reply):
            raise ProtocolError("unexpected reply")
        return reply

    def _reply(self, report: bytes) -> bytes:
        cmd = report[0]
        if cmd == 0x01:
            return bytes([0x01, self.version >> 8, self.version & 0xFF]) + bytes(29)
        if cmd == 0x02 and report[1] == 0x96:
            sub = report[2]
            if sub == 0x0D:
                offset = (report[5] << 8) | report[6]
                count = report[7]
                data = b"".join((100 + ((offset + i) % 7)).to_bytes(2, "big")
                                for i in range(count))
                return bytes([0x02, 0x96, 0x0D, 0, 0, report[5], report[6], count]) + data + bytes(32)
            if sub == 0x0E:
                offset = (report[5] << 8) | report[6]
                count = report[7]
                data = b"".join(bytes([1, 0, 50, 0, 50]) for i in range(count))
                return bytes([0x02, 0x96, 0x0E, 0, 0, report[5], report[6], count]) + data + bytes(32)
            if sub == 0x0B:
                return bytes([0x02, 0x96, 0x0B, 0, 2, 0, 3]) + bytes(25)
            if sub == 0x11:
                return bytes([0x02, 0x96, 0x11, 0, 1, 0, 0, 1]) + bytes(24)
            if sub == 0x1E:
                return bytes([0x02, 0x96, 0x1E, 1]) + bytes(28)
            if sub == 0x1D:
                return bytes([0x02, 0x96, 0x1D, 1]) + bytes(28)
            if sub == 0x21:
                return bytes([0x02, 0x96, 0x21, 2, 1, 130, 120]) + bytes(25)
            if sub == 0x1F:
                count = report[7]
                return bytes([0x02, 0x96, 0x1F, 0, 0, report[5], report[6], count]) + bytes([1] * count) + bytes(32)
            if sub in (0x16, 0x17):
                count = report[7]
                data = b"".join((250).to_bytes(2, "big") for _ in range(count))
                return bytes([0x02, 0x96, sub, 0, 0, report[5], report[6], count]) + data + bytes(32)
        if cmd == 0x03:
            return bytes([0x03, report[1], report[2]]) + bytes(29)
        if cmd == 0x08 and report[1] == 0x41:
            return bytes([0x08, 0x41, 6, 0, 128, 255, 77, 109, 170]) + bytes(23)
        if cmd == 0x08 and report[1] == 0x45:
            count = report[4]
            data = b"".join(bytes([255, 77, 109]) for _ in range(count))
            return bytes([0x08, 0x45, report[2], report[3], count]) + data + bytes(32)
        if cmd == 0x07:
            return bytes([0x07, report[1]]) + bytes(30)
        if cmd == 0x11 and report[1] == 0x00:
            return bytes([0x11, 4]) + bytes(30)
        if cmd == 0x0C:
            return bytes([0x0C, 16]) + bytes(30)
        if cmd == 0x0D:
            return bytes([0x0D, 0x02, 0x00]) + bytes(29)
        if cmd == 0x12 or cmd == 0x0E:
            size = report[3]
            return bytes([cmd, report[1], report[2], size]) + bytes(28)
        if cmd == 0x04:
            return bytes([0x04, report[1], report[2], report[3], 0, 0x04]) + bytes(26)
        if cmd == 0xFE:
            return bytes([0xFE, 0x0D, 0x01, report[3], 0, 0, 0, 0, 0, 200]) + bytes(22)
        return bytes([cmd]) + bytes(31)


class DeviceProtocolTests(unittest.TestCase):
    def _device(self, version=9, board=None, allow=False):
        board = board or boards.DEFAULT_BOARD
        info = HidInfo(
            path="/dev/fake",
            hidraw="fake",
            name=board.name,
            product_name="MAD68",
            product_id=board.product_id,
            vendor_id=0x373B,
            serial="MAD HE",
            descriptor=b"\x06\x60\xff\x09\x61\x95\x20",
            supported=True,
            board=board,
        )
        transport = FakeTransport(version)
        device = MadlionsDevice(info, transport, allow_unverified=allow)
        device._probe()
        return device, transport

    def test_protocol_and_reads(self):
        device, _transport = self._device()
        self.assertEqual(device.protocol_version, 9)
        self.assertTrue(device.writable)
        actuation = device.read_actuation()
        self.assertEqual(len(actuation), 75)
        self.assertAlmostEqual(actuation[0], 1.00)
        triggers = device.read_rapid_trigger()
        self.assertEqual(len(triggers), 75)
        self.assertTrue(triggers[0].enabled)
        self.assertEqual(device.read_light().effect, 6)
        self.assertEqual(device.read_light().hex, "#ff4d6d")
        self.assertEqual(device.read_features().nkro, 1)
        self.assertEqual(device.read_dead_band().top_mm, 0.02)
        self.assertEqual(device.read_game_mode(), 1)
        self.assertEqual(device.read_box_light().mode, 2)
        self.assertEqual(len(device.read_travel()), 75)
        self.assertEqual(device.read_layer_count(), 4)
        self.assertEqual(device.read_macro_buffer_size(), 512)
        self.assertEqual(len(device.read_keymap()), 600)

    def test_writes_are_framed(self):
        device, transport = self._device()
        device.write_actuation([1.25] * 75)
        reports = [report for report in transport.writes if report[0] == 0x03]
        self.assertTrue(reports)
        self.assertTrue(all(report[1] == 0x96 and report[2] == 0x0D for report in reports))
        device.write_light(device.read_light())
        self.assertTrue(any(report[0] == 0x07 and report[1] == 0x41 for report in transport.writes))
        device.write_features(device.read_features())
        self.assertTrue(any(report[0] == 0x03 and report[2] == 0x11 for report in transport.writes))

    def test_off_light_stages_visible_effect(self):
        device, transport = self._device()
        device.write_light(LightInfo(effect=0, speed=127, r=7, g=30, b=29,
                                     brightness=103))
        reports = [report for report in transport.writes
                   if report[0] == 0x07 and report[1] == 0x41]
        self.assertEqual(len(reports), 2)
        self.assertEqual(reports[0][2], 2)
        self.assertEqual(reports[1][2], 0)
        for report in reports:
            self.assertEqual(report[4], 127)
            self.assertEqual(tuple(report[5:8]), (7, 30, 29))
            self.assertEqual(report[8], 103)

    def test_unverified_board_is_read_only(self):
        unknown = boards.BoardSpec(0x9999, "Unknown", verified=False)
        device, _transport = self._device(board=unknown)
        self.assertFalse(device.writable)
        with self.assertRaises(WriteBlocked):
            device.write_actuation([1.0] * 75)

    def test_protocol_mismatch_is_read_only(self):
        device, _transport = self._device(version=10)
        self.assertFalse(device.writable)
        with self.assertRaises(WriteBlocked):
            device.write_features(device.read_features())


if __name__ == "__main__":
    unittest.main()


class SaveAllTests(unittest.TestCase):
    class _Stub:
        def __init__(self, lighting_error=None):
            self.lighting_error = lighting_error
            self.committed = False
            self.lighting_saved = False

        def commit(self):
            self.committed = True

        def save_lighting(self):
            if self.lighting_error:
                raise RuntimeError(self.lighting_error)
            self.lighting_saved = True

    def test_success_returns_none(self):
        stub = self._Stub()
        self.assertIsNone(MadlionsDevice.save_all(stub))
        self.assertTrue(stub.committed)
        self.assertTrue(stub.lighting_saved)

    def test_lighting_failure_is_reported(self):
        stub = self._Stub("lighting write failed")
        self.assertIn("lighting write failed", MadlionsDevice.save_all(stub))
        self.assertTrue(stub.committed)
