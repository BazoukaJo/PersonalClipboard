"""Stitch overlapping Whisper windows. Commit only on a completed phrase (period)."""

from __future__ import annotations

from personalclipboard.asr.commands import match_command

_END = (".", "?", "!", "。", "？", "！")


class SentenceAssembler:
    def __init__(self, min_chars: int = 4) -> None:
        self._min_chars = min_chars
        self._acc = ""
        self._committed: list[str] = []
        self._pause_commit = False
        self._quiet_hops = 0

    def reset(self) -> None:
        self._acc = ""
        self._committed = []
        self._quiet_hops = 0

    def set_pause_commit(self, enabled: bool) -> None:
        self._pause_commit = enabled
        self._quiet_hops = 0

    def take_remainder(self) -> str:
        text = self._acc.strip()
        self._acc = ""
        self._quiet_hops = 0
        if text:
            self._committed.append(text)
        return text

    def update(
        self,
        text: str,
        no_speech_prob: float,
        avg_logprob: float,
        *,
        no_speech_max: float,
        logprob_min: float,
    ) -> tuple[str, str | None, str]:
        """Return (partial, commit_or_none, status). Commits only on . ? !"""
        text = " ".join(text.split())
        if match_command(text) and not self._pause_commit:
            self.reset()
            return "", text, "listening"

        quiet = no_speech_prob > no_speech_max or not text
        if quiet:
            return self._on_quiet()

        self._quiet_hops = 0
        if avg_logprob < logprob_min:
            return text, None, "uncertain"

        window = _strip_commits(text, self._committed)
        self._acc = _stitch(self._acc, window)
        self._acc = _strip_commits(self._acc, self._committed)
        if match_command(self._acc) and not self._pause_commit:
            command = self._acc
            self.reset()
            return "", command, "listening"

        sentence, rest = _split_completed(self._acc, self._min_chars)
        if sentence is not None:
            self._remember(sentence)
            self._acc = rest
            return rest, sentence, "listening"

        return self._acc, None, "listening"

    def _on_quiet(self) -> tuple[str, str | None, str]:
        self._quiet_hops += 1
        if not self._pause_commit or self._quiet_hops < 3:
            return self._acc, None, "listening"
        text = self._acc.strip()
        if _alnum_count(text) < self._min_chars:
            return self._acc, None, "listening"
        self._remember(text)
        self._acc = ""
        self._quiet_hops = 0
        return "", text, "listening"

    def _remember(self, sentence: str) -> None:
        self._committed.append(sentence)
        if len(self._committed) > 8:
            self._committed = self._committed[-8:]


def _stitch(prev: str, new: str) -> str:
    if not prev:
        return new
    if not new or new == prev:
        return prev
    if prev in new:
        return new
    if new in prev:
        return prev
    previous_words = prev.split()
    new_words = new.split()
    max_ol = min(len(previous_words), len(new_words))
    for count in range(max_ol, 0, -1):
        left = [word.lower() for word in previous_words[-count:]]
        right = [word.lower() for word in new_words[:count]]
        if left == right:
            return " ".join(previous_words + new_words[count:])
    return " ".join(previous_words + new_words)


def _strip_commits(text: str, committed: list[str]) -> str:
    remaining = text
    for item in committed:
        remaining = _excise(remaining, item)
    return " ".join(remaining.split())


def _excise(text: str, chunk: str) -> str:
    if not chunk or not text:
        return text
    idx = text.lower().find(chunk.lower())
    if idx < 0:
        return text
    return (text[:idx] + " " + text[idx + len(chunk) :]).strip()


def _alnum_count(text: str) -> int:
    return sum(1 for char in text if char.isalnum())


def _split_completed(text: str, min_chars: int) -> tuple[str | None, str]:
    for i, char in enumerate(text):
        if char not in _END:
            continue
        sentence = text[: i + 1].strip()
        rest = text[i + 1 :].strip()
        if match_command(sentence) or _alnum_count(sentence) >= min_chars:
            return sentence, rest
    return None, text
