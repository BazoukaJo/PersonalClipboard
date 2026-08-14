"""Background Ollama jobs. Drop results if a newer commit id exists."""

from __future__ import annotations

import queue
import threading
from collections.abc import Callable
from typing import Protocol

_Job = tuple[int, str, str]


class LlmBackend(Protocol):
    def correct(self, text: str) -> str: ...
    def complete(self, prefix: str) -> str: ...


class LlmWorker:
    def __init__(
        self,
        corrector: LlmBackend,
        on_result: Callable[[int, str], None],
        on_complete: Callable[[str, str], None] | None = None,
    ) -> None:
        self._corrector = corrector
        self._on_result = on_result
        self._on_complete = on_complete
        self._queue: queue.Queue[_Job | None] = queue.Queue()
        self._latest = 0
        self._latest_complete = 0
        self._closed = False
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._loop, name="llm-worker", daemon=True)
        self._thread.start()

    def submit(self, text: str) -> int:
        with self._lock:
            self._latest += 1
            self._latest_complete += 1
            job_id = self._latest
        self._queue.put((job_id, "correct", text))
        return job_id

    def submit_complete(self, text: str) -> int:
        with self._lock:
            self._latest_complete += 1
            job_id = self._latest_complete
        self._queue.put((job_id, "complete", text))
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
            job_id, kind, text = item
            if kind == "complete":
                self._run_complete(job_id, text)
                continue
            with self._lock:
                if self._closed or job_id != self._latest:
                    continue
            result = self._corrector.correct(text)
            with self._lock:
                if self._closed or job_id != self._latest:
                    continue
            self._on_result(job_id, result)

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
