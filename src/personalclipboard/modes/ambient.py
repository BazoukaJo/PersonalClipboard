"""Ambient dictation: grammar/punctuation/logic correction. Output is prose."""

AMBIENT_SYSTEM_PROMPT = (
    "You correct a single dictated or typed sentence for a local clipboard. "
    "Fix grammar, punctuation, and word choice so the language is clearer and "
    "has stronger impact. Keep the speaker's meaning. "
    "Return only the corrected sentence, with a period."
)


def prompt(text: str) -> str:
    return text
