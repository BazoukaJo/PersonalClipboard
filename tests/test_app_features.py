from __future__ import annotations

# pylint: disable=protected-access,redefined-outer-name

import threading
import time
from pathlib import Path

from PyQt6.QtWidgets import QLabel

from personalclipboard.config import load_settings


def test_copy_button_writes_last_ready(pc_app) -> None:
    pc_app._last_ready = "Hello from copy."
    pc_app._copy_ready()
    assert pc_app._clipboard.read() == "Hello from copy."
    assert "Hello from copy." in pc_app._history.path.read_text(encoding="utf-8")


def test_history_button_opens_modal(pc_app, monkeypatch) -> None:
    from datetime import datetime

    seen: list[list[str]] = []

    def fake_exec(self) -> int:
        bodies = [
            label.text()
            for label in self.findChildren(QLabel)
            if label.objectName() == "historyBody"
        ]
        seen.append(bodies)
        return 0

    monkeypatch.setattr("personalclipboard.app.HistoryDialog.exec", fake_exec)
    pc_app._history._record("Hello history.", datetime(2026, 8, 14, 13, 0, 0))
    pc_app._open_history()
    assert seen
    assert seen[0] == ["Hello history."]


def test_copy_history_entry_does_not_relog(pc_app) -> None:
    pc_app._history.path.write_text("", encoding="utf-8")
    pc_app._copy_history_entry("From history.")
    assert pc_app._clipboard.read() == "From history."
    assert pc_app._history.path.read_text(encoding="utf-8") == ""


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


def test_typed_ai_mode_does_not_change_voice(pc_app) -> None:
    seen: list[dict] = []

    def fake_submit(text: str, **kwargs: object) -> int:
        seen.append({"text": text, **kwargs})
        return 1

    pc_app._llm.submit = fake_submit
    pc_app._overlay.set_correction_mode("ai")
    pc_app._on_typed_commit("Write a summary.")
    pc_app._on_speech_commit("Write a summary.")
    pc_app._clipboard.write("raw clipboard")
    pc_app._on_reformat()
    assert seen[0]["text"] == "Write a summary."
    assert seen[0]["mode"] == "ai"
    assert seen[1]["mode"] == "human"
    assert seen[2]["mode"] == "ai"
    assert pc_app._overlay.correction_mode() == "ai"
    pc_app._overlay.show_audio_phrase("Spoken sentence.")
    assert pc_app._overlay._audio_frame.property("active") == "true"


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
    assert pc_app.record_submitted == ["We discussed the schedule."]
    notes = (tmp_path / pc_app._meeting.filename).read_text(encoding="utf-8")
    assert "schedule" not in notes
    pc_app._on_record_corrected("We discussed the schedule.")
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
    assert pc_app._overlay._enable.accessibleName() == "Micro"


def test_settings_opacity_and_vad(pc_app) -> None:
    pc_app._booting = False
    pc_app._on_opacity_changed(75)
    assert pc_app._settings.overlay_opacity == 75
    pc_app._on_opacity_changed(40)
    assert pc_app._settings.overlay_opacity == 60
    pc_app._on_vad_changed(False)
    assert pc_app._settings.vad_enabled is False
    loaded = load_settings(pc_app.settings_file)
    assert loaded.overlay_opacity == 60
    assert loaded.vad_enabled is False


def test_overlay_geometry_restored(pc_app, qapp) -> None:
    pc_app._settings.overlay_x = 40
    pc_app._settings.overlay_y = 50
    pc_app._settings.overlay_w = 560
    pc_app._settings.overlay_h = 999
    pc_app._place_overlay(qapp)
    geo = pc_app._overlay.geometry()
    assert geo.x() == 40
    assert geo.y() == 50
    assert geo.width() == 560
    assert geo.height() == pc_app._overlay.minimumHeight()
    assert geo.height() < 900


def test_overlay_geometry_falls_back_when_unset(pc_app, qapp) -> None:
    pc_app._settings.overlay_w = 0
    pc_app._settings.overlay_h = 0
    pc_app._place_overlay(qapp)
    screen = qapp.primaryScreen()
    assert screen is not None
    geo = screen.availableGeometry()
    assert pc_app._overlay.y() == geo.y() + 24


