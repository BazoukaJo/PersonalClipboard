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
