from __future__ import annotations

import os

import pytest
from PyQt6.QtWidgets import QApplication

from personalclipboard.app import PersonalClipboardApp
from personalclipboard.clipboard.history import ClipboardHistory
from personalclipboard.config import Settings, save_settings as write_settings


class FakeWindows:
    def __init__(self) -> None:
        self.can_focus = True
        self.paste_calls = 0
        self.copy_calls = 0
        self.foreign_calls = 0
        self.hwnd_calls: list[int] = []

    def poll(self) -> None:
        return None

    def focus_last_foreign(self) -> bool:
        self.foreign_calls += 1
        return self.can_focus

    def focus_hwnd(self, hwnd: int) -> bool:
        self.hwnd_calls.append(hwnd)
        return True

    def paste(self) -> None:
        self.paste_calls += 1

    def copy(self) -> None:
        self.copy_calls += 1


@pytest.fixture(scope="session")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    existing = QApplication.instance()
    if isinstance(existing, QApplication):
        existing.setQuitOnLastWindowClosed(False)
        return existing
    app = QApplication(["personalclipboard-tests"])
    app.setQuitOnLastWindowClosed(False)
    return app


@pytest.fixture
def pc_app(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr("personalclipboard.clipboard.service.play_copy_cue", lambda: None)
    monkeypatch.setattr("personalclipboard.app.play_copy_cue", lambda: None)
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(
        "personalclipboard.app.save_settings",
        lambda settings, path=None: write_settings(settings, settings_file),
    )
    settings = Settings()
    history = ClipboardHistory(tmp_path / "history.txt", threaded=False)
    app = PersonalClipboardApp(qapp, settings, start_background=False, history=history)
    submitted: list[str] = []
    record_submitted: list[str] = []
    app._llm.submit = lambda text, **_kwargs: submitted.append(text) or 1
    app._llm.submit_record = lambda text, **_kwargs: record_submitted.append(text) or 1
    app.submitted = submitted  # type: ignore[attr-defined]
    app.record_submitted = record_submitted  # type: ignore[attr-defined]
    app.settings_file = settings_file  # type: ignore[attr-defined]
    fake = FakeWindows()
    app._windows = fake  # type: ignore[assignment]
    app._probe.start = lambda: None
    app._probe.stop = lambda: None
    app._capture.start = lambda: None
    app._capture.stop = lambda: None
    app._capture.close = lambda: None
    app._capture.start_loopback = lambda: True
    app._capture.stop_loopback = lambda: None
    app._capture.device_name = "fake-mic"
    app._capture.loopback_name = "fake-speakers"
    app._capture.backend = "pyaudio"
    app._asr.start = lambda: None
    app._asr.stop = lambda: None
    app._asr._model = object()  # type: ignore[assignment]
    yield app
    app.shutdown()
