"""Linux hidraw transport and device discovery.

The configuration channel is the 32-byte vendor collection defined by usage
page ``0xFF60`` / usage ``0x61``, with report ID 0.  It is found through sysfs,
not by a fixed interface number, because boards in this family enumerate their
interfaces in different orders.
"""

from __future__ import annotations

import errno
import fcntl
import os
import select
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import boards
from .config import VID, VENDOR_NAME

REPORT_SIZE = 32
VENDOR_USAGE_PAGE = b"\x06\x60\xff"
VENDOR_USAGE = b"\x09\x61"
COLLECTION = b"\xa1\x01"
REPORT_COUNT_32 = b"\x95\x20"
REPORT_SIZE_8 = b"\x75\x08"

SYSFS = Path("/sys/class/hidraw")


class DeviceError(RuntimeError):
    """Base class for device errors that are safe to show to the user."""


class DeviceNotFound(DeviceError):
    pass


class DeviceBusy(DeviceError):
    """Another process already owns the keyboard's configuration channel."""


class PermissionDenied(DeviceError):
    pass


class UnsupportedDevice(DeviceError):
    pass


class ProtocolError(DeviceError):
    pass


@dataclass(frozen=True)
class HidInfo:
    path: str
    hidraw: str
    name: str
    product_name: str
    product_id: int
    vendor_id: int
    serial: str
    descriptor: bytes
    interface: str = ""
    supported: bool = True
    reason: str = ""
    board: boards.BoardSpec = field(default_factory=lambda: boards.DEFAULT_BOARD)

    @property
    def usb_id(self) -> str:
        return f"{self.vendor_id:04X}:{self.product_id:04X}"

    @property
    def title(self) -> str:
        return boards.display_name(self.board, self.product_name)


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""


def _usb_parent(hid_dir: Path) -> Path:
    """Walk up from the hidraw device until the USB device node is reached."""
    for _ in range(6):
        if (hid_dir / "idVendor").is_file():
            return hid_dir
        if hid_dir.parent == hid_dir:
            break
        hid_dir = hid_dir.parent
    return hid_dir


def _parse_hid_id(value: str) -> tuple[int, int]:
    # HID_ID=0003:0000373B:00001058
    try:
        _, vid, pid = value.split(":")
        return int(vid, 16), int(pid, 16)
    except (ValueError, AttributeError):
        return 0, 0


def inspect_node(hidraw: str) -> HidInfo | None:
    sysdev = SYSFS / hidraw
    uevent_path = sysdev / "device" / "uevent"
    uevent: dict[str, str] = {}
    try:
        for line in uevent_path.read_text(encoding="utf-8", errors="replace").splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                uevent[key] = value
    except OSError:
        return None

    vid, pid = _parse_hid_id(uevent.get("HID_ID", ""))
    if vid != VID:
        return None

    try:
        descriptor = (sysdev / "device" / "report_descriptor").read_bytes()
    except OSError:
        descriptor = b""

    usb = _usb_parent(Path(os.path.realpath(sysdev / "device")))
    product_name = _read(usb / "product")
    serial = _read(usb / "serial")
    manufacturer = _read(usb / "manufacturer")
    interface = _read(usb / "bInterfaceNumber") if (usb / "bInterfaceNumber").is_file() else ""
    name = product_name or uevent.get("HID_NAME", "").replace(VENDOR_NAME, "").strip() or hidraw

    board = boards.describe(pid, product_name)
    supported = True
    reason = ""
    if not descriptor:
        supported, reason = False, "the HID report descriptor is unavailable"
    elif VENDOR_USAGE_PAGE not in descriptor or VENDOR_USAGE not in descriptor:
        supported, reason = False, "the 0xFF60 vendor collection was not found"
    elif REPORT_COUNT_32 not in descriptor or REPORT_SIZE_8 not in descriptor:
        supported, reason = False, "the vendor channel does not use 32-byte reports"
    elif b"\x85" in descriptor:
        supported, reason = False, "the vendor channel uses numbered reports"
    elif not usb.is_dir():
        supported, reason = False, "the owning USB device could not be resolved"

    return HidInfo(
        path=f"/dev/{hidraw}",
        hidraw=hidraw,
        name=name,
        product_name=product_name,
        product_id=pid,
        vendor_id=vid,
        serial=serial,
        descriptor=descriptor,
        interface=interface,
        supported=supported,
        reason=reason,
        board=board,
    )


def discover() -> list[HidInfo]:
    """All HID collections from the MADLIONS vendor, supported or not."""
    found: list[HidInfo] = []
    try:
        entries = sorted(SYSFS.iterdir())
    except OSError:
        return found
    for entry in entries:
        if not entry.name.startswith("hidraw"):
            continue
        info = inspect_node(entry.name)
        if info is not None:
            found.append(info)
    found.sort(key=lambda item: (not item.supported, item.product_id, item.path))
    return found


def supported_devices() -> list[HidInfo]:
    """Supported keyboards currently present, in discovery order."""
    return [node for node in discover() if node.supported]


def find_supported() -> HidInfo:
    nodes = discover()
    supported = [node for node in nodes if node.supported]
    if supported:
        return supported[0]
    if nodes:
        node = nodes[0]
        raise UnsupportedDevice(
            f"{node.usb_id} was found ({node.product_name or 'unknown model'}), but "
            f"{node.reason}. This application only supports the 32-byte VIA "
            f"configuration channel."
        )
    if boards.BOOTLOADER_IDS & _bootloader_ids_present():
        raise DeviceNotFound(
            "The keyboard is in bootloader mode. Unplug it and plug it back in "
            "to return to normal operation."
        )
    raise DeviceNotFound("No MADLIONS keyboard was found.")


