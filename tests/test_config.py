from pathlib import Path

from personalclipboard.config import (
    default_settings,
    load_settings,
    save_settings,
    saved_overlay_rect,
)


def test_capture_defaults_off() -> None:
    s = default_settings()
    assert s.preferred_input == "maono"


def test_cuda_whisper_defaults() -> None:
    s = default_settings()
    assert s.whisper_model == "large-v3-turbo"
    assert s.whisper_device == "cuda"
    assert s.compute_type == "float16"
    assert s.condition_on_previous_text is False
    assert s.beam_size_partial == 1
    assert s.beam_size_commit == 3
    assert s.record_window_seconds == 6.0
    assert s.record_hop_ms == 800
    assert s.ring_seconds == 16.0
    assert s.ring_seconds >= s.record_window_seconds * 2


def test_ollama_is_localhost() -> None:
    s = default_settings()
    assert s.ollama_host.startswith("http://127.0.0.1")
    assert s.ollama_model == "qwen2.5:1.5b"
    assert s.hotkey == "<ctrl>+<shift>+a"
    assert s.type_hotkey == "<ctrl>+<shift>+r"
    assert s.vad_enabled is True
    assert s.predict_enabled is True
    assert s.correction_mode == "human"
    assert s.ollama_keep_alive_s == 120
    assert 60 <= s.overlay_opacity <= 100
    assert s.overlay_opacity == 80


def test_load_settings_recovers_from_bad_values(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(
        '{"overlay_opacity": "nope", "ui_language": "xx",'
        ' "vad_silence_ms": 99999, "whisper_model": "",'
        ' "ollama_keep_alive_s": 5, "correction_mode": "robot"}',
        encoding="utf-8",
    )
    loaded = load_settings(path)
    assert loaded.overlay_opacity == 80
    assert loaded.ui_language == "en"
    assert loaded.vad_silence_ms == 8000
    assert loaded.whisper_model == "large-v3-turbo"
    assert loaded.ollama_keep_alive_s == 120
    assert loaded.correction_mode == "human"
    assert loaded.overlay_w == 0
    assert saved_overlay_rect(loaded) is None


def test_opacity_clamped_60_to_100(tmp_path: Path) -> None:
    from personalclipboard.config import shell_alpha

    path = tmp_path / "settings.json"
    path.write_text('{"overlay_opacity": 35}', encoding="utf-8")
    assert load_settings(path).overlay_opacity == 60
    path.write_text('{"overlay_opacity": 100}', encoding="utf-8")
    assert load_settings(path).overlay_opacity == 100
    assert shell_alpha(100) == 255
    assert shell_alpha(60) == int(255 * 0.6)


def test_overlay_geometry_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    settings = load_settings(path)
    settings.ui_language = "fr"
    settings.overlay_opacity = 100
    settings.whisper_model = "turbo"
    settings.ollama_model = "llama3.2:1b"
    settings.vad_enabled = False
    settings.predict_enabled = False
    settings.correction_mode = "ai"
    settings.overlay_x = -80
    settings.overlay_y = 40
    settings.overlay_w = 640
    settings.overlay_h = 360
    settings.enable_capture = True
    save_settings(settings, path)
    raw = path.read_text(encoding="utf-8")
    assert "enable_capture" not in raw
    loaded = load_settings(path)
    assert loaded.ui_language == "fr"
    assert loaded.overlay_opacity == 100
    assert loaded.whisper_model == "turbo"
    assert loaded.ollama_model == "llama3.2:1b"
    assert loaded.vad_enabled is False
    assert loaded.predict_enabled is False
    assert loaded.correction_mode == "ai"
    assert loaded.overlay_x == -80
    assert loaded.overlay_y == 40
    assert loaded.overlay_w == 640
    assert loaded.overlay_h == 360
    assert loaded.enable_capture is False
    assert saved_overlay_rect(loaded) == (-80, 40, 640, 360)


def test_load_settings_drops_removed_ui_languages(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text('{"ui_language": "de"}', encoding="utf-8")
    assert load_settings(path).ui_language == "en"
    path.write_text('{"ui_language": "nl"}', encoding="utf-8")
    assert load_settings(path).ui_language == "en"


def test_saved_overlay_rect_ignores_tiny_size() -> None:
    settings = default_settings()
    settings.overlay_x = 10
    settings.overlay_y = 10
    settings.overlay_w = 200
    settings.overlay_h = 100
    assert saved_overlay_rect(settings) is None
