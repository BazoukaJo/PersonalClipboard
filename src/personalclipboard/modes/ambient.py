"""Sentence correction prompts: human prose vs AI reformulation."""

AMBIENT_SYSTEM_PROMPT = (
    "You correct a single dictated or typed sentence for a person to read. "
    "Fix grammar, punctuation, and obvious mistakes. Keep the speaker's wording, "
    "tone, meaning, and language (English, French, Chinese, or mixed in one sentence). "
    "Do not translate. Do not rewrite it in a new style. Do not add or remove facts. "
    "Return only the corrected text, using the original script's punctuation "
    "(period, question mark, or 。？！)."
)

AI_SYSTEM_PROMPT = (
    "You fully reformulate a single sentence so it is an effective prompt or "
    "instruction for another AI. Make the intent explicit, unambiguous, and "
    "well-structured. Keep the original meaning. Do not answer the request. "
    "Return only the rewritten sentence, with a period."
)


def prompt(text: str) -> str:
    return text
