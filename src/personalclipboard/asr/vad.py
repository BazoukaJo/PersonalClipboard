"""Silence timer: after enough quiet hops, idle the microphone pipeline."""

from __future__ import annotations


class QuietIdle:
    def __init__(self, silence_ms: int = 1500) -> None:
        self.silence_ms = max(400, silence_ms)
        self._accum = 0
        self.idle = False

    def reset(self) -> None:
        self._accum = 0
        self.idle = False

    def on_silence(self, hop_ms: int) -> bool:
        """Return True the moment quiet time crosses the threshold."""
        if self.idle:
            return False
        self._accum += max(hop_ms, 1)
        if self._accum >= self.silence_ms:
            self.idle = True
            return True
        return False

    def on_voice(self) -> None:
        self._accum = 0
        self.idle = False
