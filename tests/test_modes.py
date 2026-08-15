from personalclipboard.modes import system_prompt
from personalclipboard.modes.ambient import AI_SYSTEM_PROMPT, AMBIENT_SYSTEM_PROMPT
from personalclipboard.modes.complete import COMPLETE_SYSTEM_PROMPT
from personalclipboard.modes.rewrite import SUMMARIZE_PROMPT, translate_prompt


def test_human_prompt_keeps_wording() -> None:
    text = system_prompt("human").lower()
    assert text == AMBIENT_SYSTEM_PROMPT.lower()
    assert "grammar" in text
    assert "wording" in text
    assert "reformulat" not in text


def test_ai_prompt_reformulates_for_another_model() -> None:
    text = system_prompt("ai").lower()
    assert text == AI_SYSTEM_PROMPT.lower()
    assert "reformulat" in text
    assert "prompt" in text
    assert "do not answer" in text


def test_unknown_mode_uses_human_prompt() -> None:
    assert system_prompt("nope") == AMBIENT_SYSTEM_PROMPT


def test_translate_prompt_uses_overlay_language() -> None:
    french = system_prompt("translate", lang="fr").lower()
    assert french == translate_prompt("fr").lower()
    assert "french" in french
    assert "only the translation" in french


def test_summarize_prompt_is_rewrite_mode() -> None:
    assert system_prompt("summarize") == SUMMARIZE_PROMPT
    assert "summarize" in system_prompt("summarize").lower()


def test_complete_prompt_asks_for_suffix() -> None:
    lowered = COMPLETE_SYSTEM_PROMPT.lower()
    assert "continuation" in lowered
    assert "prefix" in lowered
