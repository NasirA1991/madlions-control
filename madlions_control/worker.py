"""Background device session.

All HID traffic happens on one thread.  The UI submits callables, receives
their results through a main-loop callback, and can subscribe to a live travel
stream for the Test page.
"""

from __future__ import annotations

import queue
import threading
import time
from dataclasses import replace
from typing import Any, Callable

from . import config, profiles, state as state_mod
from .demo import DemoBackend
from .device import DeviceError, MadlionsDevice, PermissionDenied, WriteBlocked
from .state import KeyboardState

Post = Callable[[Callable[..., Any], tuple], Any]


class DeviceWorker:
    def __init__(
        self,
        *,
        demo: bool = False,
        post: Post | None = None,
        on_event: Callable[[str, Any], None] | None = None,
    ) -> None:
        self.demo = demo
        self._post = post or (lambda fn, args: fn(*args))
        self._on_event = on_event or (lambda _name, _payload: None)
        self._queue: queue.Queue = queue.Queue()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._device: Any = None
        self._state = KeyboardState()
        self._stream_cb: Callable[[list[float]], None] | None = None
        self._stream_stop = threading.Event()
        self._next_stream = 0.0
        self._stream_hz = 60.0
        self._last_connect_error = ""
        self._next_connect = 0.0
        self._lock = threading.Lock()

    # -- lifecycle ---------------------------------------------------------
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="madlions-device", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._stream_stop.set()
        self._queue.put(None)
        if self._thread is not None:
            self._thread.join(timeout=3)
            self._thread = None
        self._disconnect()

    @property
    def state(self) -> KeyboardState:
        with self._lock:
            return self._state

    def _set_state(self, value: KeyboardState) -> None:
        with self._lock:
            self._state = value

    def _emit(self, name: str, payload: Any = None) -> None:
        self._post(self._on_event, (name, payload))

    # -- connection --------------------------------------------------------
    def _connect(self) -> Any:
        if self.demo:
            backend = DemoBackend()
            self._device = backend
            self._set_state(state_mod.load_basic(backend))
            self._emit("connected", self.state)
            self._emit("ready", self.state)
            return backend
        device = MadlionsDevice.open()
        self._device = device
        self._emit("connecting", device.device_info())
        loaded = state_mod.load_basic(device)
        self._set_state(loaded)
        self._emit("connected", loaded)
        self._emit("ready", loaded)
        return device

    def _disconnect(self) -> None:
        device, self._device = self._device, None
        if device is not None:
            try:
                device.close()
            except Exception:
                pass
        self._stream_stop.set()
        self._stream_cb = None
        if self._state.connected:
            info = self._state.info
            disconnected = replace(
                self._state,
                connected=False,
                info=info,
                error="Keyboard disconnected",
            )
            self._set_state(disconnected)
            self._emit("disconnected", disconnected)

    def _handle_connect_error(self, exc: Exception) -> None:
        message = str(exc)
        permission = isinstance(exc, PermissionDenied)
        error_state = replace(
            self._state,
            connected=False,
            loading=False,
            error=message,
            permission_error=permission,
        )
        self._set_state(error_state)
        if message != self._last_connect_error:
            self._last_connect_error = message
            self._emit("connect_error", error_state)
        self._next_connect = time.monotonic() + (4.0 if permission else 2.0)

    # -- thread loop -------------------------------------------------------
    def _run(self) -> None:
        while not self._stop.is_set():
            if self._device is None:
                if time.monotonic() < self._next_connect:
                    time.sleep(0.15)
                    continue
                try:
                    self._connect()
                    self._last_connect_error = ""
                except Exception as exc:  # noqa: BLE001 - surfaced in the UI
                    self._handle_connect_error(exc)
                    continue

            # Live telemetry if the Test page is subscribed.
            if self._stream_cb and not self._stream_stop.is_set():
                now = time.monotonic()
                if now >= self._next_stream:
                    self._next_stream = now + 1.0 / self._stream_hz
                    try:
                        frame = self._device.read_travel()
                        self._post(self._stream_cb, (frame,))
                    except Exception as exc:  # noqa: BLE001
                        self._stream_stop.set()
                        self._emit("stream_error", str(exc))

            try:
                job = self._queue.get(timeout=0.012)
            except queue.Empty:
                continue
            if job is None:
                break
            fn, callback, error_back, description = job
            try:
                result = fn(self._device)
            except WriteBlocked as exc:
                self._post(error_back or self._noop, (exc,))
                continue
            except (DeviceError, OSError, ValueError) as exc:
                self._post(error_back or self._noop, (exc,))
                message = str(exc).lower()
                if any(word in message for word in ("disconnect", "read failed", "write failed", "no reply", "timed out")):
                    self._disconnect()
                continue
            except Exception as exc:  # noqa: BLE001 - never kill the worker
                self._post(error_back or self._noop, (exc,))
                continue
            finally:
                self._queue.task_done()
            if callback is not None:
                self._post(callback, (result,))

    @staticmethod
    def _noop(*_args: Any) -> None:
        pass

    # -- public API --------------------------------------------------------
    def submit(
        self,
        fn: Callable[[Any], Any],
        *,
        callback: Callable[[Any], None] | None = None,
        error: Callable[[Exception], None] | None = None,
        description: str = "",
    ) -> None:
        if self._stop.is_set():
            return
        self._queue.put((fn, callback, error, description))

    def refresh(self, callback: Callable[[KeyboardState], None] | None = None) -> None:
        def load(device: Any) -> KeyboardState:
            loaded = state_mod.load_basic(device)
            self._set_state(loaded)
            return loaded

        def done(loaded: KeyboardState) -> None:
            self._emit("ready", loaded)
            if callback:
                callback(loaded)

        self.submit(load, callback=done, description="refresh")

    def refresh_colors(self, callback=None) -> None:
        def load(device: Any) -> KeyboardState:
            loaded = state_mod.load_colors(device, self.state)
            self._set_state(loaded)
            return loaded

        self.submit(load, callback=callback or (lambda _s: None), description="colours")

    def refresh_keymap(self, callback=None) -> None:
        def load(device: Any) -> KeyboardState:
            loaded = state_mod.load_keymap(device, self.state)
            self._set_state(loaded)
            return loaded

        self.submit(load, callback=callback or (lambda _s: None), description="keymap")

    def refresh_macros(self, callback=None) -> None:
        def load(device: Any) -> KeyboardState:
            loaded = state_mod.load_macros(device, self.state)
            self._set_state(loaded)
            return loaded

        self.submit(load, callback=callback or (lambda _s: None), description="macros")

    def refresh_advanced(self, callback=None) -> None:
        def load(device: Any) -> KeyboardState:
            loaded = state_mod.load_advanced(device, self.state)
            self._set_state(loaded)
            return loaded

        self.submit(load, callback=callback or (lambda _s: None), description="advanced keys")

    def start_stream(self, callback: Callable[[list[float]], None]) -> None:
        self._stream_cb = callback
        self._stream_stop.clear()
        self._next_stream = 0.0
        self._stream_hz = 60.0

    def stop_stream(self) -> None:
        self._stream_stop.set()
        self._stream_cb = None