def _bootloader_ids_present() -> set[int]:
    ids: set[int] = set()
    for entry in SYSFS.glob("hidraw*"):
        try:
            uevent = (entry / "device" / "uevent").read_text(errors="replace")
        except OSError:
            continue
        for line in uevent.splitlines():
            if line.startswith("HID_ID="):
                vid, pid = _parse_hid_id(line.split("=", 1)[1])
                if vid == VID:
                    ids.add(pid)
    return ids


def udev_rule() -> str:
    return (
        "# MADLIONS / FGG keyboards (Shenzhen Yizhita, 373B)\n"
        "# Grants the active desktop user access to the vendor HID collection.\n"
        'SUBSYSTEM=="hidraw", ATTRS{idVendor}=="373b", MODE="0660", TAG+="uaccess"\n'
    )


class HidrawTransport:
    """Blocking-ish request/response transport over one hidraw node."""

    def __init__(self, info: HidInfo, *, timeout: float = 1.0, debug: bool = False,
                 read_only: bool = False) -> None:
        self.info = info
        self.timeout = timeout
        self.debug = debug
        self.read_only = read_only
        self.fd = -1
        self.prefix = b""
        self._auto_prefix = True
        self._last_error: str | None = None

    @property
    def is_open(self) -> bool:
        return self.fd >= 0

    def open(self) -> None:
        if self.fd >= 0:
            return
        flags = os.O_RDONLY if self.read_only else os.O_RDWR
        try:
            self.fd = os.open(self.info.path, flags | os.O_NONBLOCK)
        except PermissionError as exc:
            raise PermissionDenied(
                f"Permission denied opening {self.info.path}. Install the udev "
                f"rule or add your user to the group that owns the node."
            ) from exc
        except FileNotFoundError as exc:
            raise DeviceNotFound(f"{self.info.path} disappeared") from exc
        except OSError as exc:
            raise DeviceError(f"Could not open {self.info.path}: {exc}") from exc
        try:
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            os.close(self.fd)
            self.fd = -1
            raise DeviceBusy(
                f"{self.info.path} is already in use by another process; "
                "close the other Madlions Control or madlionsctl session and retry"
            ) from exc

    def close(self) -> None:
        if self.fd >= 0:
            try:
                os.close(self.fd)
            finally:
                self.fd = -1

    def __enter__(self) -> "HidrawTransport":
        self.open()
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    # -- low level ------------------------------------------------------
    def _write(self, data: bytes) -> None:
        view = memoryview(data)
        deadline = time.monotonic() + self.timeout
        while view:
            try:
                written = os.write(self.fd, view)
                view = view[written:]
            except BlockingIOError:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ProtocolError("timed out writing to the keyboard")
                select.select([], [self.fd], [], remaining)
            except OSError as exc:
                raise ProtocolError(f"write failed: {exc}") from exc

    def read_report(self, timeout: float | None = None) -> bytes | None:
        timeout = self.timeout if timeout is None else timeout
        ready, _, _ = select.select([self.fd], [], [], max(0.0, timeout))
        if not ready:
            return None
        try:
            data = os.read(self.fd, 64)
        except BlockingIOError:
            return None
        except OSError as exc:
            raise ProtocolError(f"read failed: {exc}") from exc
        if not data:
            raise ProtocolError("the keyboard disconnected")
        if self.debug:
            print("<<", data.hex(" "))
        return bytes(data)

    def drain(self) -> None:
        """Discard queued input reports.  Telemetry can otherwise satisfy a read."""
        if self.fd < 0:
            return
        while True:
            ready, _, _ = select.select([self.fd], [], [], 0)
            if not ready:
                return
            try:
                if not os.read(self.fd, 64):
                    return
            except (BlockingIOError, OSError):
                return

    def send(self, report: bytes) -> None:
        if len(report) > REPORT_SIZE:
            raise ValueError("a report is at most 32 bytes")
        payload = bytes(report) + bytes(REPORT_SIZE - len(report))
        self._write(self.prefix + payload)
        if self.debug:
            print(">>", payload.hex(" "))

    def request(
        self,
        report: bytes,
        *,
        match=None,
        timeout: float | None = None,
        drain: bool = True,
        attempts: int = 1,
    ) -> bytes:
        """Send one report and wait for its reply.

        ``match`` receives the raw reply and returns True for the answer we want.
        Unrelated unsolicited reports are ignored.
        """
        timeout = self.timeout if timeout is None else timeout
        if drain:
            self.drain()
        last_error: str | None = None
        for attempt in range(attempts):
            self.send(report)
            deadline = time.monotonic() + timeout
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                reply = self.read_report(remaining)
                if reply is None:
                    break
                if match is None or match(reply):
                    return reply
            last_error = f"no reply to command {report[0]:#04x}"
            if self._auto_prefix and attempts > 1 and attempt == 0:
                # Some firmware builds prepend a report-ID byte even for report 0.
                # Only the initial read probe opts into this retry; re-sending a
                # write would be unsafe, so writes never use attempts > 1.
                self.prefix = b"\x00" if not self.prefix else b""
                continue
        raise ProtocolError(last_error or "the keyboard did not answer")


def open_device() -> tuple[HidInfo, HidrawTransport]:
    info = find_supported()
    transport = HidrawTransport(info)
    transport.open()
    return info, transport
