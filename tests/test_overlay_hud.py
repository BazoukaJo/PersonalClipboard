# pylint: disable=protected-access
from PyQt6.QtCore import QEventLoop, QTimer

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
    assert overlay._enable.text() == t("fr", "mic")
    assert overlay._brand.text() == t("fr", "app_title")
    assert overlay._history_btn.text() == t("fr", "history")
    overlay.apply_language("de")
    assert overlay._hide_btn.text() == t("de", "hide")
    overlay.set_opacity(60)
    overlay.set_status("quiet")
    assert overlay._status_key == "quiet"
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


def test_opening_settings_grows_overlay(qapp) -> None:
    assert qapp is not None
    overlay = Overlay()
    overlay.show()
    qapp.processEvents()
    before_h = overlay.height()
    before_w = overlay.width()
    voice_y = overlay._audio_frame.y()
    voice_h = overlay._audio_frame.height()
    extra = overlay.settings.extra_open_height()
    type_gap = overlay._typed_frame.y() - overlay._audio_frame.geometry().bottom()
    overlay.settings._toggle.click()
    _flush_qt(qapp)
    screen = overlay.screen()
    avail_h = screen.availableGeometry().height() if screen is not None else overlay.height()
    need = before_h + extra
    assert overlay.height() > before_h
    assert overlay.height() >= min(need, avail_h)
    assert overlay.width() >= before_w
    assert overlay._audio_frame.y() == voice_y
    assert overlay._audio_frame.height() == voice_h
    assert overlay._typed_frame.y() - overlay._audio_frame.geometry().bottom() == type_gap
    assert overlay.settings._predict.isVisible()
    header_bottom = overlay.settings._toggle.mapTo(
        overlay, overlay.settings._toggle.rect().bottomRight()
    ).y()
    lang_top = overlay.settings._lang_box.mapTo(
        overlay, overlay.settings._lang_box.rect().topLeft()
    ).y()
    assert lang_top >= header_bottom
    whisper_top = overlay.settings._whisper.mapTo(
        overlay, overlay.settings._whisper.rect().topLeft()
    ).y()
    lang_bottom = overlay.settings._lang_box.mapTo(
        overlay, overlay.settings._lang_box.rect().bottomRight()
    ).y()
    assert whisper_top - lang_bottom >= 10
    if overlay.height() >= need:
        predict_bottom = overlay.settings._predict.mapTo(
            overlay, overlay.settings._predict.rect().bottomRight()
        ).y()
        assert predict_bottom <= overlay.height() - 8
    else:
        assert overlay.settings._scroll.height() < overlay.settings.natural_body_height()
    overlay.settings._toggle.click()
    _flush_qt(qapp)
    assert abs(overlay.height() - before_h) <= 8
    assert abs(overlay.width() - before_w) <= 8
    overlay.close()


def test_settings_stays_a_button_until_opened(qapp) -> None:
    assert qapp is not None
    overlay = Overlay()
    overlay.show()
    qapp.processEvents()
    assert overlay.settings.objectName() == "settingsDock"
    assert overlay.settings._header.isHidden()
    assert not overlay.settings._scroll.isVisible()
    overlay.settings._toggle.click()
    qapp.processEvents()
    assert overlay.settings.objectName() == "panel"
    assert overlay.settings._header.isVisible()
    assert overlay.settings._scroll.isVisible()
    overlay.settings._toggle.click()
    qapp.processEvents()
    assert overlay.settings.objectName() == "settingsDock"
    assert not overlay.settings._scroll.isVisible()
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


def test_mic_dot_follows_listen_state(qapp) -> None:
    assert qapp is not None
    overlay = Overlay()
    chrome = overlay.styleSheet()
    assert overlay._enable.objectName() == "micToggle"
    assert "#c4453c" in chrome
    assert "#9a9aa0" in chrome
    assert "#2faf5a" in chrome
    overlay.set_enable_checked(False)
    overlay.set_status("off")
    assert overlay._enable.property("mic") == "off"
    overlay.set_enable_checked(True)
    overlay.set_status("quiet")
    assert overlay._enable.property("mic") == "wait"
    overlay.set_status("listening")
    assert overlay._enable.property("mic") == "live"
    overlay.set_enable_checked(False)
    overlay.set_status("recording")
    assert overlay._enable.property("mic") == "off"
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
    overlay.set_typed("Draft sentence.")
    qapp.processEvents()
    assert overlay._input._clear.isVisible()
    overlay._input._clear.click()
    qapp.processEvents()
    assert overlay.typed_text() == ""
    overlay.show_audio_phrase("Hello there.", state="ready")
    assert overlay._audio_cycle.isVisible()
    assert overlay._audio_cycle.isEnabled()
    assert not overlay._typed_cycle.isVisible()
    overlay.show_audio_phrase("Hello there.", state="correcting")
    assert overlay._audio_cycle.isVisible()
    assert not overlay._audio_cycle.isEnabled()
    overlay.close()
