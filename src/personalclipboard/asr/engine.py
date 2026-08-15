"""Resident CUDA Faster-Whisper. Partials → overlay; commits → LLM queue."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

import numpy as np

from personalclipboard.asr.assembler import SentenceAssembler
from personalclipboard.asr.commands import match_command
from personalclipboard.asr.vad import QuietIdle
from personalclipboard.asr.voice_gate import VoiceGate
from personalclipboard.audio.capture import RingBuffer
from personalclipboard.audio.mix import mix_windows
from personalclipboard.config import Settings

_RECORD_ENERGY_MIN = 0.0015


class AsrEngine:
    """Overlapping windows on a worker thread. Never call from PortAudio or Qt."""

    def __init__(
        self,
        settings: Settings,
        ring: RingBuffer,
        on_partial: Callable[[str], None] | None = None,
        on_commit: Callable[[str], None] | None = None,
        on_status: Callable[[str], None] | None = None,
        on_error: Callable[[str], None] | None = None,
        on_command: Callable[[str], None] | None = None,
        on_vad_idle: Callable[[], None] | None = None,
    ) -> None:
        self._settings = settings
        self._ring = ring
        self._loop_ring: RingBuffer | None = None
        self._on_partial = on_partial
        self._on_commit = on_commit
        self._on_status = on_status
        self._on_error = on_error
        self._on_command = on_command
        self._on_vad_idle = on_vad_idle
        self._model = None
        self._load_error: str | None = None
        self._enabled = threading.Event()
        self._shutdown = threading.Event()
        self._thread: threading.Thread | None = None
        self._assembler = SentenceAssembler(min_chars=settings.min_commit_chars)
        self._gate = VoiceGate()
        self._quiet = QuietIdle(settings.vad_silence_ms)
        self._last_command: str | None = None
        self._last_command_at = 0.0
        self._record_mode = ""
        self._state_lock = threading.Lock()

    def set_loop_ring(self, ring: RingBuffer | None) -> None:
        """Second ring mixed in during Meeting Record (speaker loopback)."""
        self._loop_ring = ring

    @property
    def ready(self) -> bool:
        return self._model is not None

    @property
    def running(self) -> bool:
        return self._enabled.is_set() and not self._shutdown.is_set()

    @property
    def load_error(self) -> str | None:
        return self._load_error

    def load(self) -> None:
        """Load the configured Faster-Whisper model and keep weights on CUDA."""
        try:
            from personalclipboard.asr.cuda_runtime import configure_cuda12_dlls
            from faster_whisper import WhisperModel

            configure_cuda12_dlls()

            self._model = WhisperModel(
                self._settings.whisper_model,
                device=self._settings.whisper_device,
                compute_type=self._settings.compute_type,
            )
            self._load_error = None
        except Exception as exc:
            self._model = None
            self._load_error = str(exc)
            if self._on_error:
                self._on_error(f"ASR load failed: {exc}")

    def set_record_mode(self, mode: str) -> None:
        """None/empty = dictation. meeting = mic+speakers. playback = speakers only."""
        normalized = mode if mode in ("meeting", "playback") else ""
        with self._state_lock:
            self._record_mode = normalized
            self._assembler.set_pause_commit(bool(normalized))
            self._assembler.reset()
            self._gate.reset()
            self._quiet.reset()
            self._last_command = None

    def set_meeting_mode(self, enabled: bool) -> None:
        """Meeting notes: all speakers, pause commits, no voice commands."""
        self.set_record_mode("meeting" if enabled else "")

    def flush_remainder(self) -> str:
        with self._state_lock:
            return self._assembler.take_remainder()

    def start(self) -> None:
        """Run the hop loop while Mic is ON."""
        if self._model is None:
            raise RuntimeError(self._load_error or "Whisper model is not loaded")
        with self._state_lock:
            self._assembler.reset()
            self._last_command = None
            self._last_command_at = 0.0
            self._quiet.reset()
            self._quiet.silence_ms = self._settings.vad_silence_ms
        self._enabled.set()
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._loop, name="asr-worker", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        """Idle the worker; do not transcribe after enable OFF."""
        self._enabled.clear()
        with self._state_lock:
            self._assembler.reset()
            self._last_command = None
            self._quiet.reset()
        self._gate.reset()

    def shutdown(self) -> None:
        self.stop()
        self._shutdown.set()
        self._enabled.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _loop(self) -> None:
        while not self._shutdown.is_set():
            if not self._enabled.wait(timeout=0.2):
                continue
            if self._shutdown.is_set() or not self._enabled.is_set():
                continue
            deadline = time.perf_counter() + self._hop_seconds()
            try:
                self._tick()
            except Exception as exc:
                if self._on_error:
                    self._on_error(f"ASR: {exc}")
            remaining = deadline - time.perf_counter()
            _idle_remaining(remaining, self._enabled, self._shutdown)

    def _hop_seconds(self) -> float:
        with self._state_lock:
            recording = bool(self._record_mode)
        hop_ms = self._settings.record_hop_ms if recording else self._settings.hop_ms
        return max(hop_ms, 50) / 1000.0

    def _window_seconds(self) -> float:
        with self._state_lock:
            recording = bool(self._record_mode)
        if recording:
            return max(self._settings.record_window_seconds, self._settings.window_seconds)
        return self._settings.window_seconds

    def _tick(self) -> None:
        model = self._model
        if model is None or not self._enabled.is_set():
            return
        seconds = self._window_seconds()
        rate = self._settings.sample_rate
        audio = self._ring.window_float32(seconds, rate)
        min_samples = int(rate * 0.2)
        mode = self._record_mode
        if mode == "playback" and self._loop_ring is not None:
            audio = self._loop_ring.window_float32(seconds, rate)
        elif mode == "meeting" and self._loop_ring is not None:
            loop = self._loop_ring.window_float32(seconds, rate)
            audio = mix_windows(audio, loop)
        if audio.size < min_samples:
            return
        recording = bool(mode)
        if recording:
            energy = float(np.sqrt(np.mean(np.square(audio.astype(np.float64)))))
            if energy < _RECORD_ENERGY_MIN:
                self._finish_tick("", 1.0, 0.0, audio)
                return
        elif not self._voice_ok(audio):
            return
        beam = self._settings.beam_size_commit if recording else self._settings.beam_size_partial
        text, no_speech, avg_lp = _transcribe(
            model,
            audio,
            beam_size=beam,
            condition_on_previous_text=self._settings.condition_on_previous_text,
        )
        if not recording:
            command = match_command(text)
            if command:
                self._emit_command(command)
                return
        self._finish_tick(text, no_speech, avg_lp, audio)

    def _voice_ok(self, audio: np.ndarray) -> bool:
        verdict = self._gate.classify(audio, self._settings.sample_rate)
        if verdict == "silence":
            if self._settings.vad_enabled and self._quiet.on_silence(self._settings.hop_ms):
                if self._on_status:
                    self._on_status("quiet")
                if self._on_vad_idle:
                    self._on_vad_idle()
                return False
            if self._on_status:
                self._on_status("locked" if self._gate.enrolled else "listening")
            return False
        self._quiet.on_voice()
        if verdict == "reject_other":
            if self._on_status:
                self._on_status("uncertain")
            if self._on_partial:
                self._on_partial("")
            return False
        return True

    def _finish_tick(self, text: str, no_speech: float, avg_lp: float, audio: np.ndarray) -> None:
        with self._state_lock:
            recording = bool(self._record_mode)
            partial, commit, status = self._assembler.update(
                text,
                no_speech,
                avg_lp,
                no_speech_max=self._settings.no_speech_prob_max,
                logprob_min=self._settings.avg_logprob_min,
            )
        if recording and status == "listening":
            status = "recording"
        elif self._gate.enrolled and status == "listening":
            status = "locked"
        if self._on_status:
            self._on_status(status)
        if self._on_partial:
            self._on_partial(partial)
        if status == "uncertain" or not commit:
            return
        if not recording:
            command = match_command(commit)
            if command:
                self._emit_command(command)
                return
            self._gate.enroll(audio, self._settings.sample_rate)
        if self._on_commit:
            self._on_commit(commit)

    def _emit_command(self, command: str) -> None:
        now = time.monotonic()
        if command == self._last_command and (now - self._last_command_at) < 1.2:
            return  # overlapping hops repeat the same spoken command
        self._last_command = command
        self._last_command_at = now
        self._assembler.reset()
        if self._on_partial:
            self._on_partial("")
        if self._on_command:
            self._on_command(command)


def _idle_remaining(remaining: float, enabled: threading.Event, shutdown: threading.Event) -> None:
    end = time.perf_counter() + remaining
    while remaining > 0:
        if not enabled.is_set() or shutdown.is_set():
            return
        time.sleep(min(0.02, remaining))
        remaining = end - time.perf_counter()


def _transcribe(
    model,
    audio: np.ndarray,
    *,
    beam_size: int,
    condition_on_previous_text: bool,
) -> tuple[str, float, float]:
    # condition_on_previous_text=False: overlapping windows must not inherit prior text.
    # vad_filter=False: this process owns VAD (QuietIdle + VoiceGate).
    segments, _info = model.transcribe(
        audio,
        beam_size=beam_size,
        condition_on_previous_text=condition_on_previous_text,
        vad_filter=False,
        without_timestamps=True,
    )
    parts: list[str] = []
    no_speech = 0.0
    logprobs: list[float] = []
    for seg in segments:
        if seg.text:
            parts.append(seg.text.strip())
        no_speech = max(no_speech, float(getattr(seg, "no_speech_prob", 0.0) or 0.0))
        lp = getattr(seg, "avg_logprob", None)
        if lp is not None:
            logprobs.append(float(lp))
    avg_lp = float(sum(logprobs) / len(logprobs)) if logprobs else 0.0
    return " ".join(parts).strip(), no_speech, avg_lp
