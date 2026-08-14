from personalclipboard.ui.win11_resize import resize_hit, unpack_nchittest_point


def test_resize_hit_corners_and_edges() -> None:
    assert resize_hit(2, 2, 400, 300) is not None
    assert resize_hit(398, 2, 400, 300) is not None
    assert resize_hit(2, 298, 400, 300) is not None
    assert resize_hit(200, 2, 400, 300) is not None
    assert resize_hit(398, 150, 400, 300) is not None
    assert resize_hit(200, 150, 400, 300) is None


def test_unpack_nchittest_point_low_word() -> None:
    x, y = unpack_nchittest_point(100 | (200 << 16))
    assert x == 100
    assert y == 200
