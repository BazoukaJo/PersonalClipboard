# pylint: disable=protected-access
from PyQt6.QtCore import QEventLoop, Qt, QTimer
from PyQt6.QtWidgets import QToolButton

from personalclipboard.ui.i18n import t
from personalclipboard.ui.overlay import Overlay
from personalclipboard.ui.settings_panel import SettingsPanel


def _flush_qt(qapp) -> None:
    qapp.processEvents()
    loop = QEventLoop()
    QTimer.singleShot(0, loop.quit)
    loop.exec()
    qapp.processEvents()
    QTimer.singleShot(0, loop.quit)
    loop.exec()
    qapp.processEvents()


def test_overlay_builds_and_translates(qapp) -> None:
    assert qapp is not None
    overlay = Overlay()
    overlay.apply_language("fr")
    assert overlay._enable.accessibleName() == t("fr", "mic")
    assert overlay._enable.text() == t("fr", "status_off")
    assert overlay._status is overlay._enable
    assert overlay._mode_human.text() == t("fr", "correct_human")
    assert overlay._mode_ai.text() == t("fr", "correct_ai")
    assert overlay._history_btn.text() == t("fr", "clips")
    assert overlay._voice_role.text() == t("fr", "voice_role")
    overlay.apply_language("es")
    overlay.set_opacity(60)
    overlay.set_status("quiet")
    assert overlay._status_key == "quiet"
    assert overlay._enable.text() == t("es", "status_quiet")
    overlay.close()


def test_native_event_returns_tuple(qapp) -> None:
    assert qapp is not None
    overlay = Overlay()
    handled, code = overlay.nativeEvent(b"not-windows-msg", 0)  # type: ignore[arg-type]
    assert handled is False
    assert code == 0
    overlay.close()


def test_settings_panel_emits_language_opacity_vad(qapp) -> None:
    assert qapp is not None
    panel = SettingsPanel()
    langs: list[str] = []
    opacities: list[int] = []
    vads: list[bool] = []
    panel.language_changed.connect(langs.append)
    panel.opacity_changed.connect(opacities.append)
    panel.vad_changed.connect(vads.append)
    french = panel._lang_box.findData("fr")
    panel._lang_box.setCurrentIndex(french)
    panel._opacity.setValue(72)
    panel._vad.setChecked(True)
    panel._vad.setChecked(False)
    assert langs == ["fr"]
    assert opacities[-1] == 72
    assert vads == [True, False]
    panel.set_values(
        language="en",
        opacity=80,
        whisper="large-v3-turbo",
        ollama="qwen2.5:1.5b",
        ollama_models=[],
        vad=True,
        predict=True,
    )
    assert langs == ["fr"]
    panel.deleteLater()


def test_settings_panel_emits_input_output(qapp) -> None:
    panel = SettingsPanel()
    inputs: list[tuple[str, str]] = []
    outputs: list[tuple[str, str]] = []
    panel.input_changed.connect(lambda ident, name: inputs.append((ident, name)))
    panel.output_changed.connect(lambda ident, name: outputs.append((ident, name)))
    panel.set_values(
        language="en",
        opacity=80,
        whisper="large-v3-turbo",
        ollama="qwen2.5:1.5b",
        ollama_models=[],
        vad=True,
        predict=True,
        input_devices=[("{mic}", "Microphone (Maono AU-PM401)")],
        output_devices=[("{spk}", "Headphones (JBL)")],
        input_device_id="",
        output_device_id="",
    )
    panel._input.setCurrentIndex(panel._input.findData("{mic}"))
    panel._output.setCurrentIndex(panel._output.findData("{spk}"))
    assert inputs == [("{mic}", "Microphone (Maono AU-PM401)")]
    assert outputs == [("{spk}", "Headphones (JBL)")]
    panel.set_values(
        language="en",
        opacity=80,
        whisper="large-v3-turbo",
        ollama="qwen2.5:1.5b",
        ollama_models=[],
        vad=True,
        predict=True,
        input_devices=[("{mic}", "Microphone (Maono AU-PM401)")],
        output_devices=[("{spk}", "Headphones (JBL)")],
        input_device_id="{mic}",
        input_device_name="Microphone (Maono AU-PM401)",
        output_device_id="{spk}",
        output_device_name="Headphones (JBL)",
    )
    assert inputs == [("{mic}", "Microphone (Maono AU-PM401)")]
    panel.deleteLater()


