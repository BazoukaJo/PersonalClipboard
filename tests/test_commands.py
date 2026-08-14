from personalclipboard.asr.commands import match_command, normalize_phrase


def test_normalize_strips_punctuation() -> None:
    assert normalize_phrase("Paste last.") == "paste last"
    assert normalize_phrase("  COPY LAST!  ") == "copy last"


def test_match_known_commands() -> None:
    assert match_command("paste last") == "paste_last"
    assert match_command("Paste last.") == "paste_last"
    assert match_command("copy last one") == "copy_last"
    assert match_command("correct last") == "correct_last"
    assert match_command("fix last") == "correct_last"


def test_non_command_is_none() -> None:
    assert match_command("please paste last tomorrow") is None
    assert match_command("hello there.") is None
