import winsound

from personalclipboard.ui.copy_cue import copy_wav_bytes, play_copy_cue


def test_copy_wav_is_short_riff() -> None:
    wav = copy_wav_bytes()
    assert wav[:4] == b"RIFF"
    assert wav[8:12] == b"WAVE"
    assert wav[20:22] == b"\x01\x00"
    assert 1500 < len(wav) < 6000


def test_play_copy_cue_is_async(monkeypatch) -> None:
    calls: list[tuple[object, int]] = []

    def _fake_play(sound: object, flags: int) -> bool:
        calls.append((sound, flags))
        return True

    monkeypatch.setattr("winsound.PlaySound", _fake_play)
    play_copy_cue()
    assert len(calls) == 1
    sound, flags = calls[0]
    assert sound == copy_wav_bytes()
    assert flags & winsound.SND_ASYNC
    assert flags & winsound.SND_MEMORY