def test_opening_settings_does_not_grow_overlay(qapp) -> None:
    assert qapp is not None
    overlay = Overlay()
    overlay.show()
    qapp.processEvents()
    before_h = overlay.height()
    before_w = overlay.width()
    voice_y = overlay._audio_frame.y()
    voice_h = overlay._audio_frame.height()
    assert overlay._root.indexOf(overlay.settings) == -1
    overlay.settings.show()
    _flush_qt(qapp)
    assert overlay.settings.isVisible()
    assert overlay.settings.isModal()
    assert overlay.settings.windowModality() == Qt.WindowModality.ApplicationModal
    assert overlay.height() == before_h
    assert overlay.width() == before_w
    assert overlay._audio_frame.y() == voice_y
    assert overlay._audio_frame.height() == voice_h
    assert overlay.settings._predict.isVisible()
    overlay.settings.close()
    overlay.close()


def test_settings_stays_closed_until_opened(qapp) -> None:
    assert qapp is not None
    overlay = Overlay()
    overlay.show()
    qapp.processEvents()
    assert overlay.settings.objectName() == "settingsDialog"
    assert overlay.settings.isHidden()
    overlay.settings.show()
    qapp.processEvents()
    assert overlay.settings.isVisible()
    overlay.settings.close()
    qapp.processEvents()
    assert overlay.settings.isHidden()
    overlay.close()


def test_phrase_background_follows_text_state(qapp) -> None:
    assert qapp is not None
    overlay = Overlay()
    overlay.show_audio_phrase("")
    empty_bg = overlay._audio_body.styleSheet()
    overlay.show_audio_phrase("Hello there.", state="correcting")
    correcting_bg = overlay._audio_body.styleSheet()
    overlay.show_audio_phrase("Hello there.", state="ready")
    ready_bg = overlay._audio_body.styleSheet()
    assert "rgba(12,12,14,70)" in empty_bg
    assert "rgba(56,46,24,135)" in correcting_bg
    assert "rgba(28,52,36,130)" in ready_bg
    overlay.show_partial("working on this")
    assert "rgba(28,48,72,130)" in overlay._audio_live.styleSheet()
    overlay.close()


def test_voice_hearing_is_microphone_only(qapp) -> None:
    overlay = Overlay()
    overlay.show()
    qapp.processEvents()
    assert overlay._hear_row is not None
    assert overlay._hear_row.isVisible()
    overlay.show_partial("from the microphone")
    assert "microphone" in overlay._audio_live.text().lower()
    overlay.set_meeting_recording(True, "Playback 2026-08-14 1941.md", kind="playback")
    qapp.processEvents()
    assert not overlay._hear_row.isVisible()
    overlay.show_partial("from the speakers")
    assert "speakers" in overlay._meet_live.text().lower()
    assert "speakers" not in overlay._audio_live.text().lower()
    overlay.set_meeting_recording(False)
    qapp.processEvents()
    assert overlay._hear_row.isVisible()
    overlay.set_meeting_recording(True, "Meeting 2026-08-14 1941.md", kind="meeting")
    qapp.processEvents()
    assert not overlay._hear_row.isVisible()
    overlay.close()


