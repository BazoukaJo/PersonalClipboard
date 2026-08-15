from personalclipboard.asr.commands import match_command, normalize_phrase


def test_normalize_strips_punctuation() -> None:
    assert normalize_phrase("Paste last.") == "paste last"
    assert normalize_phrase("  COPY LAST!  ") == "copy last"
    assert normalize_phrase("Résumer.") == "résumer"


def test_match_known_commands() -> None:
    assert match_command("paste last") == "paste_last"
    assert match_command("Paste last.") == "paste_last"
    assert match_command("copy last one") == "copy_last"
    assert match_command("correct last") == "correct_last"
    assert match_command("fix last") == "correct_last"


def test_match_rewrite_commands() -> None:
    assert match_command("translate") == "translate"
    assert match_command("Translate last.") == "translate"
    assert match_command("traduire") == "translate"
    assert match_command("traducir último") == "translate"
    assert match_command("summarize last") == "summarize"
    assert match_command("résumer") == "summarize"
    assert match_command("make it shorter") == "shorter"
    assert match_command("plus court") == "shorter"
    assert match_command("bullet list") == "bullets"
    assert match_command("faire une liste") == "bullets"
    assert match_command("as an email") == "email"
    assert match_command("como un correo") == "email"


def test_non_command_is_none() -> None:
    assert match_command("please paste last tomorrow") is None
    assert match_command("hello there.") is None
    assert match_command("please translate this tomorrow") is None
