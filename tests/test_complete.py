from personalclipboard.llm.complete import continuation_suffix, should_predict
from personalclipboard.modes.complete import COMPLETE_SYSTEM_PROMPT


def test_should_predict_requires_focus_and_words() -> None:
    assert should_predict("The meeting", focused=True, enabled=True, blocked=False) is True
    assert should_predict("The meeting", focused=False, enabled=True, blocked=False) is False
    assert should_predict("The meeting", focused=True, enabled=False, blocked=False) is False
    assert should_predict("The meeting.", focused=True, enabled=True, blocked=False) is False
    assert should_predict("Hi", focused=True, enabled=True, blocked=False) is False


def test_continuation_strips_repeated_prefix() -> None:
    assert continuation_suffix("The meeting is", "The meeting is scheduled Monday") == " scheduled Monday"
    assert continuation_suffix("The meeting is ", "scheduled Monday") == "scheduled Monday"
    assert continuation_suffix("Hello", "Hello") == ""


def test_complete_prompt_asks_for_suffix_only() -> None:
    lowered = COMPLETE_SYSTEM_PROMPT.lower()
    assert "continuation" in lowered
    assert "prefix" in lowered
