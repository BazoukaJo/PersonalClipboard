from personalclipboard.ui.tray import about_body, app_version, restart_command


def test_about_identifies_the_app() -> None:
    body = about_body().lower()
    assert "personalclipboard" in body
    assert app_version() in about_body()
    assert "127.0.0.1" in body
    assert "paste last" in body
    assert "tab" in body
    assert "ctrl+shift+r" in body


def test_restart_uses_exe_or_module() -> None:
    cmd = restart_command()
    assert cmd[0]
    if len(cmd) == 1 and cmd[0].lower().endswith(".exe"):
        assert "personalclipboard" in cmd[0].lower()
        return
    assert cmd[-2:] == ["-m", "personalclipboard"]
