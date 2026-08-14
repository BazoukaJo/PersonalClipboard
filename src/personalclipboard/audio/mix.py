"""Mix microphone and speaker PCM for meeting ASR. Not used on the PortAudio callback."""

from __future__ import annotations

import numpy as np


def mix_windows(mic: np.ndarray, loop: np.ndarray) -> np.ndarray:
    """Add the most recent overlapping samples. Empty side is a no-op."""
    if loop.size == 0:
        return mic
    if mic.size == 0:
        return loop
    count = min(int(mic.size), int(loop.size))
    mixed = mic[-count:].astype(np.float32, copy=False) + loop[-count:].astype(
        np.float32, copy=False
    )
    return np.clip(mixed, -1.0, 1.0).astype(np.float32)


def resample_mono(audio: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    if audio.size == 0 or src_rate <= 0 or src_rate == dst_rate:
        return audio.astype(np.float32, copy=False)
    duration = audio.size / float(src_rate)
    need = int(round(duration * dst_rate))
    if need <= 0:
        return np.zeros(0, dtype=np.float32)
    old_x = np.linspace(0.0, 1.0, int(audio.size), endpoint=False)
    new_x = np.linspace(0.0, 1.0, need, endpoint=False)
    return np.interp(new_x, old_x, audio.astype(np.float64)).astype(np.float32)
