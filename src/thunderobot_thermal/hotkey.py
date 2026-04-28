from __future__ import annotations

import ctypes
import threading
from ctypes import wintypes


MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_NOREPEAT = 0x4000
VK_0 = 0x30
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012

DEFAULT_HOTKEY_ID = 0x5448
DEFAULT_HOTKEY_MODIFIERS = MOD_CONTROL | MOD_ALT | MOD_SHIFT | MOD_NOREPEAT
DEFAULT_HOTKEY_VK = VK_0
DEFAULT_HOTKEY_TEXT = "Ctrl+Alt+Shift+0"


class ManualFullHotkeyState:
    def __init__(self, enabled: bool = False) -> None:
        self._enabled = enabled
        self._lock = threading.Lock()

    def is_enabled(self) -> bool:
        with self._lock:
            return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        with self._lock:
            self._enabled = enabled

    def toggle(self) -> bool:
        with self._lock:
            self._enabled = not self._enabled
            return self._enabled


class GlobalHotkeyListener:
    def __init__(
        self,
        state: ManualFullHotkeyState,
        hotkey_id: int = DEFAULT_HOTKEY_ID,
        modifiers: int = DEFAULT_HOTKEY_MODIFIERS,
        virtual_key: int = DEFAULT_HOTKEY_VK,
    ) -> None:
        self._state = state
        self._hotkey_id = hotkey_id
        self._modifiers = modifiers
        self._virtual_key = virtual_key
        self._thread: threading.Thread | None = None
        self._thread_id = 0
        self._started = threading.Event()
        self._stopped = threading.Event()
        self.error: str | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="thermal-hotkey", daemon=True)
        self._thread.start()
        self._started.wait(timeout=2)

    def stop(self) -> None:
        if self._thread is None or self._thread_id == 0:
            return
        ctypes.windll.user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        self._stopped.wait(timeout=2)

    def _run(self) -> None:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self._thread_id = kernel32.GetCurrentThreadId()

        registered = bool(user32.RegisterHotKey(None, self._hotkey_id, self._modifiers, self._virtual_key))
        if not registered:
            self.error = ctypes.WinError().strerror
            self._started.set()
            self._stopped.set()
            return

        self._started.set()
        message = wintypes.MSG()
        try:
            while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
                if message.message == WM_HOTKEY and message.wParam == self._hotkey_id:
                    enabled = self._state.toggle()
                    print(
                        f"{DEFAULT_HOTKEY_TEXT} -> {'手动满转开启' if enabled else '手动满转关闭'}",
                        flush=True,
                    )
        finally:
            user32.UnregisterHotKey(None, self._hotkey_id)
            self._stopped.set()
