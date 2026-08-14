from personalclipboard.modes.ambient import AMBIENT_SYSTEM_PROMPT


def test_correction_prompt_is_prose() -> None:
    assert "corrected sentence" in AMBIENT_SYSTEM_PROMPT.lower()
    assert "clipboard" in AMBIENT_SYSTEM_PROMPT.lower()