def test_header_is_a_single_status_button(qapp) -> None:
    assert qapp is not None
    overlay = Overlay()
    overlay.show()
    qapp.processEvents()
    chrome = overlay.styleSheet()
    assert overlay._enable.objectName() == "micToggle"
    assert isinstance(overlay._enable, QToolButton)
    assert overlay._enable.isCheckable()
    assert overlay._status is overlay._enable
    assert overlay._enable.text() == t("en", "status_off")
    assert not overlay._enable.icon().isNull()
    assert overlay._enable.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonTextBesideIcon
    assert overlay._enable.x() < overlay.width() // 4
    assert not hasattr(overlay, "_brand")
    assert not hasattr(overlay, "_hide_btn")
    assert "QToolButton#micToggle" in chrome
    overlay.set_enable_checked(True)
    overlay.set_status("listening")
    assert overlay._enable.isChecked()
    assert overlay._enable.text() == t("en", "status_listening")
    overlay.close()


def test_human_ai_modes_sit_on_header_row(qapp) -> None:
    assert qapp is not None
    overlay = Overlay()
    overlay.show()
    qapp.processEvents()
    assert overlay.correction_mode() == "human"
    assert overlay._mode_human.isChecked()
    assert overlay._mode_human.text() == t("en", "correct_human")
    assert overlay._mode_ai.text() == t("en", "correct_ai")
    assert not overlay._mode_human.icon().isNull()
    assert not overlay._mode_ai.icon().isNull()
    enable = overlay._enable.mapTo(overlay, overlay._enable.rect().topLeft())
    human = overlay._mode_human.mapTo(overlay, overlay._mode_human.rect().topLeft())
    ai = overlay._mode_ai.mapTo(overlay, overlay._mode_ai.rect().topLeft())
    voice_top = overlay._audio_frame.mapTo(overlay, overlay._audio_frame.rect().topLeft()).y()
    type_top = overlay._typed_frame.mapTo(overlay, overlay._typed_frame.rect().topLeft()).y()
    assert abs(enable.y() - human.y()) <= 8
    assert human.x() > enable.x()
    assert ai.x() > human.x()
    assert overlay._mode_row.mapTo(overlay, overlay._mode_row.rect().bottomLeft()).y() <= voice_top
    assert voice_top < type_top
    assert overlay._typed_frame.findChildren(QToolButton, "modeSeg") == []
    overlay.set_correction_mode("ai")
    assert overlay.correction_mode() == "ai"
    assert overlay._mode_ai.isChecked()
    overlay.close()


def test_header_buttons_are_not_cropped(qapp) -> None:
    overlay = Overlay()
    overlay.show()
    qapp.processEvents()
    box = overlay.rect()
    for widget in (overlay._enable, overlay._mode_human, overlay._mode_ai):
        top_left = widget.mapTo(overlay, widget.rect().topLeft())
        bottom_right = widget.mapTo(overlay, widget.rect().bottomRight())
        assert top_left.y() >= 0
        assert bottom_right.y() <= box.height()
        assert top_left.x() >= 0
        assert bottom_right.x() <= box.width()
    overlay.close()


def test_voice_stays_active_when_type_has_a_phrase(qapp) -> None:
    overlay = Overlay()
    overlay.show_audio_phrase("Spoken sentence.")
    assert overlay._audio_frame.property("active") == "true"
    overlay.show_typed_phrase("Typed sentence.")
    assert overlay._audio_frame.property("active") == "true"
    assert overlay._typed_frame.property("active") == "true"
    assert overlay._audio_frame.objectName() == "voicePanel"
    assert overlay._typed_frame.objectName() == "typePanel"
    overlay.close()


def test_opacity_percent_tracks_slider(qapp) -> None:
    assert qapp is not None
    overlay = Overlay()
    overlay.settings._opacity.setValue(80)
    assert overlay.settings._opacity_value.text() == "80%"
    overlay.settings._opacity.setValue(96)
    assert overlay.settings._opacity_value.text() == "96%"
    overlay.close()


