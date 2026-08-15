"""Stitch overlapping Whisper windows. Commit only on a completed phrase (period)."""

from __future__ import annotations

from personalclipboard.asr.commands import match_command

_END = (".", "?", "!", "。", "？", "！")
_STRIP = ".,?!:;\"'`“”‘’。？！"
_REVISION_RUN = 2


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

        if not text:
            return self._on_quiet()
        # YouTube/video mix often scores high no_speech / low logprob even when
        # speech is clear. Dictation still gates; records keep stitching.
        if not self._pause_commit and no_speech_prob > no_speech_max:
            return self._on_quiet()

        self._quiet_hops = 0
        if avg_logprob < logprob_min and not self._pause_commit:
            return text, None, "uncertain"

        window = strip_committed(text, self._committed)
        self._acc = stitch(self._acc, window, allow_concat=not self._pause_commit)
        self._acc = strip_committed(self._acc, self._committed)
        if match_command(self._acc) and not self._pause_commit:
            command = self._acc
            self.reset()
            return "", command, "listening"

        # Trailing period on a sliding window is Whisper punctuation, not a
        # sentence end. Meeting/playback wait for a mid-window period or a pause.
        follow = self._pause_commit
        sentence, rest = split_completed(self._acc, self._min_chars, require_follow=follow)
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


def stitch(prev: str, new: str, *, allow_concat: bool = True) -> str:
    """Merge overlapping ASR windows. Public for tests."""
    if not prev:
        return new
    if not new or new == prev:
        return prev
    prev_w = _keyed_words(prev)
    new_w = _keyed_words(new)
    if not new_w:
        return prev
    if not prev_w:
        return new
    prev_k = [key for _word, key in prev_w]
    new_k = [key for _word, key in new_w]
    if _contains(prev_k, new_k):
        return new
    if _contains(new_k, prev_k):
        return prev
    overlap = _prefix_suffix_overlap(prev_k, new_k)
    if overlap:
        kept = [word for word, _key in prev_w[:-overlap]] + [word for word, _key in new_w]
        return " ".join(kept)
    if _longest_run(prev_k, new_k) >= _REVISION_RUN:
        return new if len(new_k) > len(prev_k) else prev
    if not allow_concat:
        return prev if len(prev_k) >= len(new_k) else new
    kept = [word for word, _key in prev_w] + [word for word, _key in new_w]
    return " ".join(kept)


def strip_committed(text: str, committed: list[str]) -> str:
    remaining = text
    for item in committed:
        remaining = _excise_words(remaining, item)
    remaining = _strip_commit_suffix(remaining, committed)
    return " ".join(remaining.split())


def split_completed(
    text: str, min_chars: int, *, require_follow: bool = False
) -> tuple[str | None, str]:
    for i, char in enumerate(text):
        if char not in _END:
            continue
        sentence = text[: i + 1].strip()
        rest = text[i + 1 :].strip()
        if require_follow and not rest:
            continue
        if match_command(sentence) or _alnum_count(sentence) >= min_chars:
            return sentence, rest
    return None, text


def _keyed_words(text: str) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    for word in text.split():
        key = _word_key(word)
        if key:
            items.append((word, key))
    return items


def _word_key(word: str) -> str:
    return word.lower().strip(_STRIP)


def _contains(inner: list[str], outer: list[str]) -> bool:
    count = len(inner)
    if count == 0:
        return True
    if count > len(outer):
        return False
    for index in range(len(outer) - count + 1):
        if outer[index : index + count] == inner:
            return True
    return False


def _prefix_suffix_overlap(left: list[str], right: list[str]) -> int:
    limit = min(len(left), len(right))
    for count in range(limit, 0, -1):
        if left[-count:] == right[:count]:
            return count
    return 0


def _longest_run(left: list[str], right: list[str]) -> int:
    best = 0
    for i, word in enumerate(left):
        for j, other in enumerate(right):
            if word != other:
                continue
            length = 0
            while (
                i + length < len(left)
                and j + length < len(right)
                and left[i + length] == right[j + length]
            ):
                length += 1
            if length > best:
                best = length
    return best


def _excise_words(text: str, chunk: str) -> str:
    hay = _keyed_words(text)
    needle = [key for _word, key in _keyed_words(chunk)]
    if not hay or not needle:
        return text
    count = len(needle)
    for index in range(len(hay) - count + 1):
        keys = [key for _word, key in hay[index : index + count]]
        if keys == needle:
            kept = hay[:index] + hay[index + count :]
            return " ".join(word for word, _key in kept)
    return text


def _strip_commit_suffix(text: str, committed: list[str]) -> str:
    hay = _keyed_words(text)
    if not hay:
        return text
    for item in reversed(committed):
        needle = [key for _word, key in _keyed_words(item)]
        if not needle:
            continue
        limit = min(len(hay), len(needle))
        for count in range(limit, 0, -1):
            head = [key for _word, key in hay[:count]]
            if head == needle[-count:]:
                hay = hay[count:]
                break
    return " ".join(word for word, _key in hay)


def _alnum_count(text: str) -> int:
    return sum(1 for char in text if char.isalnum())
