"""Background Ollama jobs. Drop results if a newer commit id exists."""

from __future__ import annotations

import queue
import threading
from collections.abc import Callable

from personalclipboard.llm.corrector import Corrector


class LlmWorker:
    def __init__(
        self,
        corrector: Corrector,
        on_result: Callable[[int, str], None],
    ) -> None:
        self._corrector = corrector
        self._on_result = on_result
        self._queue: queue.Queue[tuple[int, str] | None] = queue.Queue()
        self._latest = 0
        self._closed = False
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._loop, name="llm-worker", daemon=True)
        self._thread.start()

    def submit(self, text: str) -> int:
        with self._lock:
            self._latest += 1
            job_id = self._latest
        self._queue.put((job_id, text))
        return job_id

    def shutdown(self) -> None:
        with self._lock:
            self._latest += 1
            self._closed = True
        self._queue.put(None)

    def _loop(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                return
            job_id, text = item
            with self._lock:
                if self._closed or job_id != self._latest:
                    continue
            result = self._corrector.correct(text)
            with self._lock:
                if self._closed or job_id != self._latest:
                    continue
            self._on_result(job_id, result)