def test_type_clear_and_output_cycle_controls(qapp) -> None:
    assert qapp is not None
    overlay = Overlay()
    overlay.show()
    qapp.processEvents()
    assert not overlay._input._clear.isVisible()
    assert not overlay._audio_cycle.isVisible()
    assert not overlay._typed_cycle.isVisible()
    assert not overlay._audio_translate.isVisible()
    assert not overlay._typed_translate.isVisible()
    overlay.set_typed("Draft sentence.")
    qapp.processEvents()
    assert overlay._input._clear.isVisible()
    overlay._input._clear.click()
    qapp.processEvents()
    assert overlay.typed_text() == ""
    overlay.show_audio_phrase("Hello there.", state="ready")
    assert overlay._audio_cycle.isVisible()
    assert overlay._audio_cycle.isEnabled()
    assert overlay._audio_translate.isVisible()
    assert overlay._audio_translate.isEnabled()
    assert not overlay._typed_cycle.isVisible()
    assert not overlay._typed_translate.isVisible()
    overlay.show_audio_phrase("Hello there.", state="correcting")
    assert overlay._audio_cycle.isVisible()
    assert not overlay._audio_cycle.isEnabled()
    assert overlay._audio_translate.isVisible()
    assert not overlay._audio_translate.isEnabled()
    overlay.close()


def test_translate_icon_sits_under_retry(qapp) -> None:
    overlay = Overlay()
    overlay.show()
    qapp.processEvents()
    overlay.show_audio_phrase("Hello there.", state="ready")
    qapp.processEvents()
    retry = overlay._audio_cycle.mapTo(overlay, overlay._audio_cycle.rect().topLeft())
    trans = overlay._audio_translate.mapTo(overlay, overlay._audio_translate.rect().topLeft())
    assert trans.y() > retry.y()
    assert abs(trans.x() - retry.x()) <= 8
    overlay.set_meeting_recording(True, "Playback 2026-08-14 1941.md", kind="playback")
    qapp.processEvents()
    assert not overlay._audio_translate.isVisible()
    overlay.close()


def test_compact_geometry_matches_current_box(qapp) -> None:
    overlay = Overlay()
    overlay.resize(520, overlay.height())
    box = overlay.compact_geometry()
    assert box.width() == overlay.width()
    assert box.height() == overlay.height()
    overlay.close()


def test_phrase_body_is_three_lines_then_capped(qapp) -> None:
    overlay = Overlay()
    overlay.show()
    qapp.processEvents()
    body = overlay._audio_body
    line = body.fontMetrics().lineSpacing()
    assert body.minimumHeight() >= line * 3
    assert body.maximumHeight() == body.minimumHeight()
    overlay.show_audio_phrase("One. Two. Three. Four. Five long sentences stay in the box.")
    qapp.processEvents()
    assert body.height() == body.minimumHeight()
    overlay.close()


def test_overlay_height_is_locked_to_content(qapp) -> None:
    overlay = Overlay()
    overlay.show()
    qapp.processEvents()
    assert overlay.minimumHeight() == overlay.maximumHeight()
    before = overlay.height()
    overlay.set_meeting_recording(True, "Meeting 2026-08-14 1941.md", kind="meeting")
    qapp.processEvents()
    assert overlay.height() > before
    assert overlay.minimumHeight() == overlay.maximumHeight()
    overlay.set_meeting_recording(False)
    qapp.processEvents()
    assert overlay.height() == overlay.minimumHeight()
    overlay.close()


def test_action_bar_record_and_records_have_tooltips(qapp) -> None:
    overlay = Overlay()
    overlay.show()
    qapp.processEvents()
    assert overlay._records_btn.isVisible()
    assert overlay._record_btn.isVisible()
    assert overlay._history_btn.isVisible()
    assert overlay._copy_btn.isVisible()
    assert overlay._settings_btn.isVisible()
    assert overlay._records_btn.toolTip()
    assert overlay._record_btn.toolTip()
    assert overlay._enable.toolTip()
    assert overlay._status.toolTip()
    overlay.set_meeting_recording(True, "Playback 2026-08-14 1941.md", kind="playback")
    assert overlay._meet_frame.isVisible()
    assert overlay._record_btn.objectName() == "danger"
    overlay.set_meeting_recording(False)
    assert not overlay._meet_frame.isVisible()
    overlay.close()
