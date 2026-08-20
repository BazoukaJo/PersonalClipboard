from personalclipboard.audio.devices import (
    AudioEndpoint,
    labeled_endpoints,
    list_capture_endpoints,
    list_render_endpoints,
    names_match,
)


def test_names_match_allows_truncated_portaudio_labels() -> None:
    assert names_match("Microphone (Maono AU-PM401)", "Microphone (Maono AU-PM40")
    assert not names_match("Microphone (Maono AU-PM401)", "Headphones (JBL)")


def test_endpoint_lists_are_lists() -> None:
    assert isinstance(list_capture_endpoints(), list)
    assert isinstance(list_render_endpoints(), list)


def test_labeled_endpoints_keeps_default_plus_duplicates() -> None:
    items = [
        AudioEndpoint("{a}", "NVIDIA Output", True),
        AudioEndpoint("{b}", "NVIDIA Output", False),
        AudioEndpoint("{c}", "Headphones (JBL)", True),
    ]
    labeled = labeled_endpoints(items)
    assert labeled[0] == ("{a}", "NVIDIA Output [1]", "NVIDIA Output")
    assert labeled[1] == ("{b}", "NVIDIA Output [2]", "NVIDIA Output")
    assert labeled[2] == ("{c}", "Headphones (JBL)", "Headphones (JBL)")
