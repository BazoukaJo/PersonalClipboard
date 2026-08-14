from personalclipboard.ui.tray import about_body, app_version, restart_command


def test_about_identifies_the_app() -> None:
    body = about_body().lower()
    assert "personalclipboard" in body
    assert app_version() in about_body()
    assert "127.0.0.1" in body
    assert "paste last" in body


def test_restart_relaunches_this_package() -> None:
    cmd = restart_command()
    assert cmd[-2:] == ["-m", "personalclipboard"]
    assert cmd[0]
