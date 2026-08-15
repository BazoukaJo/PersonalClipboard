"""Ollama system prompts: prose correction, AI reformulation, Type continuation."""

from personalclipboard.modes.ambient import AI_SYSTEM_PROMPT, AMBIENT_SYSTEM_PROMPT
from personalclipboard.modes.complete import COMPLETE_SYSTEM_PROMPT


def system_prompt(mode: str = "human") -> str:
    if mode == "ai":
        return AI_SYSTEM_PROMPT
    return AMBIENT_SYSTEM_PROMPT


def complete_prompt() -> str:
    return COMPLETE_SYSTEM_PROMPT
