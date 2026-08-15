import time

from personalclipboard.llm.worker import LlmWorker


class _FakeCorrector:
    def __init__(self, delay_s: float = 0.0) -> None:
        self.delay_s = delay_s
        self.complete_calls: list[str] = []

    def correct(self, text: str, **_kwargs: object) -> str:
        return text

    def complete(self, prefix: str) -> str:
        self.complete_calls.append(prefix)
        if self.delay_s:
            time.sleep(self.delay_s)
        return " next"


def test_stale_complete_is_dropped() -> None:
    fake = _FakeCorrector(delay_s=0.12)
    got: list[str] = []
    worker = LlmWorker(fake, lambda *_args: None, lambda prefix, _s: got.append(prefix))
    worker.submit_complete("The meeting is")
    time.sleep(0.03)
    worker.submit_complete("Please schedule")
    deadline = time.monotonic() + 1.5
    while time.monotonic() < deadline and "Please schedule" not in got:
        time.sleep(0.02)
    worker.shutdown()
    assert got == ["Please schedule"]


def test_correct_invalidates_pending_complete() -> None:
    fake = _FakeCorrector(delay_s=0.12)
    got: list[str] = []
    worker = LlmWorker(fake, lambda *_args: None, lambda prefix, _s: got.append(prefix))
    worker.submit_complete("The meeting is")
    time.sleep(0.03)
    worker.submit("Done.")
    time.sleep(0.4)
    worker.shutdown()
    assert got == []


def test_submit_passes_retry_options() -> None:
    class Recording:
        def __init__(self) -> None:
            self.kwargs: dict[str, object] = {}

        def correct(self, text: str, **kwargs: object) -> str:
            self.kwargs = {"text": text, **kwargs}
            return text

        def complete(self, prefix: str) -> str:
            return ""

    fake = Recording()
    got: list[str] = []
    worker = LlmWorker(fake, lambda _jid, text: got.append(text))
    worker.submit("Hello.", temperature=0.55, seed=1717, vary=True)
    deadline = time.monotonic() + 1.5
    while time.monotonic() < deadline and not got:
        time.sleep(0.02)
    worker.shutdown()
    assert got == ["Hello."]
    assert fake.kwargs["text"] == "Hello."
    assert fake.kwargs["temperature"] == 0.55
    assert fake.kwargs["seed"] == 1717
    assert fake.kwargs["vary"] is True
    assert fake.kwargs["mode"] == "human"


def test_submit_passes_ai_mode() -> None:
    class Recording:
        def __init__(self) -> None:
            self.mode = ""

        def correct(self, text: str, **kwargs: object) -> str:
            self.mode = str(kwargs.get("mode", ""))
            return text

        def complete(self, prefix: str) -> str:
            return ""

    fake = Recording()
    got: list[str] = []
    worker = LlmWorker(fake, lambda _jid, text: got.append(text))
    worker.submit("Write a summary.", mode="ai")
    deadline = time.monotonic() + 1.5
    while time.monotonic() < deadline and not got:
        time.sleep(0.02)
    worker.shutdown()
    assert got == ["Write a summary."]
    assert fake.mode == "ai"


def test_record_jobs_are_not_dropped() -> None:
    got: list[str] = []
    fake = _FakeCorrector()
    worker = LlmWorker(fake, lambda *_args: None, on_record=got.append)
    worker.submit_record("First sentence.")
    worker.submit_record("Second sentence.")
    deadline = time.monotonic() + 1.5
    while time.monotonic() < deadline and len(got) < 2:
        time.sleep(0.02)
    worker.shutdown()
    assert got == ["First sentence.", "Second sentence."]
