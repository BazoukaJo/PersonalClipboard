from personalclipboard.ui.overlay import _display_partial, flash_label, live_preview


def test_partial_hides_punctuation_noise() -> None:
    assert _display_partial("..") == ""
    assert _display_partial("…") == ""
    assert _display_partial("") == ""


def test_partial_keeps_real_words() -> None:
    assert _display_partial("  Hey there  ") == "Hey there"


def test_live_preview_ends_with_ellipsis() -> None:
    assert live_preview("") == "…"
    assert live_preview("Hey there").endswith("…")
    assert "Hey there" in live_preview("Hey there")


def test_flash_label_shortens_status() -> None:
    assert flash_label("On clipboard. Press Ctrl+V to paste.") == "Copied"
    assert flash_label("Meeting notes saved as Meeting 2026-08-14 1228.md") == "Saved"
    assert flash_label("Correcting…") == "Correcting"
    assert flash_label("Clipboard is empty") == "Empty"
    assert flash_label("ASR load failed: CUDA") == "Error"
