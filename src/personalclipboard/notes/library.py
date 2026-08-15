"""Index desktop meeting/playback transcripts for the Records modal."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from personalclipboard.notes.meeting import desktop_directory


@dataclass(frozen=True)
class RecordInfo:
    path: Path
    kind: str
    title: str
    started: str
    preview: str
    body: str

    @property
    def filename(self) -> str:
        return self.path.name


def list_records(directory: Path | None = None) -> list[RecordInfo]:
    folder = directory if directory is not None else desktop_directory()
    if not folder.is_dir():
        return []
    items: list[RecordInfo] = []
    for path in folder.glob("*.md"):
        kind = _kind_from_name(path.name)
        if kind is None:
            continue
        try:
            body = path.read_text(encoding="utf-8")
        except OSError:
            continue
        items.append(_info_from_text(path, kind, body))
    items.sort(key=lambda item: item.path.stat().st_mtime if item.path.exists() else 0, reverse=True)
    return items


def load_record(path: Path) -> RecordInfo | None:
    if not path.is_file():
        return None
    kind = _kind_from_name(path.name) or "meeting"
    try:
        body = path.read_text(encoding="utf-8")
    except OSError:
        return None
    return _info_from_text(path, kind, body)


def _kind_from_name(name: str) -> str | None:
    lower = name.lower()
    if lower.startswith("playback "):
        return "playback"
    if lower.startswith("meeting "):
        return "meeting"
    return None


def _info_from_text(path: Path, kind: str, body: str) -> RecordInfo:
    started = _meta_value(body, "Started") or _stamp_from_name(path.name)
    preview = _preview_lines(body)
    title = path.stem
    return RecordInfo(
        path=path,
        kind=kind,
        title=title,
        started=started,
        preview=preview,
        body=body,
    )


def _meta_value(body: str, label: str) -> str:
    prefix = f"- {label}:"
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith(prefix):
            return stripped[len(prefix) :].strip()
    return ""


def _preview_lines(body: str) -> str:
    phrases: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped.startswith("- **"):
            continue
        marker = "** "
        index = stripped.find(marker)
        if index < 0:
            continue
        phrases.append(stripped[index + len(marker) :].strip())
        if len(phrases) >= 2:
            break
    if phrases:
        return " ".join(phrases)
    for line in body.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith("- "):
            return stripped
    return ""


def _stamp_from_name(name: str) -> str:
    stem = Path(name).stem
    parts = stem.split(" ", 1)
    if len(parts) != 2:
        return ""
    token = parts[1].strip()
    try:
        when = datetime.strptime(token[:16], "%Y-%m-%d %H%M")
    except ValueError:
        return token
    return when.strftime("%A, %d %B %Y, %H:%M")
