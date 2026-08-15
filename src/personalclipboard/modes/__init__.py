"""Ollama system prompts: prose correction, AI reformulation, Type continuation."""

from personalclipboard.modes.ambient import AI_SYSTEM_PROMPT, AMBIENT_SYSTEM_PROMPT
from personalclipboard.modes.complete import COMPLETE_SYSTEM_PROMPT
from personalclipboard.modes.rewrite import (
    BULLETS_PROMPT,
    EMAIL_PROMPT,
    SHORTER_PROMPT,
    SUMMARIZE_PROMPT,
    translate_prompt,
)

_REWRITE = {
    "summarize": SUMMARIZE_PROMPT,
    "shorter": SHORTER_PROMPT,
    "bullets": BULLETS_PROMPT,
    "email": EMAIL_PROMPT,
}


def system_prompt(mode: str = "human", *, lang: str = "en") -> str:
    if mode == "ai":
        return AI_SYSTEM_PROMPT
    if mode == "translate":
        return translate_prompt(lang)
    rewrite = _REWRITE.get(mode)
    if rewrite is not None:
        return rewrite
    return AMBIENT_SYSTEM_PROMPT


def complete_prompt() -> str:
    return COMPLETE_SYSTEM_PROMPT
