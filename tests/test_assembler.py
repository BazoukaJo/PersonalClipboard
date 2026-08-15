from personalclipboard.asr.assembler import SentenceAssembler


def test_commit_on_punctuation() -> None:
    asm = SentenceAssembler(min_chars=8)
    partial, commit, status = asm.update(
        "hello there.",
        no_speech_prob=0.1,
        avg_logprob=-0.2,
        no_speech_max=0.65,
        logprob_min=-1.2,
    )
    assert commit == "hello there."
    assert partial == ""
    assert status == "listening"


def test_reject_low_confidence_does_not_commit() -> None:
    asm = SentenceAssembler(min_chars=8)
    partial, commit, status = asm.update(
        "hello there.",
        no_speech_prob=0.1,
        avg_logprob=-2.0,
        no_speech_max=0.65,
        logprob_min=-1.2,
    )
    assert commit is None
    assert status == "uncertain"
    assert "hello" in partial


def test_pause_does_not_commit_without_period() -> None:
    asm = SentenceAssembler(min_chars=8)
    asm.update(
        "hello world",
        no_speech_prob=0.1,
        avg_logprob=-0.2,
        no_speech_max=0.65,
        logprob_min=-1.2,
    )
    partial, commit, status = asm.update(
        "",
        no_speech_prob=0.9,
        avg_logprob=-0.2,
        no_speech_max=0.65,
        logprob_min=-1.2,
    )
    assert commit is None
    assert "hello world" in partial
    assert status == "listening"


def test_stitches_windows_then_commits_on_period() -> None:
    asm = SentenceAssembler(min_chars=4)
    _, commit, _ = asm.update(
        "this is a fairly",
        no_speech_prob=0.1,
        avg_logprob=-0.2,
        no_speech_max=0.65,
        logprob_min=-1.2,
    )
    assert commit is None
    _, commit, _ = asm.update(
        "fairly long sentence.",
        no_speech_prob=0.1,
        avg_logprob=-0.2,
        no_speech_max=0.65,
        logprob_min=-1.2,
    )
    assert commit == "this is a fairly long sentence."


def test_voice_command_commits_without_period() -> None:
    asm = SentenceAssembler(min_chars=8)
    _, commit, _ = asm.update(
        "paste last",
        no_speech_prob=0.1,
        avg_logprob=-0.2,
        no_speech_max=0.65,
        logprob_min=-1.2,
    )
    assert commit == "paste last"


def _hop(asm: SentenceAssembler, text: str, *, quiet: bool = False) -> str | None:
    _, commit, _ = asm.update(
        text,
        no_speech_prob=0.9 if quiet else 0.1,
        avg_logprob=-0.2,
        no_speech_max=0.65,
        logprob_min=-1.2,
    )
    return commit


def test_overlapping_windows_do_not_recommit_in_dictation() -> None:
    asm = SentenceAssembler(min_chars=4)
    assert _hop(asm, "hello there.") == "hello there."
    assert _hop(asm, "there.") is None
    assert _hop(asm, "there.") is None


def test_meeting_stitches_sliding_windows_until_pause() -> None:
    asm = SentenceAssembler(min_chars=4)
    asm.set_pause_commit(True)
    windows = [
        "that from its shadows.",
        "from its shadows.",
        "its shadows.",
        "shadows is very clean.",
        "Shadows is very clean and distinct.",
        "It's very clean and distinctive.",
        "is very clean and distinctive shadows.",
        "very clean and distinctive shadows.",
        "clean and distinctive shadows.",
        "and distinctive shadows.",
        "distinctive shadows.",
        "shadows.",
    ]
    commits = [commit for window in windows if (commit := _hop(asm, window))]
    assert commits == []
    assert _hop(asm, "", quiet=True) is None
    assert _hop(asm, "", quiet=True) is None
    final = _hop(asm, "", quiet=True)
    assert final is not None
    lower = final.lower()
    assert "shadows" in lower
    assert "clean" in lower
    assert lower.count("shadows") == 1


def test_meeting_keeps_stitching_when_whisper_scores_no_speech() -> None:
    asm = SentenceAssembler(min_chars=4)
    asm.set_pause_commit(True)
    kwargs = {
        "avg_logprob": -1.8,
        "no_speech_max": 0.65,
        "logprob_min": -1.2,
    }
    _, commit, status = asm.update(
        "the lighting on the set is harsh",
        no_speech_prob=0.8,
        **kwargs,
    )
    assert commit is None
    assert status == "listening"
    assert "lighting" in asm._acc
    _, commit, _ = asm.update(
        "the lighting on the set is harsh tonight.",
        no_speech_prob=0.7,
        **kwargs,
    )
    assert commit is None
    assert "tonight" in asm._acc


def test_meeting_commits_when_next_sentence_starts() -> None:
    asm = SentenceAssembler(min_chars=4)
    asm.set_pause_commit(True)
    assert _hop(asm, "the lighting is harsh.") is None
    commit = _hop(asm, "lighting is harsh. Next shot is ready.")
    assert commit == "the lighting is harsh."
    assert "Next shot is ready." in (asm._acc or "")
