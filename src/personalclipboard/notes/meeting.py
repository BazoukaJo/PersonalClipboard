"""Save live meeting transcripts to the Windows desktop."""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path


def desktop_directory() -> Path:
    """User desktop, including OneDrive-redirected Desktop/Bureau."""
    candidates: list[Path] = []
    known = _known_folder_desktop()
    if known is not None:
        candidates.append(known)
    home = Path.home()
    profile = Path(os.environ.get("USERPROFILE", str(home)))
    candidates.extend(
        [
            home / "Desktop",
            profile / "Desktop",
            home / "OneDrive" / "Desktop",
            profile / "OneDrive" / "Desktop",
            home / "OneDrive" / "Bureau",
            profile / "OneDrive" / "Bureau",
        ]
    )
    for path in candidates:
        if path.is_dir():
            return path
    fallback = home / "Desktop"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def meeting_filename(when: datetime, existing: list[str] | None = None) -> str:
    stamp = when.strftime("%Y-%m-%d %H%M")
    base = f"Meeting {stamp}.md"
    names = set(existing or [])
    if base not in names:
        return base
    index = 2
    while True:
        candidate = f"Meeting {stamp} {index}.md"
        if candidate not in names:
            return candidate
        index += 1


class MeetingNotes:
    """Append-only markdown notes. Flushes each line so a crash still keeps text."""

    def __init__(self, directory: Path, started: datetime, source: str) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        existing = [path.name for path in directory.glob("Meeting *.md")]
        self.path = directory / meeting_filename(started, existing)
        self._started = started
        self._lines: list[str] = []
        header = (
            f"# Meeting notes\n\n"
            f"- Started: {started.strftime('%A, %d %B %Y, %H:%M')}\n"
            f"- Source: {source}\n"
            f"- Local transcript only. Audio is not saved.\n\n"
        )
        self.path.write_text(header, encoding="utf-8")

    @property
    def filename(self) -> str:
        return self.path.name

    def append(self, text: str, when: datetime | None = None) -> None:
        stripped = " ".join(text.split())
        if not stripped:
            return
        stamp = (when or datetime.now()).strftime("%H:%M")
        line = f"- **{stamp}** {stripped}"
        self._lines.append(line)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def preview(self) -> str:
        if not self._lines:
            return ""
        return "\n".join(self._lines[-12:])

    def close(self) -> None:
        ended = datetime.now().strftime("%A, %d %B %Y, %H:%M")
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(f"\n- Ended: {ended}\n")
            handle.flush()


def _known_folder_desktop() -> Path | None:
    if sys.platform != "win32":
        return None
    import ctypes
    from ctypes import wintypes
    from uuid import UUID

    class Guid(ctypes.Structure):
        _fields_ = [
            ("Data1", wintypes.DWORD),
            ("Data2", wintypes.WORD),
            ("Data3", wintypes.WORD),
            ("Data4", ctypes.c_ubyte * 8),
        ]

    folderid = UUID("{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}")
    guid = Guid(
        folderid.time_low,
        folderid.time_mid,
        folderid.time_hi_version,
        (ctypes.c_ubyte * 8).from_buffer_copy(folderid.bytes[8:]),
    )
    path_ptr = ctypes.c_wchar_p()
    result = ctypes.windll.shell32.SHGetKnownFolderPath(
        ctypes.byref(guid), 0, None, ctypes.byref(path_ptr)
    )
    if result != 0 or not path_ptr.value:
        return None
    text = path_ptr.value
    ctypes.windll.ole32.CoTaskMemFree(path_ptr)
    path = Path(text)
    return path if path.is_dir() else None
