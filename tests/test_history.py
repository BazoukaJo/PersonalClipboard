from datetime import datetime
from pathlib import Path

from personalclipboard.clipboard.history import (
    HISTORY_MAX_BYTES,
    ClipboardHistory,
    format_entry,
    parse_entries,
    trim_history_bytes,
)


def test_trim_drops_oldest_bytes() -> None:
    first = format_entry("alpha", datetime(2026, 1, 1, 12, 0, 0)).encode("utf-8")
    second = format_entry("bravo", datetime(2026, 1, 1, 12, 0, 1)).encode("utf-8")
    third = format_entry("charlie", datetime(2026, 1, 1, 12, 0, 2)).encode("utf-8")
    kept = trim_history_bytes(first + second + third, len(second + third))
    assert kept == second + third
    assert b"alpha" not in kept
    assert b"bravo" in kept
    assert b"charlie" in kept


def test_trim_drops_partial_oldest_entry() -> None:
    first = format_entry("alpha", datetime(2026, 1, 1, 12, 0, 0)).encode("utf-8")
    second = format_entry("bravo", datetime(2026, 1, 1, 12, 0, 1)).encode("utf-8")
    blob = first + second
    kept = trim_history_bytes(blob, len(blob) - 8)
    assert b"alpha" not in kept
    assert b"bravo" in kept
    blob = ("é" * 1000).encode("utf-8") * 40
    trimmed = trim_history_bytes(blob, 500)
    assert len(trimmed) <= 500
    trimmed.decode("utf-8")


def test_history_file_caps_and_drops_oldest(tmp_path: Path) -> None:
    path = tmp_path / "history.txt"
    first = format_entry("old line", datetime(2026, 8, 14, 10, 0, 0))
    second = format_entry("new line", datetime(2026, 8, 14, 10, 0, 1))
    log = ClipboardHistory(path, max_bytes=len(second.encode("utf-8")), threaded=False)
    log._record("old line", datetime(2026, 8, 14, 10, 0, 0))
    log._record("new line", datetime(2026, 8, 14, 10, 0, 1))
    text = path.read_text(encoding="utf-8")
    assert "old line" not in text
    assert "new line" in text
    assert path.stat().st_size <= len(second.encode("utf-8"))
    assert HISTORY_MAX_BYTES == 20 * 1024 * 1024
    assert first != second


def test_history_skips_blank(tmp_path: Path) -> None:
    path = tmp_path / "history.txt"
    log = ClipboardHistory(path, threaded=False)
    log.append("   ")
    assert not path.exists()


def test_parse_entries_keeps_complete_multiline_text() -> None:
    raw = (
        "2026-08-14 10:00:00\n"
        "first paragraph\n"
        "\n"
        "still the first clip\n"
        "\n"
        "2026-08-14 10:00:01\n"
        "second clip\n"
        "\n"
    )
    entries = parse_entries(raw)
    assert entries == [
        ("2026-08-14 10:00:00", "first paragraph\n\nstill the first clip"),
        ("2026-08-14 10:00:01", "second clip"),
    ]
