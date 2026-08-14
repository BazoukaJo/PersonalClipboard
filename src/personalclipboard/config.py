"""Runtime defaults. Capture starts OFF (privacy); models match the PRD."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Process-wide settings. Enable capture is the master kill switch."""

    enable_capture: bool = False
    sample_rate: int = 16_000
    frame_ms: int = 20
    window_seconds: float = 2.0
    hop_ms: int = 250
    whisper_model: str = "large-v3-turbo"
    whisper_device: str = "cuda"
    compute_type: str = "float16"
    beam_size_partial: int = 1
    beam_size_commit: int = 3
    condition_on_previous_text: bool = False
    ollama_host: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5-coder:1.5b"
    ollama_timeout_s: float = 8.0
    hotkey: str = "<ctrl>+<shift>+a"
    persist_audio: bool = False
    preferred_input: str = "maono"
    ring_seconds: float = 8.0
    no_speech_prob_max: float = 0.65
    avg_logprob_min: float = -1.2
    min_commit_chars: int = 2


def default_settings() -> Settings:
    return Settings()
