"""Stored wordings for one committed sentence. Retry never uses ASR partials."""

from __future__ import annotations

MAX_VARIANTS = 8
FIRST_TEMPERATURE = 0.1
RETRY_TEMPERATURE = 0.55


class PhraseBank:
    """Original plus Ollama rewrites. Cycle locally, then request another rewrite."""

    def __init__(self) -> None:
        self.original = ""
        self.items: list[str] = []
        self.index = 0
        self.retrying = False
        self._retries = 0
        self._allow_wrap = True

    def reset(self, original: str) -> None:
        text = original.strip()
        self.original = text
        self.items = [text] if text else []
        self.index = 0
        self.retrying = False
        self._retries = 0
        self._allow_wrap = True

    def current(self) -> str:
        if not self.items:
            return ""
        return self.items[self.index]

    def record(self, text: str) -> str:
        """Keep a unique rewrite and select it. Duplicates move the cursor only."""
        cleaned = text.strip()
        self.retrying = False
        self._allow_wrap = True
        if not cleaned:
            return self.current()
        if cleaned not in self.items:
            self.items.append(cleaned)
        self.index = self.items.index(cleaned)
        if not self.original:
            self.original = cleaned
        return self.current()

    def step(self) -> str | None:
        """Next stored wording, or None when the caller should request another rewrite."""
        if not self.items or self.retrying:
            return None
        if self.index + 1 < len(self.items):
            self.index += 1
            return self.items[self.index]
        if len(self.items) >= MAX_VARIANTS:
            self.index = 0
            self._allow_wrap = False
            return self.items[0]
        if len(self.items) > 1 and self._allow_wrap:
            self._allow_wrap = False
            self.index = 0
            return self.items[0]
        return None

    def begin_retry(self) -> tuple[str, float, int]:
        self.retrying = True
        self._retries += 1
        extra = 0.08 * (self._retries - 1)
        temperature = min(0.9, RETRY_TEMPERATURE + extra)
        seed = 1700 + self._retries * 17
        return self.original, temperature, seed
