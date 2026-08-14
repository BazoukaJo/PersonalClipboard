"""Signals from worker threads onto the Qt main thread."""

from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal


class UiBridge(QObject):
    partial = pyqtSignal(str)
    status = pyqtSignal(str)
    commit = pyqtSignal(str)
    corrected = pyqtSignal(str)
    error = pyqtSignal(str)
    model_ready = pyqtSignal()
    reformat_requested = pyqtSignal()
    command = pyqtSignal(str)
