"""Global hotkeys via pynput. QShortcut only fires when the overlay is focused."""

from __future__ import annotations

from collections.abc import Callable

from pynput import keyboard

from personalclipboard.config import Settings


class GlobalHotkeys:
    def __init__(
        self,
        settings: Settings,
        on_reformat: Callable[[], None],
        on_type_focus: Callable[[], None] | None = None,
    ) -> None:
        self._settings = settings
        self._on_reformat = on_reformat
        self._on_type_focus = on_type_focus
        self._listener: keyboard.GlobalHotKeys | None = None

    def bindings(self) -> dict[str, Callable[[], None]]:
        mapping: dict[str, Callable[[], None]] = {self._settings.hotkey: self._on_reformat}
        if self._on_type_focus is not None:
            combo = self._settings.type_hotkey
            if combo and combo != self._settings.hotkey:
                mapping[combo] = self._on_type_focus
        return mapping

    def start(self) -> None:
        self._listener = keyboard.GlobalHotKeys(self.bindings())
        self._listener.start()

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
