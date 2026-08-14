from __future__ import annotations

# pylint: disable=protected-access,redefined-outer-name

import threading
import time
from pathlib import Path

import pytest

from personalclipboard.app import PersonalClipboardApp
from personalclipboard.config import Settings


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


@pytest.fixture
def pc_app(qapp, monkeypatch):
    monkeypatch.setattr("personalclipboard.clipboard.service.play_copy_cue", lambda: None)
    monkeypatch.setattr("personalclipboard.app.play_copy_cue", lambda: None)
    settings = Settings()
    app = PersonalClipboardApp(qapp, settings, start_background=False)
    submitted: list[str] = []
    app._llm.submit = lambda text: submitted.append(text) or 1
    app.submitted = submitted  # type: ignore[attr-defined]
    fake = FakeWindows()
    app._windows = fake  # type: ignore[assignment]
    app._probe.start = lambda: None
    app._probe.stop = lambda: None
    app._capture.start = lambda: None
    app._capture.stop = lambda: None
    app._capture.close = lambda: None
    app._capture.device_name = "fake-mic"
    app._capture.backend = "pyaudio"
    app._asr.start = lambda: None
    app._asr.stop = lambda: None
    app._asr._model = object()  # type: ignore[assignment]
    yield app
    app.shutdown()


def test_copy_button_writes_last_ready(pc_app) -> None:
    pc_app._last_ready = "Hello from copy."
    pc_app._copy_ready()
    assert pc_app._clipboard.read() == "Hello from copy."


def test_copy_button_empty(pc_app) -> None:
    pc_app._clipboard.write("")
    pc_app._last_ready = ""
    pc_app._copy_ready()
    assert "Nothing" in pc_app._overlay._status.text() or pc_app._overlay._status.text() == "Empty"


def test_paste_last_focuses_and_pastes(pc_app) -> None:
    pc_app._last_ready = "Paste me."
    pc_app._on_command("paste_last")
    assert pc_app._clipboard.read() == "Paste me."
    assert pc_app._windows.paste_calls == 1


def test_paste_last_without_target_window(pc_app) -> None:
    pc_app._last_ready = "Paste me."
    pc_app._windows.can_focus = False
    pc_app._on_command("paste_last")
    assert pc_app._windows.paste_calls == 0
    assert pc_app._overlay._status.text()


def test_paste_last_empty(pc_app) -> None:
    pc_app._last_ready = ""
    pc_app._clipboard.write("")
    pc_app._on_command("paste_last")
    assert pc_app._windows.paste_calls == 0


def test_copy_last_from_other_window(pc_app, qapp) -> None:
    def fake_copy() -> None:
        pc_app._windows.copy_calls += 1
        pc_app._clipboard.write("Selected in Notepad.")

    pc_app._windows.copy = fake_copy
    pc_app._on_command("copy_last")
    qapp.processEvents()
    assert pc_app._windows.copy_calls == 1
    assert pc_app._last_ready == "Selected in Notepad."
    assert "Selected in Notepad." in pc_app._overlay.typed_text()


def test_copy_last_without_focus(pc_app) -> None:
    pc_app._windows.can_focus = False
    pc_app._on_command("copy_last")
    assert pc_app._windows.copy_calls == 0


def test_correct_last_reformats_clipboard(pc_app) -> None:
    pc_app._clipboard.write("fix this sentence")
    pc_app._on_command("correct_last")
    assert pc_app.submitted == ["fix this sentence"]


def test_reformat_empty_clipboard(pc_app) -> None:
    pc_app._clipboard.write("   ")
    pc_app._on_reformat()
    assert pc_app.submitted == []


def test_typed_commit_goes_to_llm(pc_app) -> None:
    pc_app._on_typed_commit("Hello world.")
    assert pc_app.submitted == ["Hello world."]
    assert pc_app._commit_source == "typed"


def test_speech_commit_goes_to_llm(pc_app) -> None:
    pc_app._on_speech_commit("Spoken sentence.")
    assert pc_app.submitted == ["Spoken sentence."]
    assert pc_app._commit_source == "audio"


def test_corrected_text_lands_on_clipboard(pc_app) -> None:
    pc_app._commit_source = "audio"
    pc_app._on_corrected("Clean prose.")
    assert pc_app._last_ready == "Clean prose."
    assert pc_app._clipboard.read() == "Clean prose."


