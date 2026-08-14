"""Windows 11 system resize: thick frame + WM_NCHITTEST hit codes."""

from __future__ import annotations

import sys

_EDGE = 8
HTLEFT = 10
HTRIGHT = 11
HTTOP = 12
HTTOPLEFT = 13
HTTOPRIGHT = 14
HTBOTTOM = 15
HTBOTTOMLEFT = 16
HTBOTTOMRIGHT = 17

_GWL_STYLE = -16
_WS_THICKFRAME = 0x00040000
_SWP_NOSIZE = 0x0001
_SWP_NOMOVE = 0x0002
_SWP_NOZORDER = 0x0004
_SWP_FRAMECHANGED = 0x0020


_HITS = {
    (1, 0, 1, 0): HTTOPLEFT,
    (0, 1, 1, 0): HTTOPRIGHT,
    (1, 0, 0, 1): HTBOTTOMLEFT,
    (0, 1, 0, 1): HTBOTTOMRIGHT,
    (1, 0, 0, 0): HTLEFT,
    (0, 1, 0, 0): HTRIGHT,
    (0, 0, 1, 0): HTTOP,
    (0, 0, 0, 1): HTBOTTOM,
}


def resize_hit(x: int, y: int, width: int, height: int, margin: int = _EDGE) -> int | None:
    """Return a WM_NCHITTEST code for a border, or None for the client area."""
    if width < 1 or height < 1:
        return None
    left = int(x <= margin)
    right = int(x >= width - margin)
    top = int(y <= margin)
    bottom = int(y >= height - margin)
    return _HITS.get((left, right, top, bottom))


def enable_thick_frame(hwnd: int) -> None:
    """Add WS_THICKFRAME so Windows 11 can run its resize/snap pipeline."""
    if sys.platform != "win32" or hwnd == 0:
        return
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
    user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
    user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
    style = int(user32.GetWindowLongPtrW(hwnd, _GWL_STYLE))
    if style & _WS_THICKFRAME:
        return
    user32.SetWindowLongPtrW(hwnd, _GWL_STYLE, style | _WS_THICKFRAME)
    user32.SetWindowPos(
        hwnd,
        None,
        0,
        0,
        0,
        0,
        _SWP_NOMOVE | _SWP_NOSIZE | _SWP_NOZORDER | _SWP_FRAMECHANGED,
    )


def unpack_nchittest_point(lparam: int) -> tuple[int, int]:
    """Signed 16-bit x/y packed in WM_NCHITTEST lParam (can be off-screen)."""
    raw_x = lparam & 0xFFFF
    raw_y = (lparam >> 16) & 0xFFFF
    x = raw_x - 0x10000 if raw_x >= 0x8000 else raw_x
    y = raw_y - 0x10000 if raw_y >= 0x8000 else raw_y
    return x, y
