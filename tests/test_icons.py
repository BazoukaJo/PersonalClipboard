from personalclipboard.ui.icons import make_icon, make_pixmap


def test_lucide_icons_render(qapp) -> None:
    assert qapp is not None
    for name in ("user", "sparkles", "refresh-cw", "x", "mic", "mic-off", "languages"):
        pixmap = make_pixmap(name, 16)
        assert not pixmap.isNull(), name
        assert int(round(pixmap.width() / pixmap.devicePixelRatio())) == 16
        icon = make_icon(name, 16)
        assert not icon.isNull(), name