def test_vad_idle_stops_stream_and_wake_restarts(pc_app) -> None:
    starts: list[str] = []
    stops: list[str] = []
    probes: list[str] = []
    pc_app._capture.start = lambda: starts.append("cap")
    pc_app._asr.start = lambda: starts.append("asr")
    pc_app._capture.stop = lambda: stops.append("cap")
    pc_app._asr.stop = lambda: stops.append("asr")
    pc_app._probe.start = lambda: probes.append("start")
    pc_app._probe.stop = lambda: probes.append("stop")
    pc_app._want_mic = True
    pc_app._enter_vad_idle()
    assert pc_app._vad_sleeping is True
    assert "cap" in stops and "asr" in stops
    assert probes == ["start"]
    pc_app._leave_vad_idle()
    assert pc_app._vad_sleeping is False
    assert "cap" in starts and "asr" in starts
    assert probes[-1] == "stop"


def test_vad_idle_skipped_during_meeting(pc_app, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("personalclipboard.app.desktop_directory", lambda: tmp_path)
    pc_app._want_mic = True
    pc_app._start_meeting()
    assert pc_app._meeting is not None
    pc_app._enter_vad_idle()
    assert pc_app._vad_sleeping is False
    pc_app._stop_meeting(restore_mic=False)


def test_meeting_notes_append_not_clipboard(pc_app, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("personalclipboard.app.desktop_directory", lambda: tmp_path)
    pc_app._clipboard.write("keep-me")
    pc_app._asr.flush_remainder = lambda: ""
    pc_app._start_meeting()
    pc_app._on_speech_commit("We discussed the schedule.")
    assert pc_app._clipboard.read() == "keep-me"
    assert pc_app.submitted == []
    notes = (tmp_path / pc_app._meeting.filename).read_text(encoding="utf-8")
    assert "schedule" in notes
    pc_app._stop_meeting(restore_mic=False)
    saved = list(tmp_path.glob("Meeting *.md"))
    assert saved


def test_settings_language_persists(pc_app, monkeypatch) -> None:
    monkeypatch.setattr("personalclipboard.app.save_settings", lambda _settings: None)
    pc_app._booting = False
    pc_app._on_language_changed("fr")
    assert pc_app._settings.ui_language == "fr"
    pc_app._overlay.apply_language("fr")
    assert pc_app._overlay._enable.text() == "Micro"


def test_settings_opacity_and_vad(pc_app) -> None:
    pc_app._booting = False
    pc_app._on_opacity_changed(55)
    assert pc_app._settings.overlay_opacity == 55
    pc_app._on_vad_changed(False)
    assert pc_app._settings.vad_enabled is False


def test_mic_off_is_privacy_kill_switch(pc_app) -> None:
    probes: list[str] = []
    pc_app._probe.stop = lambda: probes.append("stop")
    pc_app._vad_sleeping = True
    pc_app._set_capture(False)
    assert pc_app._want_mic is False
    assert pc_app._vad_sleeping is False
    assert probes == ["stop"]


def test_worker_thread_can_fill_ollama_models(pc_app, qapp) -> None:
    done = threading.Event()

    def emit() -> None:
        pc_app._bridge.ollama_models.emit(["llama3.2:1b"])
        done.set()

    threading.Thread(target=emit, daemon=True).start()
    assert done.wait(2)
    deadline = time.monotonic() + 2
    while pc_app._overlay.settings._ollama.findText("llama3.2:1b") < 0:
        qapp.processEvents()
        if time.monotonic() > deadline:
            break
        time.sleep(0.02)
    assert pc_app._overlay.settings._ollama.findText("llama3.2:1b") >= 0


def test_worker_thread_model_ready_enables_mic(pc_app, qapp) -> None:
    pc_app._start_mic_on_ready = False
    done = threading.Event()

    def emit() -> None:
        pc_app._bridge.model_ready.emit()
        done.set()

    threading.Thread(target=emit, daemon=True).start()
    assert done.wait(2)
    deadline = time.monotonic() + 2
    while not pc_app._overlay._enable.isEnabled():
        qapp.processEvents()
        if time.monotonic() > deadline:
            break
        time.sleep(0.02)
    assert pc_app._overlay._enable.isEnabled()


def test_type_hotkey_focuses_type_when_idle(pc_app, qapp) -> None:
    pc_app._overlay.show()
    pc_app._overlay.release_type_field()
    qapp.processEvents()
    pc_app._on_type_focus()
    qapp.processEvents()
    assert pc_app._windows.hwnd_calls
    assert pc_app._windows.foreign_calls == 0


def test_type_hotkey_returns_to_other_app_when_type_focused(pc_app, monkeypatch) -> None:
    monkeypatch.setattr(pc_app._overlay, "type_field_active", lambda: True)
    pc_app._on_type_focus()
    assert pc_app._windows.foreign_calls == 1


def test_type_hotkey_stays_when_no_other_app(pc_app, monkeypatch) -> None:
    monkeypatch.setattr(pc_app._overlay, "type_field_active", lambda: True)
    pc_app._windows.can_focus = False
    pc_app._on_type_focus()
    assert pc_app._windows.foreign_calls == 1
    assert pc_app._overlay._status.text()
