from __future__ import annotations

# pylint: disable=protected-access,redefined-outer-name

from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QLabel

from personalclipboard.config import load_settings
from personalclipboard.notes.meeting import MeetingNotes
from personalclipboard.ui.i18n import LANGS, t
from personalclipboard.ui.records_dialog import RecordsDialog, _RecordCard


def _track_submit(app) -> list[dict]:
    calls: list[dict] = []

    def submit(text: str, **kwargs: object) -> int:
        calls.append({"text": text, **kwargs})
        app.submitted.append(text)
        return 1

    app._llm.submit = submit
    return calls


def test_settings_offers_en_fr_es_only(qapp) -> None:
    from personalclipboard.ui.overlay import Overlay

    overlay = Overlay()
    codes = [overlay.settings._lang_box.itemData(i) for i in range(overlay.settings._lang_box.count())]
    names = [overlay.settings._lang_box.itemText(i) for i in range(overlay.settings._lang_box.count())]
    assert tuple(codes) == ("en", "fr", "es")
    assert LANGS == (("en", "English"), ("fr", "Français"), ("es", "Español"))
    assert "de" not in codes
    assert "nl" not in codes
    assert "Deutsch" not in names
    assert "Nederlands" not in names
    assert "Dutch" not in names
    overlay.close()


