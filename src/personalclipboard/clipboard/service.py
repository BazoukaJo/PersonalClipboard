"""Windows clipboard via QClipboard. Must be used from the Qt main thread."""

from __future__ import annotations

from PyQt6.QtGui import QClipboard

from personalclipboard.ui.copy_cue import play_copy_cue


class ClipboardService:
    def __init__(self, clipboard: QClipboard) -> None:
        self._clip = clipboard

    def read(self) -> str:
        return self._clip.text() or ""

    def write(self, text: str) -> None:
        """Replace clipboard contents. Callers must not write rejected cacophony commits."""
        self._clip.setText(text)
        if text.strip():
            play_copy_cue()
