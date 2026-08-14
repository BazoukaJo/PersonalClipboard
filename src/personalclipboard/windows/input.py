"""Windows foreground tracking and synthetic Ctrl+C / Ctrl+V."""

from __future__ import annotations

import ctypes
import os
import time
from ctypes import wintypes

from pynput.keyboard import Controller, Key

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

user32.GetForegroundWindow.restype = wintypes.HWND
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.BringWindowToTop.argtypes = [wintypes.HWND]
user32.BringWindowToTop.restype = wintypes.BOOL
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL
user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL
user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
user32.AttachThreadInput.restype = wintypes.BOOL
user32.AllowSetForegroundWindow.argtypes = [wintypes.DWORD]
user32.AllowSetForegroundWindow.restype = wintypes.BOOL
user32.SetFocus.argtypes = [wintypes.HWND]
user32.SetFocus.restype = wintypes.HWND
user32.GetGUIThreadInfo.argtypes = [wintypes.DWORD, ctypes.c_void_p]
user32.GetGUIThreadInfo.restype = wintypes.BOOL
kernel32.GetCurrentThreadId.restype = wintypes.DWORD

_SW_RESTORE = 9
_ASFW_ANY = 0xFFFFFFFF


class _GUITHREADINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hwndActive", wintypes.HWND),
        ("hwndFocus", wintypes.HWND),
        ("hwndCapture", wintypes.HWND),
        ("hwndMenuOwner", wintypes.HWND),
        ("hwndMoveSize", wintypes.HWND),
        ("hwndCaret", wintypes.HWND),
        ("rcCaret", wintypes.RECT),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.cbSize = ctypes.sizeof(_GUITHREADINFO)


class WindowInput:
    def __init__(self) -> None:
        self._pid = os.getpid()
        self._last_foreign: int | None = None
        self._last_focus: int | None = None
        self._keys = Controller()

    def poll(self) -> None:
        hwnd = int(user32.GetForegroundWindow() or 0)
        if not hwnd or _pid_of(hwnd) == self._pid:
            return
        self._last_foreign = hwnd
        child = _focused_control(hwnd)
        if child and _pid_of(child) != self._pid:
            self._last_focus = child
        else:
            self._last_focus = hwnd

    def focus_last_foreign(self) -> bool:
        hwnd = self._last_foreign
        if not hwnd or not user32.IsWindow(hwnd):
            return False
        child = self._last_focus if self._last_focus and user32.IsWindow(self._last_focus) else 0
        return _steal_foreground(hwnd, extra_focus=child)

    def focus_hwnd(self, hwnd: int) -> bool:
        if not hwnd or not user32.IsWindow(hwnd):
            return False
        return _steal_foreground(hwnd, extra_focus=0)

    def copy(self) -> None:
        self._chord("c")

    def paste(self) -> None:
        self._chord("v")

    def _chord(self, letter: str) -> None:
        keyboard = self._keys
        keyboard.press(Key.ctrl)
        keyboard.press(letter)
        keyboard.release(letter)
        keyboard.release(Key.ctrl)
        time.sleep(0.08)


def _steal_foreground(hwnd: int, *, extra_focus: int) -> bool:
    user32.ShowWindow(hwnd, _SW_RESTORE)
    user32.AllowSetForegroundWindow(_ASFW_ANY)
    current = int(kernel32.GetCurrentThreadId())
    target_tid = _thread_of(hwnd)
    extra_tid = _thread_of(extra_focus) if extra_focus else 0
    foreground = int(user32.GetForegroundWindow() or 0)
    fg_tid = _thread_of(foreground) if foreground else 0
    attached: list[int] = []
    for tid in (fg_tid, target_tid, extra_tid):
        if tid and tid != current and tid not in attached:
            if user32.AttachThreadInput(current, tid, True):
                attached.append(tid)
    user32.BringWindowToTop(hwnd)
    focused = bool(user32.SetForegroundWindow(hwnd))
    if extra_focus:
        user32.SetFocus(extra_focus)
    for tid in attached:
        user32.AttachThreadInput(current, tid, False)
    time.sleep(0.08)
    now = int(user32.GetForegroundWindow() or 0)
    return focused or now == hwnd or (extra_focus != 0 and now == extra_focus)


def _focused_control(hwnd: int) -> int:
    info = _GUITHREADINFO()
    if not user32.GetGUIThreadInfo(_thread_of(hwnd), ctypes.byref(info)):
        return hwnd
    focus = int(info.hwndFocus or 0)
    caret = int(info.hwndCaret or 0)
    return focus or caret or hwnd


def _thread_of(hwnd: int) -> int:
    if not hwnd:
        return 0
    pid = wintypes.DWORD()
    return int(user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid)))


def _pid_of(hwnd: int) -> int:
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return int(pid.value)
