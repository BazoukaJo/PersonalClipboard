from personalclipboard.ui.win11_resize import HTLEFT, HTRIGHT, resize_hit, unpack_nchittest_point


def test_resize_hit_is_width_only() -> None:
    assert resize_hit(2, 2, 400, 300) == HTLEFT
    assert resize_hit(398, 2, 400, 300) == HTRIGHT
    assert resize_hit(2, 298, 400, 300) == HTLEFT
    assert resize_hit(200, 2, 400, 300) is None
    assert resize_hit(398, 150, 400, 300) == HTRIGHT
    assert resize_hit(200, 150, 400, 300) is None
    assert resize_hit(200, 298, 400, 300) is None


def test_unpack_nchittest_point_low_word() -> None:
    x, y = unpack_nchittest_point(100 | (200 << 16))
    assert x == 100
    assert y == 200
