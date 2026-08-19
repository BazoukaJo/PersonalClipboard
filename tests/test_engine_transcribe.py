from types import SimpleNamespace

import numpy as np

from personalclipboard.asr.engine import _transcribe


class _FakeModel:
    def __init__(self) -> None:
        self.kwargs: dict = {}

    def transcribe(self, _audio, **kwargs):
        self.kwargs = kwargs
        segment = SimpleNamespace(text="bonjour", no_speech_prob=0.1, avg_logprob=-0.2)
        return [segment], None


def test_transcribe_keeps_source_language() -> None:
    model = _FakeModel()
    text, no_speech, avg_lp = _transcribe(
        model,
        np.zeros(1600, dtype=np.float32),
        beam_size=1,
        condition_on_previous_text=False,
    )
    assert text == "bonjour"
    assert no_speech == 0.1
    assert avg_lp == -0.2
    assert model.kwargs["language"] is None
    assert model.kwargs["task"] == "transcribe"
    assert model.kwargs["multilingual"] is True
    assert model.kwargs["condition_on_previous_text"] is False
    assert model.kwargs["vad_filter"] is False
