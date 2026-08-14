"""Dictation correction prompt."""

from personalclipboard.modes.ambient import AMBIENT_SYSTEM_PROMPT
from personalclipboard.modes.complete import COMPLETE_SYSTEM_PROMPT


def system_prompt() -> str:
    return AMBIENT_SYSTEM_PROMPT


def complete_prompt() -> str:
    return COMPLETE_SYSTEM_PROMPT
