import numpy as np

from personalclipboard.asr.voice_gate import VoiceGate


def test_silence_on_zeros() -> None:
    gate = VoiceGate()
    audio = np.zeros(1600, dtype=np.float32)
    assert gate.classify(audio, 16_000) == "silence"


def test_accepts_first_loud_voice() -> None:
    gate = VoiceGate()
    audio = np.full(1600, 0.2, dtype=np.float32)
    assert gate.classify(audio, 16_000) == "accept"


def test_rejects_quiet_other_after_enroll() -> None:
    gate = VoiceGate()
    user = np.full(1600, 0.25, dtype=np.float32)
    gate.enroll(user, 16_000)
    other = np.full(1600, 0.05, dtype=np.float32)
    assert gate.classify(other, 16_000) == "reject_other"
    assert gate.enrolled is True
