"""Short blocking peeks so VAD can stop the streaming mic and still wake on speech."""

from __future__ import annotations

import threading
from collections.abc import Callable

import numpy as np
import pyaudio
import sounddevice as sd

from personalclipboard.config import Settings


class WakeProbe:
    """Opens the mic in short bursts. Not used while the streaming capture is active."""

    def __init__(self, settings: Settings, on_speech: Callable[[], None]) -> None:
        self._settings = settings
        self._on_speech = on_speech
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.min_rms = 0.018

    @property
    def active(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.active:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="vad-probe", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.5)
            self._thread = None

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                rms = _peek_rms(
                    self._settings.sample_rate,
                    0.08,
                    self._settings.input_device_name,
                )
            except Exception:
                if self._stop.wait(0.35):
                    return
                continue
            if rms >= self.min_rms:
                self._on_speech()
                return
            if self._stop.wait(0.18):
                return


def _peek_rms(sample_rate: int, seconds: float, preferred: str = "") -> float:
    frames = max(int(sample_rate * seconds), 256)
    try:
        return _peek_sounddevice(sample_rate, frames, preferred)
    except Exception:
        return _peek_pyaudio(sample_rate, frames, preferred)


def _peek_sounddevice(sample_rate: int, frames: int, preferred: str = "") -> float:
    kwargs: dict = {
        "samplerate": sample_rate,
        "channels": 1,
        "dtype": "float32",
        "blocking": True,
    }
    index = _sd_input_index(preferred)
    if index is not None:
        kwargs["device"] = index
    audio = sd.rec(frames, **kwargs)
    if audio is None or audio.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(audio.astype(np.float64)))))


def _sd_input_index(preferred: str) -> int | None:
    if not preferred.strip():
        return None
    from personalclipboard.audio.capture import _ranked_sd_devices

    for index, label in _ranked_sd_devices(preferred):
        return index
    return None


def _peek_pyaudio(sample_rate: int, frames: int, preferred: str = "") -> float:
    pa = pyaudio.PyAudio()
    stream = None
    try:
        kwargs: dict = {
            "format": pyaudio.paInt16,
            "channels": 1,
            "rate": sample_rate,
            "input": True,
            "frames_per_buffer": frames,
        }
        from personalclipboard.audio.capture import _ranked_input_devices

        ranked = _ranked_input_devices(pa, preferred)
        if ranked:
            kwargs["input_device_index"] = ranked[0][0]
        stream = pa.open(**kwargs)
        raw = stream.read(frames, exception_on_overflow=False)
        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        if samples.size == 0:
            return 0.0
        return float(np.sqrt(np.mean(np.square(samples.astype(np.float64)))))
    finally:
        if stream is not None:
            try:
                stream.stop_stream()
                stream.close()
            except Exception:
                pass
        pa.terminate()
