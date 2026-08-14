import pytest

from personalclipboard.config import Settings
from personalclipboard.llm.corrector import Corrector, _assistant_text, _strip_fences


def test_corrector_rejects_non_localhost() -> None:
    with pytest.raises(ValueError, match="127.0.0.1"):
        Corrector(Settings(ollama_host="http://8.8.8.8:11434"))


def test_strip_markdown_fences() -> None:
    raw = "```t3d\nBegin Object\nEnd Object\n```"
    assert _strip_fences(raw) == "Begin Object\nEnd Object"


def test_assistant_text_from_chat_json() -> None:
    payload = {"message": {"role": "assistant", "content": "  Hello.  "}}
    assert _assistant_text(payload) == "Hello."


def test_assistant_text_ignores_non_dict() -> None:
    assert _assistant_text(object()) == ""
    assert _assistant_text({"message": "stream-chunk"}) == ""
