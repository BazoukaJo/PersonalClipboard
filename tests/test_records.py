from datetime import datetime
from pathlib import Path

from personalclipboard.notes.library import list_records, load_record
from personalclipboard.notes.meeting import MeetingNotes


def test_list_records_newest_first_with_kinds(tmp_path: Path) -> None:
    meeting = MeetingNotes(tmp_path, datetime(2026, 8, 14, 12, 28), "mic + speakers", kind="meeting")
    meeting.append("Hello everyone.", when=datetime(2026, 8, 14, 12, 29))
    meeting.close()
    playback = MeetingNotes(tmp_path, datetime(2026, 8, 14, 19, 41), "speakers", kind="playback")
    playback.append("From the video.", when=datetime(2026, 8, 14, 19, 41))
    playback.close()
    items = list_records(tmp_path)
    assert [item.kind for item in items] == ["playback", "meeting"]
    assert items[0].preview.startswith("From the video.")
    loaded = load_record(playback.path)
    assert loaded is not None
    assert "From the video." in loaded.body
    assert loaded.kind == "playback"


def test_records_dialog_click_opens_full_body(qapp, tmp_path: Path) -> None:
    from personalclipboard.ui.records_dialog import RecordsDialog, _RecordCard

    notes = MeetingNotes(tmp_path, datetime(2026, 8, 14, 19, 41), "speakers", kind="playback")
    notes.append("From the video.", when=datetime(2026, 8, 14, 19, 41))
    notes.close()
    items = list_records(tmp_path)
    dialog = RecordsDialog(items, "en")
    cards = dialog.findChildren(_RecordCard)
    assert cards
    cards[0].clicked.emit(items[0])
    assert dialog._stack.currentIndex() == 1
    assert "From the video." in dialog._detail_page._body.toPlainText()
    dialog.close()
