"""Local clipboard history. Oldest text is dropped so the file stays ≤ 20 MB."""

from __future__ import annotations

import queue
import threading
from datetime import datetime
from pathlib import Path

HISTORY_MAX_BYTES = 20 * 1024 * 1024


def format_entry(text: str, when: datetime | None = None) -> str:
    stamp = (when or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")
    body = text.replace("\r\n", "\n").strip()
    return f"{stamp}\n{body}\n\n"


def trim_history_bytes(data: bytes, max_bytes: int = HISTORY_MAX_BYTES) -> bytes:
    if max_bytes <= 0:
        return b""
    if len(data) <= max_bytes:
        return data
    chunk = _valid_utf8(data[-max_bytes:])
    if _starts_complete_entry(chunk):
        return chunk
    sep = chunk.find(b"\n\n")
    if 0 <= sep < len(chunk) - 2:
        return chunk[sep + 2 :]
    return chunk


def _starts_complete_entry(chunk: bytes) -> bool:
    if len(chunk) < 20:
        return False
    try:
        datetime.strptime(chunk[:19].decode("ascii"), "%Y-%m-%d %H:%M:%S")
    except (UnicodeDecodeError, ValueError):
        return False
    return chunk[19:20] == b"\n"


def parse_entries(raw: str) -> list[tuple[str, str]]:
    """Split history.txt into (timestamp, complete text) oldest-first."""
    entries: list[tuple[str, str]] = []
    stamp = ""
    body: list[str] = []
    for line in raw.splitlines():
        if _is_stamp_line(line):
            _flush_entry(entries, stamp, body)
            stamp = line
            body = []
            continue
        if stamp:
            body.append(line)
    _flush_entry(entries, stamp, body)
    return entries


def _is_stamp_line(line: str) -> bool:
    if len(line) != 19:
        return False
    try:
        datetime.strptime(line, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return False
    return True


def _flush_entry(entries: list[tuple[str, str]], stamp: str, body: list[str]) -> None:
    if not stamp:
        return
    text = "\n".join(body).strip()
    if text:
        entries.append((stamp, text))


def _valid_utf8(chunk: bytes) -> bytes:
    while chunk:
        try:
            chunk.decode("utf-8")
            return chunk
        except UnicodeDecodeError:
            chunk = chunk[1:]
    return b""


class ClipboardHistory:
    """Append clipboard text off the Qt thread. Caps the file at max_bytes."""

    def __init__(
        self,
        path: Path,
        *,
        max_bytes: int = HISTORY_MAX_BYTES,
        threaded: bool = True,
    ) -> None:
        self.path = path
        self.max_bytes = max_bytes
        self._threaded = threaded
        self._queue: queue.Queue[str | None] = queue.Queue()
        if threaded:
            worker = threading.Thread(target=self._run, name="clipboard-history", daemon=True)
            worker.start()
            self._worker = worker
        else:
            self._worker = None

    def append(self, text: str) -> None:
        if not text.strip():
            return
        if self._threaded:
            self._queue.put(text)
            return
        self._record(text)

    def ensure_file(self) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.is_file():
            self.path.write_text("", encoding="utf-8")
        return self.path

    def entries(self) -> list[tuple[str, str]]:
        try:
            if not self.path.is_file():
                return []
            raw = self.path.read_text(encoding="utf-8")
        except OSError:
            return []
        return parse_entries(raw)

    def close(self) -> None:
        if self._threaded:
            self._queue.put(None)

    def _run(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                return
            self._record(item)

    def _record(self, text: str, when: datetime | None = None) -> None:
        entry = format_entry(text, when).encode("utf-8")
        try:
            existing = self.path.read_bytes() if self.path.is_file() else b""
        except OSError:
            existing = b""
        payload = trim_history_bytes(existing + entry, self.max_bytes)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        scratch = self.path.with_name(self.path.name + ".tmp")
        scratch.write_bytes(payload)
        scratch.replace(self.path)
