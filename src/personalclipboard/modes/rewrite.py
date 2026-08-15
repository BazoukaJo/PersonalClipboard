"""Ollama prompts for explicit rewrite actions on committed text."""

_LANG_NAMES = {"en": "English", "fr": "French", "es": "Spanish"}

SUMMARIZE_PROMPT = (
    "Summarize the text in one or two short sentences. Keep the meaning. "
    "Do not add facts. Return only the summary."
)

SHORTER_PROMPT = (
    "Rewrite the text so it is shorter. Keep the meaning and tone. "
    "Do not add facts. Return only the shorter text."
)

BULLETS_PROMPT = (
    "Rewrite the text as a short bullet list. Keep the meaning. "
    "Do not add facts. Return only the bullet list."
)

EMAIL_PROMPT = (
    "Rewrite the text as a brief professional email. Keep the meaning. "
    "Do not invent recipients, names, or facts. Return only the email body."
)


def translate_prompt(lang: str) -> str:
    name = _LANG_NAMES.get(lang, "English")
    return (
        f"Translate the text into {name}. Keep meaning, names, and numbers. "
        "Do not add commentary. Return only the translation."
    )
