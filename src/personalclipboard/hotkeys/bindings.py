"""Global Ctrl+Shift+A via pynput. QShortcut only fires when the overlay is focused."""

from __future__ import annotations

from collections.abc import Callable

from pynput import keyboard

from personalclipboard.config import Settings


class GlobalHotkeys:
    def __init__(self, settings: Settings, on_reformat: Callable[[], None]) -> None:
        self._settings = settings
        self._on_reformat = on_reformat
        self._listener: keyboard.GlobalHotKeys | None = None

    def start(self) -> None:
        combo = self._settings.hotkey
        self._listener = keyboard.GlobalHotKeys({combo: self._on_reformat})
        self._listener.start()

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
