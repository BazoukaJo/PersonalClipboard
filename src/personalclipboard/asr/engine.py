"""Resident CUDA Faster-Whisper. Partials → overlay; commits → LLM queue."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

import numpy as np

from personalclipboard.asr.assembler import SentenceAssembler
from personalclipboard.asr.commands import match_command
from personalclipboard.asr.voice_gate import VoiceGate
from personalclipboard.audio.capture import RingBuffer
from personalclipboard.config import Settings


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
    ) -> None:
        self._settings = settings
        self._ring = ring
        self._on_partial = on_partial
        self._on_commit = on_commit
        self._on_status = on_status
        self._on_error = on_error
        self._on_command = on_command
        self._model = None
        self._load_error: str | None = None
        self._enabled = threading.Event()
        self._shutdown = threading.Event()
        self._thread: threading.Thread | None = None
        self._assembler = SentenceAssembler(min_chars=settings.min_commit_chars)
        self._gate = VoiceGate()
        self._last_command: str | None = None
        self._last_command_at = 0.0
        self._meeting_mode = False
        self._state_lock = threading.Lock()

    @property
    def ready(self) -> bool:
        return self._model is not None

    @property
    def load_error(self) -> str | None:
        return self._load_error

    def load(self) -> None:
        """Load large-v3-turbo on CUDA float16 and keep weights resident."""
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

    def set_meeting_mode(self, enabled: bool) -> None:
        """Meeting notes: all speakers, pause commits, no voice commands."""
        with self._state_lock:
            self._meeting_mode = enabled
            self._assembler.set_pause_commit(enabled)
            self._assembler.reset()
            self._gate.reset()
            self._last_command = None

    def flush_remainder(self) -> str:
        with self._state_lock:
            return self._assembler.take_remainder()

    def start(self) -> None:
        """Run the hop loop while enable is ON. condition_on_previous_text=False."""
        if self._model is None:
            raise RuntimeError(self._load_error or "Whisper model is not loaded")
        with self._state_lock:
            self._assembler.reset()
            self._last_command = None
            self._last_command_at = 0.0
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
        self._gate.reset()

    def shutdown(self) -> None:
        self.stop()
        self._shutdown.set()
        self._enabled.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _loop(self) -> None:
        hop_s = self._settings.hop_ms / 1000.0
        while not self._shutdown.is_set():
            if not self._enabled.wait(timeout=0.2):
                continue
            if self._shutdown.is_set() or not self._enabled.is_set():
                continue
            deadline = time.perf_counter() + hop_s
            try:
                self._tick()
            except Exception as exc:
                if self._on_error:
                    self._on_error(f"ASR: {exc}")
            remaining = deadline - time.perf_counter()
            _idle_remaining(remaining, self._enabled, self._shutdown)

    def _tick(self) -> None:
        model = self._model
        if model is None or not self._enabled.is_set():
            return
        audio = self._ring.window_float32(self._settings.window_seconds, self._settings.sample_rate)
        min_samples = int(self._settings.sample_rate * 0.2)
        if audio.size < min_samples:
            return
        meeting = self._meeting_mode
        if meeting:
            energy = float(np.sqrt(np.mean(np.square(audio.astype(np.float64)))))
            if energy < 0.008:
                self._finish_tick("", 1.0, 0.0, audio)
                return
        elif not self._voice_ok(audio):
            return
        text, no_speech, avg_lp = _transcribe(
            model,
            audio,
            beam_size=self._settings.beam_size_partial,
            condition_on_previous_text=self._settings.condition_on_previous_text,
        )
        if not meeting:
            command = match_command(text)
            if command:
                self._emit_command(command)
                return
        self._finish_tick(text, no_speech, avg_lp, audio)

    def _voice_ok(self, audio: np.ndarray) -> bool:
        verdict = self._gate.classify(audio, self._settings.sample_rate)
        if verdict == "silence":
            if self._on_status:
                self._on_status("locked" if self._gate.enrolled else "listening")
            return False
        if verdict == "reject_other":
            if self._on_status:
                self._on_status("uncertain")
            if self._on_partial:
                self._on_partial("")
            return False
        return True

    def _finish_tick(self, text: str, no_speech: float, avg_lp: float, audio: np.ndarray) -> None:
        with self._state_lock:
            meeting = self._meeting_mode
            partial, commit, status = self._assembler.update(
                text,
                no_speech,
                avg_lp,
                no_speech_max=self._settings.no_speech_prob_max,
                logprob_min=self._settings.avg_logprob_min,
            )
        if meeting and status == "listening":
            status = "recording"
        elif self._gate.enrolled and status == "listening":
            status = "locked"
        if self._on_status:
            self._on_status(status)
        if self._on_partial:
            self._on_partial(partial)
        if status == "uncertain" or not commit:
            return
        if not meeting:
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
            return
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
