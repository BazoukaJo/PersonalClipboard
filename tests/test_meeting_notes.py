from datetime import datetime
from pathlib import Path

from personalclipboard.asr.assembler import SentenceAssembler
from personalclipboard.notes.meeting import MeetingNotes, meeting_filename


def test_meeting_filename_is_sortable_and_unique() -> None:
    when = datetime(2026, 8, 14, 12, 28)
    assert meeting_filename(when) == "Meeting 2026-08-14 1228.md"
    assert meeting_filename(when, ["Meeting 2026-08-14 1228.md"]) == "Meeting 2026-08-14 1228 2.md"


def test_meeting_notes_append_to_desktop_folder(tmp_path: Path) -> None:
    started = datetime(2026, 8, 14, 12, 28)
    notes = MeetingNotes(tmp_path, started, "Microphone (Maono AU-PM401)")
    notes.append("Hello everyone.", when=datetime(2026, 8, 14, 12, 29))
    notes.append("Let's begin.", when=datetime(2026, 8, 14, 12, 30))
    notes.close()
    text = notes.path.read_text(encoding="utf-8")
    assert notes.path.name.startswith("Meeting 2026-08-14 1228")
    assert "Hello everyone." in text
    assert "Let's begin." in text
    assert "Maono" in text
    assert "Ended:" in text
    assert notes.preview().count("Hello") == 1


def test_meeting_notes_skip_sliding_suffix(tmp_path: Path) -> None:
    started = datetime(2026, 8, 14, 12, 28)
    notes = MeetingNotes(tmp_path, started, "speakers", kind="playback")
    notes.append("that from its shadows.", when=datetime(2026, 8, 14, 12, 29))
    notes.append("from its shadows.", when=datetime(2026, 8, 14, 12, 29))
    notes.append("its shadows.", when=datetime(2026, 8, 14, 12, 29))
    text = notes.path.read_text(encoding="utf-8")
    assert text.count("shadows") == 1


def test_meeting_notes_replace_extended_overlap(tmp_path: Path) -> None:
    notes = MeetingNotes(tmp_path, datetime(2026, 8, 14, 12, 28), "speakers", kind="playback")
    notes.append("the lighting is harsh", when=datetime(2026, 8, 14, 12, 29))
    notes.append("the lighting is harsh tonight", when=datetime(2026, 8, 14, 12, 29))
    text = notes.path.read_text(encoding="utf-8")
    assert text.count("lighting") == 1
    assert "tonight" in text


def test_meeting_notes_skip_duplicate_chinese(tmp_path: Path) -> None:
    notes = MeetingNotes(tmp_path, datetime(2026, 8, 14, 12, 28), "mic", kind="meeting")
    notes.append("你好世界。", when=datetime(2026, 8, 14, 12, 29))
    notes.append("你好世界。", when=datetime(2026, 8, 14, 12, 29))
    text = notes.path.read_text(encoding="utf-8")
    assert text.count("你好世界") == 1


def test_pause_commit_after_quiet_hops() -> None:
    asm = SentenceAssembler(min_chars=4)
    asm.set_pause_commit(True)
    kwargs = {
        "avg_logprob": -0.2,
        "no_speech_max": 0.65,
        "logprob_min": -1.2,
    }
    _, commit, _ = asm.update("hello world", no_speech_prob=0.1, **kwargs)
    assert commit is None
    assert asm.update("", no_speech_prob=0.9, **kwargs)[1] is None
    assert asm.update("", no_speech_prob=0.9, **kwargs)[1] is None
    _, commit, _ = asm.update("", no_speech_prob=0.9, **kwargs)
    assert commit == "hello world"


def test_meeting_filename_accepts_playback_kind() -> None:
    when = datetime(2026, 8, 14, 12, 28)
    assert meeting_filename(when, existing=None, kind="playback") == "Playback 2026-08-14 1228.md"
    assert (
        meeting_filename(
            when, existing=["Playback 2026-08-14 1228.md"], kind="playback"
        )
        == "Playback 2026-08-14 1228 2.md"
    )


def test_dictation_pause_still_does_not_commit() -> None:
    asm = SentenceAssembler(min_chars=8)
    kwargs = {
        "avg_logprob": -0.2,
        "no_speech_max": 0.65,
        "logprob_min": -1.2,
    }
    asm.update("hello world", no_speech_prob=0.1, **kwargs)
    for _ in range(4):
        _, commit, _ = asm.update("", no_speech_prob=0.9, **kwargs)
        assert commit is None
