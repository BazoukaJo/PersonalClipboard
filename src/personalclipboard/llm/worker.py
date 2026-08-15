"""Background Ollama jobs. Newer job ids drop in-flight results."""

from __future__ import annotations

import queue
import threading
from collections.abc import Callable
from typing import NamedTuple, Protocol


class _Job(NamedTuple):
    job_id: int
    kind: str
    text: str
    temperature: float = 0.1
    seed: int | None = None
    vary: bool = False
    mode: str = "human"


class LlmBackend(Protocol):
    def correct(
        self,
        text: str,
        *,
        temperature: float = 0.1,
        seed: int | None = None,
        vary: bool = False,
        mode: str = "human",
    ) -> str: ...
    def complete(self, prefix: str) -> str: ...


class LlmWorker:
    def __init__(
        self,
        corrector: LlmBackend,
        on_result: Callable[[int, str], None],
        on_complete: Callable[[str, str], None] | None = None,
        on_record: Callable[[str], None] | None = None,
    ) -> None:
        self._corrector = corrector
        self._on_result = on_result
        self._on_complete = on_complete
        self._on_record = on_record
        self._queue: queue.Queue[_Job | None] = queue.Queue()
        self._latest = 0
        self._latest_complete = 0
        self._closed = False
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._loop, name="llm-worker", daemon=True)
        self._thread.start()

    def submit(
        self,
        text: str,
        *,
        temperature: float = 0.1,
        seed: int | None = None,
        vary: bool = False,
        mode: str = "human",
    ) -> int:
        with self._lock:
            self._latest += 1
            # A committed sentence must not keep showing a stale Type ghost.
            self._latest_complete += 1
            job_id = self._latest
        kind = mode.strip() or "human"
        self._queue.put(_Job(job_id, "correct", text, temperature, seed, vary, kind))
        return job_id

    def submit_record(self, text: str) -> int:
        """Correct a meeting/playback phrase. Does not drop earlier record jobs."""
        stripped = text.strip()
        if not stripped:
            return 0
        with self._lock:
            self._latest_complete += 1
            job_id = self._latest + 1
        self._queue.put(_Job(job_id, "record", stripped))
        return job_id

    def submit_complete(self, text: str) -> int:
        with self._lock:
            self._latest_complete += 1
            job_id = self._latest_complete
        self._queue.put(_Job(job_id, "complete", text))
        return job_id

    def shutdown(self) -> None:
        with self._lock:
            self._latest += 1
            self._latest_complete += 1
            self._closed = True
        self._queue.put(None)

    def _loop(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                return
            if item.kind == "complete":
                self._run_complete(item.job_id, item.text)
                continue
            if item.kind == "record":
                self._run_record(item.text)
                continue
            with self._lock:
                if self._closed or item.job_id != self._latest:
                    continue
            result = self._corrector.correct(
                item.text,
                temperature=item.temperature,
                seed=item.seed,
                vary=item.vary,
                mode=item.mode,
            )
            with self._lock:
                if self._closed or item.job_id != self._latest:
                    continue
            self._on_result(item.job_id, result)

    def _run_complete(self, job_id: int, text: str) -> None:
        with self._lock:
            if self._closed or job_id != self._latest_complete or self._on_complete is None:
                return
        suffix = self._corrector.complete(text)
        with self._lock:
            if self._closed or job_id != self._latest_complete or self._on_complete is None:
                return
        if suffix:
            self._on_complete(text, suffix)

    def _run_record(self, text: str) -> None:
        with self._lock:
            if self._closed or self._on_record is None:
                return
        result = self._corrector.correct(text, mode="human")
        with self._lock:
            if self._closed or self._on_record is None:
                return
        if result.strip():
            self._on_record(result)
