from personalclipboard.config import Settings
from personalclipboard.hotkeys.bindings import GlobalHotkeys


def test_bindings_include_reformat_and_type_toggle() -> None:
    settings = Settings()
    keys = GlobalHotkeys(settings, lambda: None, lambda: None).bindings()
    assert keys[settings.hotkey]
    assert keys[settings.type_hotkey]
    assert settings.hotkey != settings.type_hotkey
