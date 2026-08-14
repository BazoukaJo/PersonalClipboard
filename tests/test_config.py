"""Phase 1 tests: config defaults only. No GPU or microphone."""

from personalclipboard.config import default_settings


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
