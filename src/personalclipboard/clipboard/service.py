"""Windows clipboard via QClipboard. Must be used from the Qt main thread."""

from __future__ import annotations

from PyQt6.QtGui import QClipboard

from personalclipboard.clipboard.history import ClipboardHistory
from personalclipboard.ui.copy_cue import play_copy_cue


class ClipboardService:
    def __init__(
        self,
        clipboard: QClipboard,
        history: ClipboardHistory | None = None,
    ) -> None:
        self._clip = clipboard
        self._history = history

    def read(self) -> str:
        return self._clip.text() or ""

    def write(self, text: str, *, log: bool = True) -> None:
        """Replace clipboard contents. Callers must not write rejected cacophony commits."""
        self._clip.setText(text)
        if text.strip():
            play_copy_cue()
            if log and self._history is not None:
                self._history.append(text)
