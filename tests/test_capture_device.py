from personalclipboard.audio.capture import AudioCapture, _score_device
from personalclipboard.config import Settings


def test_maono_outranks_webcam() -> None:
    maono = _score_device("Microphone (Maono AU-PM401)", "Windows WASAPI", "maono")
    webcam = _score_device("Microphone (Logitech Webcam C930e)", "Windows WASAPI", "maono")
    assert maono > webcam


def test_maono_wasapi_outranks_mapper() -> None:
    wasapi = _score_device("Microphone (Maono AU-PM401)", "Windows WASAPI", "maono")
    mapper = _score_device("Microsoft Sound Mapper - Input", "MME", "maono")
    assert wasapi > mapper


def test_start_falls_back_to_sounddevice(monkeypatch) -> None:
    cap = AudioCapture(Settings())

    def fail_pyaudio() -> None:
        raise OSError("pyaudio missing")

    class FakeStream:
        active = True

        def stop(self) -> None:
            self.active = False

        def close(self) -> None:
            return None

    def fake_sd() -> None:
        cap._sd_stream = FakeStream()  # pylint: disable=protected-access
        cap.backend = "sounddevice"
        cap.device_name = "sd-mic"

    monkeypatch.setattr(cap, "_start_pyaudio", fail_pyaudio)
    monkeypatch.setattr(cap, "_start_sounddevice", fake_sd)
    cap.start()
    assert cap.backend == "sounddevice"
    assert cap.active is True
    cap.stop()
    assert cap.active is False


def test_start_raises_when_both_backends_fail(monkeypatch) -> None:
    cap = AudioCapture(Settings())

    def fail_pyaudio() -> None:
        raise OSError("py")

    def fail_sd() -> None:
        raise OSError("sd")

    monkeypatch.setattr(cap, "_start_pyaudio", fail_pyaudio)
    monkeypatch.setattr(cap, "_start_sounddevice", fail_sd)
    try:
        cap.start()
        raise AssertionError("expected OSError")
    except OSError as exc:
        assert "PyAudio" in str(exc)
        assert "sounddevice" in str(exc)
