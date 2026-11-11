import tempfile
import unittest
from pathlib import Path

from madlions_control import boards
from madlions_control.transport import DeviceBusy, HidInfo, HidrawTransport


class DeviceLockTests(unittest.TestCase):
    def _info(self, path):
        board = boards.DEFAULT_BOARD
        return HidInfo(
            path=str(path), hidraw="fake", name=board.name, product_name="MAD68",
            product_id=board.product_id, vendor_id=0x373B, serial="",
            descriptor=b"", supported=True, board=board,
        )

    def test_second_open_is_rejected_until_first_closes(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "hidraw"
            path.touch()
            first = HidrawTransport(self._info(path))
            second = HidrawTransport(self._info(path))
            third = HidrawTransport(self._info(path))
            first.open()
            with self.assertRaises(DeviceBusy):
                second.open()
            first.close()
            third.open()
            third.close()


if __name__ == "__main__":
    unittest.main()
