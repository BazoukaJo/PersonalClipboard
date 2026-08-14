import numpy as np

from personalclipboard.audio.capture import RingBuffer


def test_ring_buffer_roundtrip() -> None:
    ring = RingBuffer(sample_rate=16_000, seconds=1.0)
    pcm = (np.arange(1600, dtype=np.int16)).tobytes()
    ring.write(pcm)
    window = ring.window_float32(0.1, 16_000)
    assert window.shape == (1600,)
    reconstructed = np.round(window * 32768.0).astype(np.int16)
    assert reconstructed[0] == 0
    assert reconstructed[-1] == 1599


def test_ring_buffer_wraps() -> None:
    ring = RingBuffer(sample_rate=100, seconds=1.0)
    first = np.ones(80, dtype=np.int16).tobytes()
    second = (np.arange(50, dtype=np.int16) + 10).tobytes()
    ring.write(first)
    ring.write(second)
    window = ring.window_float32(1.0, 100)
    assert window.size == 100
