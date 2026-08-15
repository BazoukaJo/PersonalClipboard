"""Signals from worker threads onto the Qt main thread."""

from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal


class UiBridge(QObject):
    """Qt-thread owner for worker signals. `predicted` is (typed prefix, ghost suffix)."""
    partial = pyqtSignal(str)
    status = pyqtSignal(str)
    commit = pyqtSignal(str)
    corrected = pyqtSignal(str)
    error = pyqtSignal(str)
    model_ready = pyqtSignal()
    reformat_requested = pyqtSignal()
    command = pyqtSignal(str)
    vad_idle = pyqtSignal()
    vad_wake = pyqtSignal()
    ollama_models = pyqtSignal(object)
    predicted = pyqtSignal(str, str)
    type_focus_requested = pyqtSignal()
    record_corrected = pyqtSignal(str)
