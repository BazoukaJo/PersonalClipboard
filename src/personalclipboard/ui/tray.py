"""System tray icon, About text, and process restart."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QMessageBox, QWidget

from personalclipboard import __version__

_CREATE_NEW_PROCESS_GROUP = 0x00000200
_DETACHED_PROCESS = 0x00000008


def app_version() -> str:
    return __version__


def about_body() -> str:
    return (
        f"PersonalClipboard {app_version()}\n\n"
        "Local dictation overlay for this PC.\n"
        "Microphone audio, transcripts, and clipboard text stay on this machine.\n"
        "Correction runs on Ollama at 127.0.0.1 only.\n\n"
        "Finish a spoken or typed phrase with a period to correct and copy.\n"
        "In Type, Tab accepts the grey suggestion while that field is focused.\n"
        "Say paste last, copy last, or correct last.\n"
        "Ctrl+Shift+A reformats the current clipboard.\n"
        "Record meeting transcribes the room and saves notes on the desktop.\n"
        "Starting the app again replaces the running overlay.\n\n"
        "Uncheck Mic to idle the microphone."
    )


def repo_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def packaged_exe() -> Path | None:
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable).resolve()
        return exe if exe.is_file() else None
    candidates = (
        repo_root() / "dist" / "PersonalClipboard" / "PersonalClipboard.exe",
        repo_root() / "PersonalClipboard.exe",
    )
    for path in candidates:
        if path.is_file():
            return path
    return None


def restart_command() -> list[str]:
    exe = packaged_exe()
    if exe is not None:
        return [str(exe)]
    return [_pythonw_or_current(), "-m", "personalclipboard"]


def spawn_new_instance() -> None:
    flags = 0
    if sys.platform == "win32":
        flags = _DETACHED_PROCESS | _CREATE_NEW_PROCESS_GROUP
    cmd = restart_command()
    work = str(Path(cmd[0]).resolve().parent) if cmd[0].lower().endswith(".exe") else os.getcwd()
    subprocess.Popen(  # pylint: disable=consider-using-with
        cmd,
        cwd=work,
        creationflags=flags,
        close_fds=True,
    )


def show_about(parent: QWidget | None) -> None:
    box = QMessageBox(parent)
    box.setWindowTitle("About PersonalClipboard")
    box.setTextFormat(Qt.TextFormat.PlainText)
    box.setText(about_body())
    box.setStandardButtons(QMessageBox.StandardButton.Ok)
    box.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
    box.exec()


def make_tray_icon() -> QIcon:
    icon = QIcon()
    for size in (16, 20, 24, 32, 48, 64):
        icon.addPixmap(_draw_icon(size))
    return icon


def _pythonw_or_current() -> str:
    exe = sys.executable
    if sys.platform == "win32" and exe.lower().endswith("python.exe"):
        pythonw = exe[: -len("python.exe")] + "pythonw.exe"
        if os.path.isfile(pythonw):
            return pythonw
    return exe


def _draw_icon(size: int) -> QPixmap:
    pix = QPixmap(size, size)
    pix.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(22, 22, 24))
    painter.drawRoundedRect(0, 0, size, size, size * 0.22, size * 0.22)
    margin = max(2, size // 8)
    painter.setBrush(QColor(36, 36, 38))
    painter.setPen(QPen(QColor(180, 180, 184), max(1, size // 16)))
    painter.drawRoundedRect(
        margin,
        margin + size // 12,
        size - 2 * margin,
        size - 2 * margin - size // 16,
        max(1, size // 16),
        max(1, size // 16),
    )
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(200, 200, 204))
    clip_w = max(4, size // 3)
    clip_h = max(3, size // 5)
    painter.drawRoundedRect((size - clip_w) // 2, max(1, size // 14), clip_w, clip_h, 2, 2)
    painter.end()
    return pix
