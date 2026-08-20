from personalclipboard.audio.capture import AudioCapture, _score_device
from personalclipboard.config import Settings


def test_maono_outranks_webcam() -> None:
    maono = _score_device("Microphone (Maono AU-PM401)", "Windows WASAPI", "maono")
    webcam = _score_device("Microphone (Logitech Webcam C930e)", "Windows WASAPI", "maono")
    assert maono > webcam


def test_saved_mic_name_outranks_maono() -> None:
    chosen = _score_device("Microphone (USB Conference)", "Windows WASAPI", "Microphone (USB Conference)")
    maono = _score_device("Microphone (Maono AU-PM401)", "Windows WASAPI", "Microphone (USB Conference)")
    assert chosen > maono
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


class _FakeLoopback:
    def __init__(self) -> None:
        self.active = False
        self.device_name = "Headphones (JBL)"
        self.stopped = False

    def start(self) -> None:
        self.active = True

    def stop(self) -> None:
        self.active = False
        self.stopped = True


def test_start_loopback_uses_render_capture(monkeypatch) -> None:
    cap = AudioCapture(Settings())
    fake = _FakeLoopback()
    monkeypatch.setattr(
        "personalclipboard.audio.loopback.LoopbackCapture",
        lambda *_args, **_kwargs: fake,
    )
    assert cap.start_loopback() is True
    assert cap.loopback_active is True
    assert cap.loopback_name == "Headphones (JBL)"
    cap.stop()
    assert fake.stopped is False
    assert cap.loopback_active is True
    cap.stop_loopback()
    assert fake.stopped is True
    assert cap.loopback_active is False


def test_start_loopback_passes_saved_output_id(monkeypatch) -> None:
    seen: list[str] = []

    class Capture(_FakeLoopback):
        def __init__(self, _ring, _rate, device_id: str = "") -> None:
            super().__init__()
            seen.append(device_id)

    cap = AudioCapture(Settings(output_device_id="{speakers}"))
    monkeypatch.setattr("personalclipboard.audio.loopback.LoopbackCapture", Capture)
    assert cap.start_loopback() is True
    assert seen == ["{speakers}"]


def test_start_loopback_fail_open(monkeypatch) -> None:
    cap = AudioCapture(Settings())

    class Boom(_FakeLoopback):
        def start(self) -> None:
            raise OSError("no wasapi")

    monkeypatch.setattr(
        "personalclipboard.audio.loopback.LoopbackCapture",
        lambda *_args, **_kwargs: Boom(),
    )
    assert cap.start_loopback() is False
    assert cap.loopback_active is False
