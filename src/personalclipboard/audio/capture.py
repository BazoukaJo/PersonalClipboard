"""PyAudio WASAPI → lock-free ring buffer. Callback copies PCM only."""

from __future__ import annotations

import numpy as np
import pyaudio

from personalclipboard.config import Settings


class RingBuffer:
    """Fixed-size int16 PCM ring. Callback writes; ASR copies a window."""

    def __init__(self, sample_rate: int, seconds: float) -> None:
        self._n = max(int(sample_rate * seconds), sample_rate)
        self._data = np.zeros(self._n, dtype=np.int16)
        self._write = 0

    def write(self, pcm: bytes) -> None:
        if not pcm:
            return
        samples = np.frombuffer(pcm, dtype=np.int16)
        n = int(samples.size)
        if n == 0:
            return
        if n > self._n:
            samples = samples[-self._n :]
            n = self._n
        idx = self._write % self._n
        first = min(n, self._n - idx)
        self._data[idx : idx + first] = samples[:first]
        rest = n - first
        if rest:
            self._data[:rest] = samples[first:]
        self._write += n

    def clear(self) -> None:
        self._write = 0
        self._data.fill(0)

    def samples_available(self) -> int:
        return min(self._write, self._n)

    def window_float32(self, seconds: float, sample_rate: int) -> np.ndarray:
        need = int(seconds * sample_rate)
        available = self.samples_available()
        if available <= 0:
            return np.zeros(0, dtype=np.float32)
        need = min(need, available)
        end = self._write
        start = end - need
        out = np.empty(need, dtype=np.int16)
        start_idx = start % self._n
        first = min(need, self._n - start_idx)
        out[:first] = self._data[start_idx : start_idx + first]
        rest = need - first
        if rest:
            out[first:] = self._data[:rest]
        return out.astype(np.float32) / 32768.0


class AudioCapture:
    """Owns the PortAudio stream. Enable OFF must stop the stream."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self.ring = RingBuffer(settings.sample_rate, settings.ring_seconds)
        self._pa: pyaudio.PyAudio | None = None
        self._stream: pyaudio.Stream | None = None
        self.device_name: str = ""

    @property
    def active(self) -> bool:
        if self._stream is None:
            return False
        try:
            return bool(self._stream.is_active())
        except Exception:
            return False

    def start(self) -> None:
        """Open 16 kHz mono; callback writes the ring buffer only."""
        if self.active:
            return
        frame_samples = max(int(self._settings.sample_rate * self._settings.frame_ms / 1000), 1)
        if self._pa is None:
            self._pa = pyaudio.PyAudio()
        candidates = _ranked_input_devices(self._pa, self._settings.preferred_input)
        last_error: Exception | None = None
        self._stream = None
        for index, label in candidates:
            kwargs: dict = {
                "format": pyaudio.paInt16,
                "channels": 1,
                "rate": self._settings.sample_rate,
                "input": True,
                "input_device_index": index,
                "frames_per_buffer": frame_samples,
                "stream_callback": self._callback,
                "start": False,
            }
            try:
                self._stream = self._pa.open(**kwargs)
                self._stream.start_stream()
                self.device_name = label
                return
            except Exception as exc:
                last_error = exc
                self._stream = None
                continue
        if last_error is not None:
            raise OSError(f"No usable microphone: {last_error}") from last_error
        raise OSError("No input devices found. Set a default microphone in Windows Sound settings.")

    def stop(self) -> None:
        """Stop the stream so the callback no longer runs (privacy kill switch)."""
        stream = self._stream
        self._stream = None
        if stream is not None:
            try:
                stream.stop_stream()
            except Exception:
                pass
            try:
                stream.close()
            except Exception:
                pass

    def close(self) -> None:
        self.stop()
        if self._pa is not None:
            self._pa.terminate()
            self._pa = None

    def _callback(self, in_data: bytes | None, _frame_count: int, _time_info: dict, _status: int):
        if in_data:
            self.ring.write(in_data)
        return (None, pyaudio.paContinue)


def _ranked_input_devices(pa: pyaudio.PyAudio, preferred: str) -> list[tuple[int, str]]:
    """Prefer the Maono (or `preferred`) mic. Windows often has no default input."""
    ranked: list[tuple[int, int, str]] = []
    for i in range(pa.get_device_count()):
        info = pa.get_device_info_by_index(i)
        if int(info.get("maxInputChannels") or 0) < 1:
            continue
        name = str(info.get("name") or f"device {i}")
        api = pa.get_host_api_info_by_index(int(info.get("hostApi") or 0))
        host_api = str(api.get("name") or "")
        score = _score_device(name, host_api, preferred)
        ranked.append((score, i, name))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [(index, name) for _score, index, name in ranked]


def _score_device(name: str, host_api: str, preferred: str) -> int:
    lower = name.lower()
    api = host_api.lower()
    score = 0
    needle = preferred.strip().lower()
    if needle and needle in lower:
        score += 100
    if "maono" in lower:
        score += 40
    if "wasapi" in api:
        score += 15
    elif "wdm" in api or "kernel" in api:
        score += 10
    if "sound mapper" in lower or "primary sound capture" in lower:
        score -= 40
    if "headset" in lower or "hands-free" in lower:
        score -= 8
    if "line" in lower or "analog" in lower or "spdif" in lower:
        score -= 20
    if "webcam" in lower:
        score -= 15
    return score