def test_saved_dutch_or_german_ui_falls_back_to_english(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text('{"ui_language": "de"}', encoding="utf-8")
    assert load_settings(path).ui_language == "en"
    path.write_text('{"ui_language": "nl"}', encoding="utf-8")
    assert load_settings(path).ui_language == "en"


def test_voice_partial_is_not_corrected_commit_lands_on_clipboard(pc_app, qapp) -> None:
    overlay = pc_app._overlay
    overlay.show()
    qapp.processEvents()
    overlay.show_partial("hello there")
    assert pc_app.submitted == []
    assert "hello" in overlay._audio_live.text().lower()
    pc_app._on_speech_commit("Hello there.")
    assert pc_app.submitted == ["Hello there."]
    assert overlay._audio_body.text() == "Hello there."
    pc_app._on_corrected("Hello there.")
    assert pc_app._clipboard.read() == "Hello there."
    assert overlay._audio_body.text() == "Hello there."
    assert overlay._status.text() == "Copied"


def test_type_period_corrects_and_copies(pc_app, qapp) -> None:
    overlay = pc_app._overlay
    overlay.show()
    qapp.processEvents()
    overlay._input.setText("The meeting is at noon.")
    qapp.processEvents()
    assert pc_app.submitted == ["The meeting is at noon."]
    assert pc_app._commit_source == "typed"
    pc_app._on_corrected("The meeting is at noon.")
    assert pc_app._clipboard.read() == "The meeting is at noon."
    assert overlay._typed_body.text() == "The meeting is at noon."


def test_type_enter_appends_period_and_copies(pc_app, qapp) -> None:
    overlay = pc_app._overlay
    overlay.show()
    qapp.processEvents()
    overlay._input.setText("Send the report")
    overlay._input.returnPressed.emit()
    qapp.processEvents()
    assert pc_app.submitted == ["Send the report."]
    pc_app._on_corrected("Send the report.")
    assert pc_app._clipboard.read() == "Send the report."


def test_type_ai_radio_reformulates_voice_stays_human(pc_app, qapp) -> None:
    overlay = pc_app._overlay
    overlay.show()
    qapp.processEvents()
    calls = _track_submit(pc_app)
    overlay._mode_ai.click()
    qapp.processEvents()
    assert overlay.correction_mode() == "ai"
    overlay._input.setText("sum up the notes.")
    qapp.processEvents()
    pc_app._on_speech_commit("sum up the notes.")
    assert calls[0]["mode"] == "ai"
    assert calls[1]["mode"] == "human"
    pc_app._on_corrected("Summarize the notes.")
    assert overlay._audio_body.text() == "Summarize the notes."
    assert overlay._audio_frame.property("active") == "true"


def test_reformat_hotkey_uses_type_correction_mode(pc_app) -> None:
    calls = _track_submit(pc_app)
    pc_app._overlay._mode_ai.click()
    pc_app._clipboard.write("fix this sentence")
    pc_app._on_command("correct_last")
    assert calls == [{"text": "fix this sentence", "mode": "ai"}]
    pc_app._on_corrected("Fix this sentence.")
    assert pc_app._clipboard.read() == "Fix this sentence."


def test_mic_on_starts_capture_off_stops_probe(pc_app, qapp) -> None:
    overlay = pc_app._overlay
    starts: list[str] = []
    stops: list[str] = []
    probes: list[str] = []
    pc_app._capture.start = lambda: starts.append("mic")
    pc_app._asr.start = lambda: starts.append("asr")
    pc_app._capture.stop = lambda: stops.append("mic")
    pc_app._asr.stop = lambda: stops.append("asr")
    pc_app._probe.stop = lambda: probes.append("stop")
    overlay.set_listen_enabled(True)
    overlay._enable.click()
    qapp.processEvents()
    assert overlay._enable.isChecked()
    assert starts == ["mic", "asr"]
    assert overlay._status_key == "listening"
    overlay._enable.click()
    qapp.processEvents()
    assert not overlay._enable.isChecked()
    assert "mic" in stops and "asr" in stops
    assert probes == ["stop"]
    assert overlay._status_key == "off"


def test_hide_button_hides_overlay(pc_app, qapp) -> None:
    overlay = pc_app._overlay
    overlay.show()
    qapp.processEvents()
    assert overlay.isVisible()
    overlay._hide_btn.click()
    qapp.processEvents()
    assert not overlay.isVisible()


def test_copy_button_puts_last_sentence_on_clipboard(pc_app, qapp) -> None:
    overlay = pc_app._overlay
    pc_app._clipboard.write("stale")
    pc_app._last_ready = "Ready to paste now."
    overlay._copy_btn.click()
    qapp.processEvents()
    assert pc_app._clipboard.read() == "Ready to paste now."
    assert overlay._status.text() == "Copied"


def test_clips_button_shows_clipboard_history(pc_app, monkeypatch) -> None:
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
    pc_app._history._record("Saved clip.", datetime(2026, 8, 14, 13, 0, 0))
    pc_app._overlay._history_btn.click()
    assert seen == [["Saved clip."]]


def test_spanish_language_relabels_overlay(pc_app, qapp) -> None:
    overlay = pc_app._overlay
    pc_app._booting = False
    box = overlay.settings._lang_box
    box.setCurrentIndex(box.findData("es"))
    qapp.processEvents()
    assert overlay._enable.text() == t("es", "mic")
    assert overlay._hide_btn.text() == t("es", "hide")
    assert overlay._voice_role.text() == t("es", "voice_role")
    assert load_settings(pc_app.settings_file).ui_language == "es"


def test_type_ahead_tab_inserts_suggestion(pc_app, qapp, monkeypatch) -> None:
    overlay = pc_app._overlay
    overlay.show()
    overlay.focus_type_field()
    qapp.processEvents()
    monkeypatch.setattr(overlay._input, "hasFocus", lambda: True)
    overlay._input.set_blocked(True)
    overlay._input.setText("The meeting is")
    overlay._input.set_blocked(False)
    pc_app._on_predicted("The meeting is", " tomorrow")
    assert overlay._input.ghost() == " tomorrow"
    tab = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Tab, Qt.KeyboardModifier.NoModifier)
    assert overlay._input.event(tab) is True
    qapp.processEvents()
    assert overlay._input.text() == "The meeting is tomorrow"
    assert overlay._input.ghost() == ""


def test_paste_last_command_pastes_into_other_app(pc_app) -> None:
    pc_app._last_ready = "Paste me."
    pc_app._on_command("paste_last")
    assert pc_app._clipboard.read() == "Paste me."
    assert pc_app._windows.paste_calls == 1


