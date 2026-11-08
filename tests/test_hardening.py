import unittest

from madlions_control import boards
from madlions_control.device import MadlionsDevice
from madlions_control.transport import HidInfo, ProtocolError


class ReplyTransport:
    """A transport whose bulk replies can be deliberately broken."""

    def __init__(self, mode: str = "short") -> None:
        self.mode = mode
        self.writes = []

    def close(self) -> None:
        pass

    def request(self, report, *, match=None, timeout=None, attempts=1, drain=True):
        self.writes.append(bytes(report))
        reply = self._reply(report)
        if match is not None and not match(reply):
            raise ProtocolError("unexpected reply")
        return reply

    def _reply(self, report: bytes) -> bytes:
        cmd = report[0]
        if cmd == 0x01:
            return bytes([0x01, 0, 9]) + bytes(29)
        if cmd == 0x02 and report[1] == 0x96:
            sub = report[2]
            if self.mode == "short-dks" and sub == 0x0F:
                return bytes([0x02, 0x96, sub]) + bytes(3)
            if self.mode == "short-single" and sub in (0x09, 0x0A, 0x1E):
                return bytes([0x02, 0x96, sub]) + bytes(2)
            offset = (report[5] << 8) | report[6]
            count = report[7]
            if self.mode == "wrong-offset":
                offset += 1
            if sub in (0x0D, 0x0E, 0x16, 0x17, 0x1F):
                if self.mode == "empty-header":
                    return bytes(32)
                return bytes([0x02, 0x96, sub, 0, 0,
                              (offset >> 8) & 0xFF, offset & 0xFF, count])
        if cmd == 0x08 and report[1] == 0x45:
            return bytes([0x08, 0x45, report[2], report[3], report[4]])
        if cmd == 0x12:
            offset = (report[1] << 8) | report[2]
            if self.mode == "wrong-offset":
                offset += 1
            return bytes([0x12, (offset >> 8) & 0xFF, offset & 0xFF, report[3]])
        return bytes([cmd]) + bytes(31)


def _device(mode="short"):
    board = boards.DEFAULT_BOARD
    info = HidInfo(
        path="/dev/fake", hidraw="fake", name=board.name, product_name="MAD68",
        product_id=board.product_id, vendor_id=0x373B, serial="",
        descriptor=b"", supported=True, board=board,
    )
    transport = ReplyTransport(mode)
    device = MadlionsDevice(info, transport)
    device._probe()
    return device, transport


class MalformedReplyTests(unittest.TestCase):
    def test_short_actuation_reply_raises(self):
        device, _ = _device()
        with self.assertRaises(ProtocolError):
            device.read_actuation()

    def test_short_rapid_trigger_reply_raises(self):
        device, _ = _device()
        with self.assertRaises(ProtocolError):
            device.read_rapid_trigger()

    def test_short_calibration_reply_raises(self):
        device, _ = _device()
        with self.assertRaises(ProtocolError):
            device.read_calibration_status()

    def test_short_colour_reply_raises(self):
        device, _ = _device()
        with self.assertRaises(ProtocolError):
            device.read_key_colors(0, 0, 3)

    def test_short_telemetry_reply_raises(self):
        device, _ = _device()
        with self.assertRaises(ProtocolError):
            device.read_travel()

    def test_wrong_offset_raises(self):
        device, _ = _device("wrong-offset")
        with self.assertRaises(ProtocolError):
            device.read_actuation()

    def test_empty_buffer_reply_raises(self):
        device, _ = _device()
        with self.assertRaises(ProtocolError):
            device.read_keymap()

    def test_short_dks_reply_raises(self):
        device, _ = _device("short-dks")
        with self.assertRaises(ProtocolError):
            device.read_dks(0)

    def test_short_single_travel_reply_raises(self):
        device, _ = _device("short-single")
        with self.assertRaises(ProtocolError):
            device.read_one_travel(0, 0)

    def test_short_single_adc_reply_raises(self):
        device, _ = _device("short-single")
        with self.assertRaises(ProtocolError):
            device.read_one_adc(0, 0)


if __name__ == "__main__":
    unittest.main()
