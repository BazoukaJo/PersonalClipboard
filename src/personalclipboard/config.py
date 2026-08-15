"""Runtime defaults and LOCALAPPDATA persistence."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path

WHISPER_CHOICES = (
    "large-v3-turbo",
    "turbo",
    "large-v3",
    "medium",
    "small",
    "base",
)

OLLAMA_CHOICES = (
    "qwen2.5:1.5b",
    "qwen2.5:3b",
    "llama3.2:1b",
    "llama3.2:3b",
    "qwen2.5-coder:1.5b",
)

OPACITY_MIN = 60
OPACITY_MAX = 100
OPACITY_DEFAULT = 80
OVERLAY_MIN_W = 440
OVERLAY_MIN_H = 220

# HUD prefs and overlay placement. Mic enable is never written — each launch
# starts capture-off until Whisper is ready, then the overlay turns Mic on.
_PERSIST = (
    "ui_language",
    "overlay_opacity",
    "whisper_model",
    "ollama_model",
    "vad_enabled",
    "vad_silence_ms",
    "predict_enabled",
    "correction_mode",
    "overlay_x",
    "overlay_y",
    "overlay_w",
    "overlay_h",
)


@dataclass
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
    condition_on_previous_text: bool = False  # overlapping windows must not inherit text
    ollama_host: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:1.5b"
    ollama_timeout_s: float = 8.0
    ollama_keep_alive_s: int = 120  # Ollama unloads sooner unless each call sets this
    hotkey: str = "<ctrl>+<shift>+a"
    type_hotkey: str = "<ctrl>+<shift>+r"
    persist_audio: bool = False  # debug WAV only; never default on
    preferred_input: str = "maono"
    ring_seconds: float = 8.0
    no_speech_prob_max: float = 0.65
    avg_logprob_min: float = -1.2
    min_commit_chars: int = 2
    ui_language: str = "en"
    overlay_opacity: int = OPACITY_DEFAULT
    vad_enabled: bool = True
    vad_silence_ms: int = 1500
    predict_enabled: bool = True
    predict_timeout_s: float = 3.0
    correction_mode: str = "human"
    overlay_x: int = 0
    overlay_y: int = 0
    overlay_w: int = 0
    overlay_h: int = 0


def default_settings() -> Settings:
    return Settings()


def load_settings(path: Path | None = None) -> Settings:
    settings = Settings()
    target = path or settings_path()
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return settings
    if not isinstance(raw, dict):
        return settings
    allowed = {item.name for item in fields(Settings)}
    for key, value in raw.items():
        if key in allowed:
            setattr(settings, key, value)
    settings.overlay_opacity = _clamp_int(
        settings.overlay_opacity, OPACITY_MIN, OPACITY_MAX, OPACITY_DEFAULT
    )
    settings.vad_silence_ms = _clamp_int(settings.vad_silence_ms, 400, 8000, 1500)
    settings.ollama_keep_alive_s = _clamp_int(settings.ollama_keep_alive_s, 120, 3600, 120)
    if settings.ui_language not in ("en", "fr", "es"):
        settings.ui_language = "en"
    if not isinstance(settings.vad_enabled, bool):
        settings.vad_enabled = bool(settings.vad_enabled)
    if not isinstance(settings.predict_enabled, bool):
        settings.predict_enabled = bool(settings.predict_enabled)
    if settings.correction_mode not in ("human", "ai"):
        settings.correction_mode = "human"
    if not isinstance(settings.whisper_model, str) or not settings.whisper_model.strip():
        settings.whisper_model = "large-v3-turbo"
    if not isinstance(settings.ollama_model, str) or not settings.ollama_model.strip():
        settings.ollama_model = "qwen2.5:1.5b"
    settings.overlay_x = _clamp_int(settings.overlay_x, -100_000, 100_000, 0)
    settings.overlay_y = _clamp_int(settings.overlay_y, -100_000, 100_000, 0)
    settings.overlay_w = _clamp_int(settings.overlay_w, 0, 10_000, 0)
    settings.overlay_h = _clamp_int(settings.overlay_h, 0, 10_000, 0)
    return settings


def saved_overlay_rect(settings: Settings) -> tuple[int, int, int, int] | None:
    """Last collapsed HUD box, or None on first launch / corrupt size."""
    width = settings.overlay_w
    height = settings.overlay_h
    if width < OVERLAY_MIN_W or height < OVERLAY_MIN_H:
        return None
    return (settings.overlay_x, settings.overlay_y, width, height)


def _clamp_int(value: object, low: int, high: int, default: int) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, parsed))


def save_settings(settings: Settings, path: Path | None = None) -> None:
    target = path or settings_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {key: asdict(settings)[key] for key in _PERSIST}
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def settings_path() -> Path:
    return data_dir() / "settings.json"


def history_path() -> Path:
    return data_dir() / "history.txt"


def data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_RUNTIME_DIR")
    path = Path(base) / "PersonalClipboard" if base else Path.home() / ".personalclipboard"
    path.mkdir(parents=True, exist_ok=True)
    return path


def shell_alpha(opacity_pct: int) -> int:
    pct = max(OPACITY_MIN, min(OPACITY_MAX, opacity_pct))
    return int(255 * (pct / 100.0))
