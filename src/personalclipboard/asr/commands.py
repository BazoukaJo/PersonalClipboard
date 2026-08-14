"""Voice command detection. Exact phrase after punctuation is stripped."""

from __future__ import annotations

import re

_ALIASES = {
    "paste last": "paste_last",
    "paste last one": "paste_last",
    "copy last": "copy_last",
    "copy last one": "copy_last",
    "correct last": "correct_last",
    "correct last one": "correct_last",
    "fix last": "correct_last",
}


def normalize_phrase(text: str) -> str:
    lowered = text.lower()
    cleaned = re.sub(r"[^a-z0-9 ]+", " ", lowered)
    return re.sub(r"\s+", " ", cleaned).strip()


def match_command(text: str) -> str | None:
    """Return command id or None. Matches the whole phrase only."""
    return _ALIASES.get(normalize_phrase(text))
