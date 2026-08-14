import time
from pathlib import Path

from personalclipboard.asr.vad import QuietIdle
from personalclipboard.audio.probe import WakeProbe
from personalclipboard.config import Settings, load_settings, save_settings
from personalclipboard.ui.i18n import flash_key, t


def test_quiet_idle_trips_after_enough_silence() -> None:
    idle = QuietIdle(silence_ms=1000)
    assert idle.on_silence(250) is False
    assert idle.on_silence(250) is False
    assert idle.on_silence(250) is False
    assert idle.on_silence(250) is True
    assert idle.idle is True
    assert idle.on_silence(250) is False


def test_quiet_idle_resets_on_voice() -> None:
    idle = QuietIdle(silence_ms=500)
    idle.on_silence(500)
    idle.on_voice()
    assert idle.idle is False
    assert idle.on_silence(400) is False


def test_settings_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    settings = load_settings(path)
    settings.ui_language = "fr"
    settings.overlay_opacity = 70
    settings.vad_enabled = True
    settings.predict_enabled = False
    save_settings(settings, path)
    loaded = load_settings(path)
    assert loaded.ui_language == "fr"
    assert loaded.overlay_opacity == 70
    assert loaded.vad_enabled is True
    assert loaded.predict_enabled is False


def test_i18n_french_mic() -> None:
    assert t("fr", "mic") == "Micro"
    assert t("en", "status_quiet") == "Quiet"
    assert flash_key("Copied") == "flash_copied"
    assert t("fr", flash_key("Copied")) == "Copié"


def test_i18n_languages_cover_english_keys() -> None:
    from personalclipboard.ui.i18n import STRINGS

    english = set(STRINGS["en"])
    for lang in ("fr", "es", "de"):
        missing = english - set(STRINGS[lang])
        assert not missing, f"{lang} missing {sorted(missing)}"


def test_wake_probe_fires_on_loud_peek(monkeypatch) -> None:
    fired: list[bool] = []
    probe = WakeProbe(Settings(), lambda: fired.append(True))
    monkeypatch.setattr("personalclipboard.audio.probe._peek_rms", lambda *_args, **_kw: 0.4)
    probe.start()
    deadline = time.monotonic() + 2
    while not fired and time.monotonic() < deadline:
        time.sleep(0.03)
    probe.stop()
    assert fired


def test_wake_probe_stop_while_quiet(monkeypatch) -> None:
    fired: list[bool] = []
    probe = WakeProbe(Settings(), lambda: fired.append(True))
    monkeypatch.setattr("personalclipboard.audio.probe._peek_rms", lambda *_args, **_kw: 0.0)
    probe.start()
    time.sleep(0.05)
    probe.stop()
    assert probe.active is False
    assert not fired
