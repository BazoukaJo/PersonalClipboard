# pylint: disable=protected-access
from personalclipboard.ui.i18n import t
from personalclipboard.ui.overlay import Overlay
from personalclipboard.ui.settings_panel import SettingsPanel


def test_overlay_builds_and_translates(qapp) -> None:
    assert qapp is not None
    overlay = Overlay()
    overlay.apply_language("fr")
    assert overlay._enable.text() == t("fr", "mic")
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
    panel._opacity.setValue(48)
    panel._vad.setChecked(True)
    panel._vad.setChecked(False)
    assert langs == ["fr"]
    assert opacities[-1] == 48
    assert vads == [True, False]
    panel.set_values(
        language="en",
        opacity=35,
        whisper="large-v3-turbo",
        ollama="qwen2.5-coder:1.5b",
        ollama_models=[],
        vad=True,
        predict=True,
    )
    assert langs == ["fr"]
    panel.deleteLater()
