"""PyAudio WASAPI → lock-free ring buffer. Callback copies PCM only."""

from __future__ import annotations

from typing import Any

import numpy as np
import pyaudio

from personalclipboard.audio.devices import names_match
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
    """Owns the input stream. Enable OFF must stop the stream."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self.ring = RingBuffer(settings.sample_rate, settings.ring_seconds)
        self.loop_ring = RingBuffer(settings.sample_rate, settings.ring_seconds)
        self._pa: pyaudio.PyAudio | None = None
        self._stream: pyaudio.Stream | None = None
        self._sd_stream: Any = None
        self._loopback: Any = None
        self.device_name: str = ""
        self.loopback_name: str = ""
        self.backend: str = ""

    @property
    def active(self) -> bool:
        if self._sd_stream is not None:
            try:
                return bool(getattr(self._sd_stream, "active", False))
            except Exception:
                return False
        if self._stream is None:
            return False
        try:
            return bool(self._stream.is_active())
        except Exception:
            return False

    @property
    def loopback_active(self) -> bool:
        loop = self._loopback
        return loop is not None and bool(getattr(loop, "active", False))

    def start_loopback(self) -> bool:
        """Capture speaker/headphone output. Meeting Record only; never persist."""
        if self.loopback_active:
            return True
        from personalclipboard.audio.loopback import LoopbackCapture

        capture = LoopbackCapture(
            self.loop_ring,
            self._settings.sample_rate,
            device_id=self._settings.output_device_id,
        )
        try:
            self.loop_ring.clear()
            capture.start()
        except Exception:
            self._loopback = None
            self.loopback_name = ""
            return False
        self._loopback = capture
        self.loopback_name = capture.device_name
        return True

    def stop_loopback(self) -> None:
        loop = self._loopback
        self._loopback = None
        self.loopback_name = ""
        if loop is not None:
            try:
                loop.stop()
            except Exception:
                pass
        self.loop_ring.clear()

    def start(self) -> None:
        """Open 16 kHz mono; callback writes the ring buffer only."""
        if self.active:
            return
        py_error: Exception | None = None
        try:
            self._start_pyaudio()
            return
        except Exception as exc:
            py_error = exc
            self.stop()
        try:
            self._start_sounddevice()
        except Exception as sd_error:
            detail = f"PyAudio: {py_error}; sounddevice: {sd_error}"
            raise OSError(f"No usable microphone ({detail})") from sd_error

    def stop(self) -> None:
        """Stop the microphone stream. Record loopback is stopped separately."""
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
        sd_stream = self._sd_stream
        self._sd_stream = None
        if sd_stream is not None:
            try:
                sd_stream.stop()
            except Exception:
                pass
            try:
                sd_stream.close()
            except Exception:
                pass
        self.backend = ""

    def close(self) -> None:
        self.stop_loopback()
        self.stop()
        if self._pa is not None:
            self._pa.terminate()
            self._pa = None

    def _start_pyaudio(self) -> None:
        frame_samples = max(int(self._settings.sample_rate * self._settings.frame_ms / 1000), 1)
        if self._pa is None:
            self._pa = pyaudio.PyAudio()
        candidates = _ranked_input_devices(self._pa, self._input_needle())
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
                self.backend = "pyaudio"
                return
            except Exception as exc:
                last_error = exc
                self._stream = None
                continue
        if last_error is not None:
            raise OSError(f"No usable microphone: {last_error}") from last_error
        raise OSError("No input devices found. Set a default microphone in Windows Sound settings.")

    def _start_sounddevice(self) -> None:
        import sounddevice as sd

        frame_samples = max(int(self._settings.sample_rate * self._settings.frame_ms / 1000), 1)
        last_error: Exception | None = None
        for index, label in _ranked_sd_devices(self._input_needle()):
            try:
                stream = sd.InputStream(
                    samplerate=self._settings.sample_rate,
                    channels=1,
                    dtype="float32",
                    blocksize=frame_samples,
                    device=index,
                    callback=self._sd_callback,
                )
                stream.start()
                self._sd_stream = stream
                self.device_name = label
                self.backend = "sounddevice"
                return
            except Exception as exc:
                last_error = exc
                self._sd_stream = None
        if last_error is not None:
            raise OSError(f"sounddevice failed: {last_error}") from last_error
        raise OSError("sounddevice found no input devices.")

    def _callback(self, in_data: bytes | None, _frame_count: int, _time_info: dict, _status: int):
        # PortAudio realtime path: copy samples only — no locks, GPU, or Qt.
        if in_data:
            self.ring.write(in_data)
        return (None, pyaudio.paContinue)

    def _sd_callback(self, indata, _frames: int, _time_info: object, _status: object) -> None:
        # Same contract as PortAudio: convert and copy into the ring, return.
        if indata is None or getattr(indata, "size", 0) == 0:
            return
        mono = indata[:, 0] if getattr(indata, "ndim", 1) > 1 else indata
        pcm = np.clip(np.asarray(mono) * 32767.0, -32768, 32767).astype(np.int16).tobytes()
        self.ring.write(pcm)

    def _input_needle(self) -> str:
        named = self._settings.input_device_name.strip()
        if named:
            return named
        return self._settings.preferred_input


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


def _ranked_sd_devices(preferred: str) -> list[tuple[int, str]]:
    import sounddevice as sd

    ranked: list[tuple[int, int, str]] = []
    host_names = []
    try:
        host_names = [str(item.get("name") or "") for item in sd.query_hostapis()]
    except Exception:
        host_names = []
    try:
        devices = sd.query_devices()
    except Exception:
        return []
    for index, info in enumerate(devices):
        if int(info.get("max_input_channels") or 0) < 1:
            continue
        name = str(info.get("name") or f"device {index}")
        api_index = int(info.get("hostapi") or 0)
        host_api = host_names[api_index] if 0 <= api_index < len(host_names) else ""
        ranked.append((_score_device(name, host_api, preferred), index, name))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [(index, name) for _score, index, name in ranked]


def _score_device(name: str, host_api: str, preferred: str) -> int:
    lower = name.lower()
    api = host_api.lower()
    score = 0
    needle = preferred.strip()
    if needle and names_match(name, needle):
        score += 200
    elif needle and needle.lower() in lower:
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
