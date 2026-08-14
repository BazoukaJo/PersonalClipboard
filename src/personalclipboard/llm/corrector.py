"""Ollama HTTP to 127.0.0.1 only. Committed sentences or Ctrl+Shift+A — never partials."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Mapping
from urllib.parse import urlparse

from personalclipboard.config import Settings
from personalclipboard.llm.complete import continuation_suffix
from personalclipboard.modes import complete_prompt, system_prompt


class Corrector:
    def __init__(self, settings: Settings) -> None:
        host = settings.ollama_host.rstrip("/")
        parsed = urlparse(host)
        if parsed.hostname not in ("127.0.0.1", "localhost"):
            raise ValueError("Ollama host must be 127.0.0.1")
        self._settings = settings
        self._chat_url = f"{host}/api/chat"

    def correct(self, text: str) -> str:
        """Rewrite `text`. Callers skip stale jobs."""
        stripped = text.strip()
        if not stripped:
            return stripped
        try:
            payload = _post_chat(
                self._chat_url,
                timeout=self._settings.ollama_timeout_s,
                body={
                    "model": self._settings.ollama_model,
                    "stream": False,
                    "messages": [
                        {"role": "system", "content": system_prompt()},
                        {"role": "user", "content": stripped},
                    ],
                    "options": {"temperature": 0.1, "num_predict": 512},
                },
            )
            out = _assistant_text(payload)
            out = _strip_fences(out)
            return out or stripped
        except Exception:
            return stripped

    def complete(self, prefix: str) -> str:
        """Return a short continuation for the Type field. Empty if unused."""
        stripped = prefix.strip()
        if len(stripped) < 4:
            return ""
        try:
            payload = _post_chat(
                self._chat_url,
                timeout=self._settings.predict_timeout_s,
                body={
                    "model": self._settings.ollama_model,
                    "stream": False,
                    "messages": [
                        {"role": "system", "content": complete_prompt()},
                        {"role": "user", "content": prefix},
                    ],
                    "options": {"temperature": 0.2, "num_predict": 32},
                },
            )
            out = _strip_fences(_assistant_text(payload))
            return continuation_suffix(prefix, out)
        except Exception:
            return ""

    def list_models(self) -> list[str]:
        names = {self._settings.ollama_model}
        payload = _get_json(f"{self._settings.ollama_host.rstrip('/')}/api/tags", timeout=2.0)
        if isinstance(payload, dict):
            models = payload.get("models")
            if isinstance(models, list):
                for item in models:
                    if isinstance(item, dict):
                        name = item.get("name")
                        if isinstance(name, str) and name.strip():
                            names.add(name.strip())
        return sorted(names)


def _get_json(url: str, *, timeout: float) -> object:
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return {}


def _post_chat(url: str, *, timeout: float, body: Mapping[str, Any]) -> object:
    request = urllib.request.Request(
        url,
        data=json.dumps(dict(body)).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return {}


def _assistant_text(payload: object) -> str:
    if not isinstance(payload, dict):
        return ""
    raw_message = payload.get("message")
    if not isinstance(raw_message, dict):
        return ""
    content = raw_message.get("content")
    return content.strip() if isinstance(content, str) else ""



def _strip_fences(text: str) -> str:
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()
