from personalclipboard.modes.ambient import AMBIENT_SYSTEM_PROMPT
from personalclipboard.modes.complete import COMPLETE_SYSTEM_PROMPT


def test_correction_prompt_is_prose() -> None:
    assert "corrected sentence" in AMBIENT_SYSTEM_PROMPT.lower()
    assert "clipboard" in AMBIENT_SYSTEM_PROMPT.lower()


def test_complete_prompt_asks_for_suffix() -> None:
    lowered = COMPLETE_SYSTEM_PROMPT.lower()
    assert "continuation" in lowered
    assert "prefix" in lowered
