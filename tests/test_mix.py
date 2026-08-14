import numpy as np

from personalclipboard.audio.mix import mix_windows, resample_mono


def test_mix_empty_loop_keeps_mic() -> None:
    mic = np.array([0.2, -0.1, 0.4], dtype=np.float32)
    out = mix_windows(mic, np.zeros(0, dtype=np.float32))
    assert np.allclose(out, mic)


def test_mix_empty_mic_keeps_loop() -> None:
    loop = np.array([0.3, 0.1], dtype=np.float32)
    out = mix_windows(np.zeros(0, dtype=np.float32), loop)
    assert np.allclose(out, loop)


def test_mix_adds_aligned_tails_and_clips() -> None:
    mic = np.array([0.2, 0.9], dtype=np.float32)
    loop = np.array([0.1, 0.4, 0.8], dtype=np.float32)
    out = mix_windows(mic, loop)
    assert out.shape == (2,)
    assert np.isclose(out[0], 0.6)
    assert np.isclose(out[1], 1.0)


def test_resample_mono_changes_length() -> None:
    audio = np.ones(16, dtype=np.float32)
    out = resample_mono(audio, 16_000, 8_000)
    assert out.size == 8
    assert np.allclose(out, 1.0, atol=1e-5)
