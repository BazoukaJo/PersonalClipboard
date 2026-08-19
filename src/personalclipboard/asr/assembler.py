"""Stitch overlapping Whisper windows. Commit only on a completed phrase (period)."""

from __future__ import annotations

from difflib import SequenceMatcher

from personalclipboard.asr.commands import match_command

_END = (".", "?", "!", "。", "？", "！")
_STRIP = ".,?!:;\"'`“”‘’。？！，、；："
_REVISION_RUN = 2
_SIMILAR_REVISION = 0.62
_LINE_NEAR = 0.9


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
            emitted = self._remember(sentence)
            self._acc = rest
            return rest, emitted, "listening"

        return self._acc, None, "listening"

    def _on_quiet(self) -> tuple[str, str | None, str]:
        self._quiet_hops += 1
        if not self._pause_commit or self._quiet_hops < 3:
            return self._acc, None, "listening"
        text = self._acc.strip()
        if _alnum_count(text) < self._min_chars:
            return self._acc, None, "listening"
        emitted = self._remember(text)
        self._acc = ""
        self._quiet_hops = 0
        return "", emitted, "listening"

    def _remember(self, sentence: str) -> str | None:
        if self._committed:
            action = record_line_action(sentence, self._committed[-1])
            if action == "skip":
                return None
            if action == "replace":
                self._committed[-1] = sentence
                return sentence
        self._committed.append(sentence)
        if len(self._committed) > 16:
            self._committed = self._committed[-16:]
        return sentence


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
        kept = prev_w[:-overlap] + new_w
        return _join_keyed(kept)
    if _longest_run(prev_k, new_k) >= _REVISION_RUN:
        return new if len(new_k) > len(prev_k) else prev
    if SequenceMatcher(None, _fold(prev), _fold(new)).ratio() >= _SIMILAR_REVISION:
        return new if len(new_k) >= len(prev_k) else prev
    if not allow_concat and len(new_k) < 4 and len(prev_k) >= len(new_k):
        return prev
    kept = prev_w + new_w
    return _join_keyed(kept)


def strip_committed(text: str, committed: list[str]) -> str:
    remaining = text
    for item in committed:
        remaining = _excise_words(remaining, item)
    remaining = _strip_commit_suffix(remaining, committed)
    return _join_keyed(_keyed_words(remaining))


def record_line_action(new: str, previous: str) -> str:
    """How a new record phrase relates to the last written line: skip, replace, or append."""
    if not previous.strip():
        return "append"
    new_k = [key for _word, key in _keyed_words(new)]
    prev_k = [key for _word, key in _keyed_words(previous)]
    if not new_k:
        return "skip"
    if not prev_k:
        return "append"
    if new_k == prev_k:
        return "skip"
    if _contains(new_k, prev_k):
        return "skip"
    if _contains(prev_k, new_k):
        return "replace"
    if SequenceMatcher(None, _fold(previous), _fold(new)).ratio() >= _LINE_NEAR:
        return "replace" if len(new_k) > len(prev_k) else "skip"
    shorter = min(len(new_k), len(prev_k))
    union = len(set(new_k) | set(prev_k))
    shared = len(set(new_k) & set(prev_k))
    if shorter >= 6 and union and shared / union >= 0.86:
        return "replace" if len(new_k) > len(prev_k) else "skip"
    return "append"


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
    for chunk in text.split():
        items.extend(_expand_chunk(chunk))
    return items


def _expand_chunk(chunk: str) -> list[tuple[str, str]]:
    if not any(_is_cjk_letter(char) for char in chunk):
        key = _word_key(chunk)
        return [(chunk, key)] if key else []
    items: list[tuple[str, str]] = []
    buf: list[str] = []

    def flush_latin() -> None:
        if not buf:
            return
        word = "".join(buf)
        buf.clear()
        key = _word_key(word)
        if key:
            items.append((word, key))

    for char in chunk:
        if _is_cjk_letter(char):
            flush_latin()
            items.append((char, char))
            continue
        if items and not buf:
            word, key = items[-1]
            items[-1] = (word + char, key)
            continue
        buf.append(char)
    flush_latin()
    return items


def _word_key(word: str) -> str:
    return word.lower().strip(_STRIP)


def _is_cjk_letter(char: str) -> bool:
    code = ord(char)
    return (
        0x3040 <= code <= 0x30FF
        or 0x3400 <= code <= 0x4DBF
        or 0x4E00 <= code <= 0x9FFF
        or 0xF900 <= code <= 0xFAFF
        or 0xAC00 <= code <= 0xD7AF
        or 0x20000 <= code <= 0x2FA1F
    )


def _join_keyed(items: list[tuple[str, str]]) -> str:
    if not items:
        return ""
    parts = [items[0][0]]
    for index in range(1, len(items)):
        prev = items[index - 1][0]
        current = items[index][0]
        if _cjk_glue(prev, current):
            parts.append(current)
        else:
            parts.append(" ")
            parts.append(current)
    return "".join(parts)


def _cjk_glue(left: str, right: str) -> bool:
    if _is_cjk_letter(left[-1]) and _is_cjk_letter(right[0]):
        return True
    if _is_cjk_letter(left[-1]) and right[0] in _STRIP:
        return True
    if left[-1] in _STRIP and _is_cjk_letter(right[0]):
        return True
    return False


def _fold(text: str) -> str:
    return " ".join(key for _word, key in _keyed_words(text))


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
            return _join_keyed(kept)
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
    return _join_keyed(hay)


def _alnum_count(text: str) -> int:
    return sum(1 for char in text if char.isalnum())
