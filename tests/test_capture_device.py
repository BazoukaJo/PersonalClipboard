from personalclipboard.audio.capture import _score_device


def test_maono_outranks_webcam() -> None:
    maono = _score_device("Microphone (Maono AU-PM401)", "Windows WASAPI", "maono")
    webcam = _score_device("Microphone (Logitech Webcam C930e)", "Windows WASAPI", "maono")
    assert maono > webcam


def test_maono_wasapi_outranks_mapper() -> None:
    wasapi = _score_device("Microphone (Maono AU-PM401)", "Windows WASAPI", "maono")
    mapper = _score_device("Microsoft Sound Mapper - Input", "MME", "maono")
    assert wasapi > mapper
