"""Small Win32 boundary. Never hooks other applications or captures keystrokes."""

import ctypes
import sys
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter, QTimer

HOTKEYS = {
    "toggle_tracing": (0x77, "Ctrl+Alt+F8"),
    "toggle_visibility": (0x78, "Ctrl+Alt+F9"),
    "toggle_panel": (0x79, "Ctrl+Alt+F10"),
}


class WindowsAPI:
    WS_EX_TRANSPARENT = 0x00000020
    WS_EX_LAYERED = 0x00080000
    WS_EX_NOACTIVATE = 0x08000000

    def __init__(self):
        if sys.platform != "win32":
            raise OSError("Win32 доступен только на Windows.")
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        suffix = "PtrW" if ctypes.sizeof(ctypes.c_void_p) == 8 else "W"
        self._get = getattr(self.user32, "GetWindowLong" + suffix)
        self._get.argtypes = [wintypes.HWND, ctypes.c_int]
        self._get.restype = ctypes.c_ssize_t
        self._set = getattr(self.user32, "SetWindowLong" + suffix)
        self._set.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
        self._set.restype = ctypes.c_ssize_t
        self.user32.SetWindowPos.argtypes = [
            wintypes.HWND,
            wintypes.HWND,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.UINT,
        ]
        self.user32.SetWindowPos.restype = wintypes.BOOL
        self.user32.RegisterHotKey.argtypes = [
            wintypes.HWND,
            ctypes.c_int,
            wintypes.UINT,
            wintypes.UINT,
        ]
        self.user32.RegisterHotKey.restype = wintypes.BOOL
        self.user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
        self.user32.UnregisterHotKey.restype = wintypes.BOOL

    def get_style(self, hwnd: int) -> int:
        ctypes.set_last_error(0)
        value = self._get(hwnd, -20)  # GWL_EXSTYLE
        if not value and ctypes.get_last_error():
            raise ctypes.WinError(ctypes.get_last_error())
        return value

    def set_click_through(self, hwnd: int, enabled: bool):
        old = self.get_style(hwnd)
        bits = self.WS_EX_TRANSPARENT | self.WS_EX_NOACTIVATE
        new = (old | bits | self.WS_EX_LAYERED) if enabled else (old & ~bits)
        ctypes.set_last_error(0)
        previous = self._set(hwnd, -20, new)
        if not previous and ctypes.get_last_error():
            raise ctypes.WinError(ctypes.get_last_error())
        # Keep the window above ordinary windows, without taking focus from the canvas.
        try:
            if not self.user32.SetWindowPos(hwnd, wintypes.HWND(-1), 0, 0, 0, 0, 0x0033):
                raise ctypes.WinError(ctypes.get_last_error())
            if bool(self.get_style(hwnd) & self.WS_EX_TRANSPARENT) != enabled:
                raise OSError("Windows не применил режим сквозных кликов.")
        except OSError:
            self._set(hwnd, -20, old)
            raise


class HotkeyManager(QAbstractNativeEventFilter):
    """Thread-bound WM_HOTKEY registrations, explicitly released on shutdown."""

    def __init__(self, app, callbacks: dict, api: WindowsAPI, id_base: int = 0x5100):
        super().__init__()
        self.app = app
        self.callbacks = callbacks
        self.api = api
        self.id_base = id_base
        self.registered: dict[str, int] = {}
        self.errors: list[str] = []
        self.started = False

    def start(self):
        if self.started:
            return
        self.started = True
        self.app.installNativeEventFilter(self)
        for offset, name in enumerate(self.callbacks):
            key, label = HOTKEYS[name]
            key_id = self.id_base + offset
            if self.api.user32.RegisterHotKey(None, key_id, 0x4003, key):
                self.registered[name] = key_id
            else:
                self.errors.append(f"{label} недоступна (возможно, занята другой программой).")

    def nativeEventFilter(self, event_type, message):
        if bytes(event_type) in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == 0x0312:  # WM_HOTKEY
                for name, key_id in self.registered.items():
                    if msg.wParam == key_id:
                        QTimer.singleShot(0, self.callbacks[name])
                        return True, 0
        return False, 0

    def close(self):
        if not self.started:
            return
        for key_id in self.registered.values():
            self.api.user32.UnregisterHotKey(None, key_id)
        self.registered.clear()
        self.app.removeNativeEventFilter(self)
        self.started = False
