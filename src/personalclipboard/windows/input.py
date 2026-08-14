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
kernel32.GetCurrentThreadId.restype = wintypes.DWORD

_SW_RESTORE = 9
_ASFW_ANY = 0xFFFFFFFF


class WindowInput:
    def __init__(self) -> None:
        self._pid = os.getpid()
        self._last_foreign: int | None = None
        self._keys = Controller()

    def poll(self) -> None:
        hwnd = int(user32.GetForegroundWindow() or 0)
        if hwnd and _pid_of(hwnd) != self._pid:
            self._last_foreign = hwnd

    def focus_last_foreign(self) -> bool:
        hwnd = self._last_foreign
        if not hwnd or not user32.IsWindow(hwnd):
            return False
        user32.ShowWindow(hwnd, _SW_RESTORE)
        user32.AllowSetForegroundWindow(_ASFW_ANY)
        current = int(kernel32.GetCurrentThreadId())
        target_tid = _thread_of(hwnd)
        foreground = int(user32.GetForegroundWindow() or 0)
        fg_tid = _thread_of(foreground) if foreground else 0
        attached_fg = False
        attached_target = False
        if fg_tid and fg_tid != current:
            attached_fg = bool(user32.AttachThreadInput(current, fg_tid, True))
        if target_tid and target_tid != current:
            attached_target = bool(user32.AttachThreadInput(current, target_tid, True))
        user32.BringWindowToTop(hwnd)
        focused = bool(user32.SetForegroundWindow(hwnd))
        if attached_target:
            user32.AttachThreadInput(current, target_tid, False)
        if attached_fg:
            user32.AttachThreadInput(current, fg_tid, False)
        time.sleep(0.12)
        return focused or int(user32.GetForegroundWindow() or 0) == hwnd

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


def _thread_of(hwnd: int) -> int:
    pid = wintypes.DWORD()
    return int(user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid)))


def _pid_of(hwnd: int) -> int:
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return int(pid.value)
