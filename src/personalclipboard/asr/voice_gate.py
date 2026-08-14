"""Reject quiet ambient audio and lock onto the user's voice level/timbre."""

from __future__ import annotations

import numpy as np


class VoiceGate:
    """RMS + spectral-centroid lock. Capture stays always-on; this only skips ASR."""

    def __init__(self, min_rms: float = 0.018, centroid_tol: float = 0.4) -> None:
        self._min_rms = min_rms
        self._centroid_tol = centroid_tol
        self._user_rms: float | None = None
        self._user_centroid: float | None = None

    def classify(self, audio: np.ndarray, sample_rate: int) -> str:
        """Return silence | accept | reject_other."""
        if audio.size == 0:
            return "silence"
        rms = _rms(audio)
        if rms < self._min_rms:
            return "silence"
        if self._user_rms is None:
            return "accept"
        if rms < 0.4 * self._user_rms:
            return "reject_other"
        centroid = _centroid(audio, sample_rate)
        if self._user_centroid is not None and centroid > 0:
            delta = abs(centroid - self._user_centroid) / (self._user_centroid + 1e-6)
            if delta > self._centroid_tol:
                return "reject_other"
        return "accept"

    def enroll(self, audio: np.ndarray, sample_rate: int) -> None:
        rms = _rms(audio)
        centroid = _centroid(audio, sample_rate)
        if self._user_rms is None:
            self._user_rms = rms
            self._user_centroid = centroid
            return
        self._user_rms = 0.85 * self._user_rms + 0.15 * rms
        if centroid > 0:
            prev = self._user_centroid or centroid
            self._user_centroid = 0.85 * prev + 0.15 * centroid

    @property
    def enrolled(self) -> bool:
        return self._user_rms is not None

    def reset(self) -> None:
        self._user_rms = None
        self._user_centroid = None


def _rms(audio: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(audio.astype(np.float64)))))


def _centroid(audio: np.ndarray, sample_rate: int) -> float:
    spec = np.abs(np.fft.rfft(audio.astype(np.float64)))
    freqs = np.fft.rfftfreq(audio.size, 1.0 / sample_rate)
    denom = float(np.sum(spec))
    if denom <= 1e-9:
        return 0.0
    return float(np.sum(freqs * spec) / denom)
