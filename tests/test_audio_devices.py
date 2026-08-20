from personalclipboard.audio.devices import list_capture_endpoints, list_render_endpoints, names_match


def test_names_match_allows_truncated_portaudio_labels() -> None:
    assert names_match("Microphone (Maono AU-PM401)", "Microphone (Maono AU-PM40")
    assert not names_match("Microphone (Maono AU-PM401)", "Headphones (JBL)")


def test_endpoint_lists_are_lists() -> None:
    assert isinstance(list_capture_endpoints(), list)
    assert isinstance(list_render_endpoints(), list)
