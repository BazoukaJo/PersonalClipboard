from personalclipboard.audio.capture import RingBuffer
from personalclipboard.audio.loopback import E_COMMUNICATIONS, E_CONSOLE, render_device_roles
from personalclipboard.asr.engine import AsrEngine
from personalclipboard.config import default_settings


def test_loopback_prefers_console_device_for_video() -> None:
    roles = render_device_roles()
    assert roles[0] == E_CONSOLE
    assert E_COMMUNICATIONS in roles


def test_record_mode_uses_longer_window() -> None:
    settings = default_settings()
    ring = RingBuffer(settings.sample_rate, settings.ring_seconds)
    engine = AsrEngine(settings, ring)
    assert engine._window_seconds() == settings.window_seconds
    engine.set_record_mode("playback")
    assert engine._window_seconds() == settings.record_window_seconds
    assert engine._hop_seconds() == settings.record_hop_ms / 1000.0
    engine.set_record_mode("")
    assert engine._window_seconds() == settings.window_seconds