def test_shutdown_persists_overlay_geometry(pc_app) -> None:
    pc_app._overlay.move(32, 48)
    expected = pc_app._overlay.compact_geometry()
    pc_app.shutdown()
    loaded = load_settings(pc_app.settings_file)
    assert loaded.overlay_x == expected.x()
    assert loaded.overlay_y == expected.y()
    assert loaded.overlay_w == expected.width()
    assert loaded.overlay_h == expected.height()


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


def test_cycle_rotates_then_retries_original(pc_app) -> None:
    calls: list[tuple[str, dict]] = []

    def fake_submit(text: str, **kwargs: object) -> int:
        calls.append((text, dict(kwargs)))
        return 1

    pc_app._llm.submit = fake_submit
    pc_app._finish_phrase("Hello there.", "audio")
    assert calls == [("Hello there.", {"mode": "human"})]
    pc_app._on_corrected("Hi there.")
    assert pc_app._clipboard.read() == "Hi there."
    pc_app._on_retry_requested()
    assert pc_app._clipboard.read() == "Hello there."
    assert len(calls) == 1
    pc_app._on_retry_requested()
    assert pc_app._clipboard.read() == "Hi there."
    pc_app._on_retry_requested()
    assert len(calls) == 2
    assert calls[1][0] == "Hello there."
    assert calls[1][1]["vary"] is True
    assert calls[1][1]["temperature"] >= 0.55
    assert calls[1][1]["mode"] == "human"
    pc_app._on_corrected("Hey there.")
    assert pc_app._clipboard.read() == "Hey there."
    history = pc_app._history.path.read_text(encoding="utf-8")
    assert history.count("Hello there.") <= 1
    assert "Hey there." in history


def test_cycle_hidden_during_meeting(pc_app, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("personalclipboard.app.desktop_directory", lambda: tmp_path)
    pc_app._finish_phrase("Hello there.", "audio")
    pc_app._on_corrected("Hi there.")
    assert pc_app._overlay._audio_cycle.isVisible()
    pc_app._start_meeting()
    assert not pc_app._overlay._audio_cycle.isVisible()
    pc_app._stop_meeting(restore_mic=False)


def test_meeting_starts_and_stops_speaker_loopback(pc_app, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("personalclipboard.app.desktop_directory", lambda: tmp_path)
    calls: list[str] = []
    pc_app._capture.start_loopback = lambda: calls.append("start") or True
    pc_app._capture.stop_loopback = lambda: calls.append("stop")
    pc_app._start_meeting()
    assert pc_app._meeting is not None
    assert calls == ["start"]
    notes = (tmp_path / pc_app._meeting.filename).read_text(encoding="utf-8")
    assert "fake-speakers" in notes
    pc_app._stop_meeting(restore_mic=False)
    assert calls == ["start", "stop"]


def test_playback_record_skips_microphone(pc_app, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("personalclipboard.app.desktop_directory", lambda: tmp_path)
    starts: list[str] = []
    pc_app._capture.start = lambda: starts.append("mic")
    pc_app._asr.start = lambda: starts.append("asr")
    pc_app._start_record("playback")
    assert pc_app._meeting is not None
    assert pc_app._record_kind == "playback"
    assert pc_app._meeting.kind == "playback"
    assert pc_app._meeting.filename.startswith("Playback")
    assert "mic" not in starts
    notes = (tmp_path / pc_app._meeting.filename).read_text(encoding="utf-8")
    assert "Kind: playback" in notes
    pc_app._stop_meeting(restore_mic=False)
    assert pc_app._meeting is None


def test_open_records_lists_desktop_files(pc_app, tmp_path: Path, monkeypatch) -> None:
    from datetime import datetime

    from personalclipboard.notes.meeting import MeetingNotes
    from personalclipboard.ui.records_dialog import RecordsDialog

    monkeypatch.setattr("personalclipboard.app.desktop_directory", lambda: tmp_path)
    notes = MeetingNotes(tmp_path, datetime(2026, 8, 14, 19, 41), "speakers", kind="playback")
    notes.append("From the video.", when=datetime(2026, 8, 14, 19, 41))
    notes.close()
    seen: list[int] = []

    def fake_exec(self) -> int:
        seen.append(len(self._records))
        return 0

    monkeypatch.setattr(RecordsDialog, "exec", fake_exec)
    pc_app._open_records()
    assert seen == [1]
