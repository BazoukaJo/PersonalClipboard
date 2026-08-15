from typing import Any, Mapping

import pytest

from personalclipboard.config import Settings
from personalclipboard.llm.corrector import Corrector, _assistant_text, _strip_fences


def test_corrector_rejects_non_localhost() -> None:
    with pytest.raises(ValueError, match="127.0.0.1"):
        Corrector(Settings(ollama_host="http://8.8.8.8:11434"))


def test_strip_markdown_fences() -> None:
    raw = "```text\nBegin Object\nEnd Object\n```"
    assert _strip_fences(raw) == "Begin Object\nEnd Object"


def test_assistant_text_from_chat_json() -> None:
    payload = {"message": {"role": "assistant", "content": "  Hello.  "}}
    assert _assistant_text(payload) == "Hello."


def test_assistant_text_ignores_non_dict() -> None:
    assert _assistant_text(object()) == ""
    assert _assistant_text({"message": "stream-chunk"}) == ""


def test_correct_keeps_model_loaded(monkeypatch) -> None:
    seen: list[dict] = []

    def fake_post(url: str, *, timeout: float, body: Mapping[str, Any]) -> object:
        seen.append({"url": url, "body": dict(body), "timeout": timeout})
        return {"message": {"content": "Hello."}}

    monkeypatch.setattr("personalclipboard.llm.corrector._post_json", fake_post)
    out = Corrector(Settings()).correct("Hello.")
    assert out == "Hello."
    assert seen[0]["body"]["keep_alive"] == 120
    assert seen[0]["url"].endswith("/api/chat")
    assert seen[0]["body"]["options"]["temperature"] == 0.1


def test_correct_ai_mode_uses_reformulate_prompt(monkeypatch) -> None:
    seen: list[dict] = []

    def fake_post(url: str, *, timeout: float, body: Mapping[str, Any]) -> object:
        seen.append(dict(body))
        return {"message": {"content": "Summarize the meeting notes."}}

    monkeypatch.setattr("personalclipboard.llm.corrector._post_json", fake_post)
    out = Corrector(Settings()).correct("sum up notes", mode="ai")
    assert out == "Summarize the meeting notes."
    system = seen[0]["messages"][0]["content"].lower()
    assert "reformulat" in system
    assert "prompt" in system


def test_correct_translate_mode_uses_translate_prompt(monkeypatch) -> None:
    seen: list[dict] = []

    def fake_post(url: str, *, timeout: float, body: Mapping[str, Any]) -> object:
        seen.append(dict(body))
        return {"message": {"content": "Bonjour."}}

    monkeypatch.setattr("personalclipboard.llm.corrector._post_json", fake_post)
    out = Corrector(Settings(ui_language="fr")).correct("Hello.", mode="translate")
    assert out == "Bonjour."
    system = seen[0]["messages"][0]["content"].lower()
    assert "french" in system
    assert "translat" in system


def test_correct_retry_sends_temperature_and_seed(monkeypatch) -> None:
    seen: list[dict] = []

    def fake_post(url: str, *, timeout: float, body: Mapping[str, Any]) -> object:
        seen.append(dict(body))
        return {"message": {"content": "Hi there."}}

    monkeypatch.setattr("personalclipboard.llm.corrector._post_json", fake_post)
    out = Corrector(Settings()).correct(
        "Hello there.", temperature=0.55, seed=1717, vary=True
    )
    assert out == "Hi there."
    options = seen[0]["options"]
    assert options["temperature"] == 0.55
    assert options["seed"] == 1717
    assert seen[0]["messages"][1]["content"].startswith("Different wording")


def test_complete_keeps_model_loaded(monkeypatch) -> None:
    seen: list[dict] = []

    def fake_post(url: str, *, timeout: float, body: Mapping[str, Any]) -> object:
        seen.append(dict(body))
        return {"message": {"content": " world"}}

    monkeypatch.setattr("personalclipboard.llm.corrector._post_json", fake_post)
    Corrector(Settings()).complete("Hello there")
    assert seen[0]["keep_alive"] == 120


def test_ensure_loaded_pins_model_two_minutes(monkeypatch) -> None:
    seen: list[dict] = []

    def fake_post(url: str, *, timeout: float, body: Mapping[str, Any]) -> object:
        seen.append({"url": url, "body": dict(body), "timeout": timeout})
        return {}

    monkeypatch.setattr("personalclipboard.llm.corrector._post_json", fake_post)
    Corrector(Settings()).ensure_loaded()
    assert seen[0]["url"].endswith("/api/generate")
    assert seen[0]["body"]["keep_alive"] == 120
    assert seen[0]["body"]["prompt"] == ""
    assert seen[0]["timeout"] >= 60.0
