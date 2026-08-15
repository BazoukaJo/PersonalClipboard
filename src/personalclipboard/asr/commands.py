"""Voice and Type command detection. Exact phrase after punctuation is stripped."""

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
    "translate": "translate",
    "translate last": "translate",
    "translate last one": "translate",
    "traduire": "translate",
    "traduire dernier": "translate",
    "traduis": "translate",
    "traducir": "translate",
    "traducir ultimo": "translate",
    "traducir último": "translate",
    "traduce": "translate",
    "summarize": "summarize",
    "summarize last": "summarize",
    "summarise": "summarize",
    "summarise last": "summarize",
    "resumer": "summarize",
    "résumer": "summarize",
    "resume": "summarize",
    "resumer dernier": "summarize",
    "résumer dernier": "summarize",
    "resumir": "summarize",
    "resumir ultimo": "summarize",
    "resumir último": "summarize",
    "shorter": "shorter",
    "make it shorter": "shorter",
    "shorten last": "shorter",
    "shorten": "shorter",
    "plus court": "shorter",
    "raccourcir": "shorter",
    "mas corto": "shorter",
    "más corto": "shorter",
    "acortar": "shorter",
    "bullets": "bullets",
    "bullet list": "bullets",
    "make a list": "bullets",
    "liste": "bullets",
    "puces": "bullets",
    "faire une liste": "bullets",
    "lista": "bullets",
    "vinetas": "bullets",
    "viñetas": "bullets",
    "hacer una lista": "bullets",
    "email": "email",
    "as an email": "email",
    "email tone": "email",
    "courriel": "email",
    "comme un email": "email",
    "correo": "email",
    "como un correo": "email",
}

REWRITE_COMMANDS = frozenset(
    {"translate", "summarize", "shorter", "bullets", "email"}
)


def normalize_phrase(text: str) -> str:
    lowered = text.casefold()
    cleaned = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in lowered)
    return re.sub(r"\s+", " ", cleaned).strip()


def match_command(text: str) -> str | None:
    """Whole-phrase match only, so 'paste last' inside a sentence is not a command."""
    return _ALIASES.get(normalize_phrase(text))
