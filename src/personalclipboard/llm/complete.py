"""Inline completion for the Type field. Tab accepts; never used on ASR partials."""

from __future__ import annotations

_ENDS = ".?!。？！"


def should_predict(
    text: str,
    *,
    focused: bool,
    enabled: bool,
    blocked: bool,
) -> bool:
    """True only while Type is focused, enabled, and not already a finished sentence."""
    if not focused or not enabled or blocked:
        return False
    stripped = text.strip()
    if len(stripped) < 4:
        return False
    if stripped[-1] in _ENDS:
        return False
    return any(char.isalnum() for char in stripped)


def continuation_suffix(prefix: str, raw: str) -> str:
    """Turn a model reply into a ghost suffix that does not repeat `prefix`."""
    if not prefix.strip() or not raw.strip():
        return ""
    text = " ".join(raw.strip().split())
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'“”‘’":
        text = text[1:-1].strip()
    rest = _without_prefix(prefix, text)
    rest = rest.lstrip()
    if rest.strip().lower() == prefix.strip().lower():
        return ""
    if rest and prefix and not prefix[-1].isspace() and rest[0].isalnum():
        rest = " " + rest
    if len(rest) > 96:
        cut = rest[:96]
        rest = cut.rsplit(" ", 1)[0] if " " in cut.strip() else cut
    return rest


def _without_prefix(prefix: str, text: str) -> str:
    lower_text = text.lower()
    if lower_text.startswith(prefix.lower()):
        return text[len(prefix) :]
    trimmed = prefix.rstrip()
    if trimmed and lower_text.startswith(trimmed.lower()):
        return text[len(trimmed) :]
    last = trimmed.split()[-1].lower() if trimmed.split() else ""
    if last and lower_text.startswith(last):
        return text[len(last) :]
    return text
