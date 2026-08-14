from pathlib import Path

from personalclipboard.config import default_settings, load_settings


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


def test_ollama_is_localhost() -> None:
    s = default_settings()
    assert s.ollama_host.startswith("http://127.0.0.1")
    assert s.ollama_model == "qwen2.5-coder:1.5b"
    assert s.hotkey == "<ctrl>+<shift>+a"
    assert s.type_hotkey == "<ctrl>+<shift>+r"
    assert s.vad_enabled is True
    assert s.predict_enabled is True
    assert 15 <= s.overlay_opacity <= 80


def test_load_settings_recovers_from_bad_values(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(
        '{"overlay_opacity": "nope", "ui_language": "xx",'
        ' "vad_silence_ms": 99999, "whisper_model": ""}',
        encoding="utf-8",
    )
    loaded = load_settings(path)
    assert loaded.overlay_opacity == 35
    assert loaded.ui_language == "en"
    assert loaded.vad_silence_ms == 8000
    assert loaded.whisper_model == "large-v3-turbo"