def test_retry_cycles_voice_wording(pc_app, qapp) -> None:
    overlay = pc_app._overlay
    pc_app._on_speech_commit("Hello there.")
    pc_app._on_corrected("Hi there.")
    assert pc_app._clipboard.read() == "Hi there."
    assert overlay._audio_cycle.isVisible()
    overlay._audio_cycle.click()
    qapp.processEvents()
    assert pc_app._clipboard.read() == "Hello there."


def test_meeting_record_writes_desktop_markdown_not_clipboard(
    pc_app, tmp_path: Path, monkeypatch, qapp
) -> None:
    monkeypatch.setattr("personalclipboard.app.desktop_directory", lambda: tmp_path)
    overlay = pc_app._overlay
    overlay.set_listen_enabled(True)
    pc_app._clipboard.write("keep-me")
    overlay._act_meeting.trigger()
    qapp.processEvents()
    assert pc_app._meeting is not None
    assert pc_app._meeting.filename.startswith("Meeting")
    assert not overlay._copy_btn.isEnabled()
    pc_app._on_speech_commit("We discussed the schedule.")
    assert pc_app._clipboard.read() == "keep-me"
    assert pc_app.record_submitted == ["We discussed the schedule."]
    pc_app._on_record_corrected("We discussed the schedule.")
    notes = (tmp_path / pc_app._meeting.filename).read_text(encoding="utf-8")
    assert "We discussed the schedule." in notes
    overlay._record_btn.click()
    qapp.processEvents()
    assert pc_app._meeting is None
    assert list(tmp_path.glob("Meeting *.md"))


def test_playback_record_uses_speakers_only(
    pc_app, tmp_path: Path, monkeypatch, qapp
) -> None:
    monkeypatch.setattr("personalclipboard.app.desktop_directory", lambda: tmp_path)
    starts: list[str] = []
    pc_app._capture.start = lambda: starts.append("mic")
    overlay = pc_app._overlay
    overlay.set_listen_enabled(True)
    overlay._act_playback.trigger()
    qapp.processEvents()
    assert pc_app._record_kind == "playback"
    assert pc_app._meeting is not None
    assert pc_app._meeting.filename.startswith("Playback")
    assert "mic" not in starts
    overlay._enable.setChecked(False)
    qapp.processEvents()
    assert pc_app._meeting is not None
    overlay._record_btn.click()
    qapp.processEvents()
    assert pc_app._meeting is None


def test_records_button_lists_saved_transcripts(
    pc_app, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr("personalclipboard.app.desktop_directory", lambda: tmp_path)
    notes = MeetingNotes(tmp_path, datetime(2026, 8, 14, 19, 41), "speakers", kind="playback")
    notes.append("From the video.", when=datetime(2026, 8, 14, 19, 41))
    notes.close()
    seen: list[int] = []

    def fake_exec(self) -> int:
        seen.append(len(self._records))
        cards = self.findChildren(_RecordCard)
        assert cards
        cards[0].clicked.emit(self._records[0])
        assert "From the video." in self._detail_page._body.toPlainText()
        return 0

    monkeypatch.setattr(RecordsDialog, "exec", fake_exec)
    pc_app._overlay._records_btn.click()
    assert seen == [1]


def test_correction_mode_persists(pc_app, qapp) -> None:
    pc_app._booting = False
    pc_app._overlay._mode_ai.click()
    qapp.processEvents()
    loaded = load_settings(pc_app.settings_file)
    assert loaded.correction_mode == "ai"


def test_vad_quiet_stops_capture_speech_wakes_it(pc_app) -> None:
    starts: list[str] = []
    stops: list[str] = []
    pc_app._capture.start = lambda: starts.append("cap")
    pc_app._asr.start = lambda: starts.append("asr")
    pc_app._capture.stop = lambda: stops.append("cap")
    pc_app._asr.stop = lambda: stops.append("asr")
    pc_app._want_mic = True
    pc_app._enter_vad_idle()
    assert pc_app._vad_sleeping is True
    assert "cap" in stops
    pc_app._leave_vad_idle()
    assert pc_app._vad_sleeping is False
    assert "cap" in starts
