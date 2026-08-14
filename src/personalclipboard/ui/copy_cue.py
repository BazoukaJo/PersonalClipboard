"""Short in-memory tick when text lands on the clipboard."""

from __future__ import annotations

import array
import functools
import math
import struct
import sys

_RATE = 22050
_MS = 52


@functools.cache
def copy_wav_bytes() -> bytes:
    n_samples = int(_RATE * _MS / 1000)
    pcm = array.array("h")
    for index in range(n_samples):
        t = index / _RATE
        env = math.exp(-t * 62.0)
        freq = 1760.0 + 720.0 * (index / max(n_samples - 1, 1))
        sample = env * (
            0.62 * math.sin(2.0 * math.pi * freq * t)
            + 0.22 * math.sin(4.0 * math.pi * freq * t)
        )
        pcm.append(int(max(-1.0, min(1.0, sample)) * 14000))
    data = pcm.tobytes()
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + len(data),
        b"WAVE",
        b"fmt ",
        16,
        1,
        1,
        _RATE,
        _RATE * 2,
        2,
        16,
        b"data",
        len(data),
    )
    return header + data


def play_copy_cue() -> None:
    if sys.platform != "win32":
        return
    import winsound

    try:
        winsound.PlaySound(
            copy_wav_bytes(),
            winsound.SND_MEMORY | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
        )
    except RuntimeError:
        return
