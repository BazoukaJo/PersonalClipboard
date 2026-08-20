"""WASAPI capture and render endpoints for Settings. IDs persist across launches."""

from __future__ import annotations

import sys
from dataclasses import dataclass

E_RENDER = 0
E_CAPTURE = 1


@dataclass(frozen=True)
class AudioEndpoint:
    device_id: str
    name: str
    active: bool = True


def list_capture_endpoints() -> list[AudioEndpoint]:
    return _list_endpoints(E_CAPTURE)


def list_render_endpoints() -> list[AudioEndpoint]:
    return _list_endpoints(E_RENDER)


def default_capture_name() -> str:
    return _default_name(E_CAPTURE)


def default_render_name() -> str:
    return _default_name(E_RENDER)


def labeled_endpoints(items: list[AudioEndpoint]) -> list[tuple[str, str, str]]:
    """(device_id, combo label, canonical name). Duplicate names get [1], [2], …"""
    counts: dict[str, int] = {}
    for item in items:
        counts[item.name] = counts.get(item.name, 0) + 1
    seen: dict[str, int] = {}
    labeled: list[tuple[str, str, str]] = []
    for item in items:
        seen[item.name] = seen.get(item.name, 0) + 1
        label = item.name
        if counts[item.name] > 1:
            label = f"{item.name} [{seen[item.name]}]"
        labeled.append((item.device_id, label, item.name))
    return labeled


def names_match(left: str, right: str) -> bool:
    a = left.strip().lower()
    b = right.strip().lower()
    if not a or not b:
        return False
    return a == b or a in b or b in a


def _list_endpoints(flow: int) -> list[AudioEndpoint]:
    if sys.platform != "win32":
        return []
    try:
        from personalclipboard.audio.loopback import list_wasapi_endpoints

        return list_wasapi_endpoints(flow)
    except Exception:
        return []


def _default_name(flow: int) -> str:
    if sys.platform != "win32":
        return ""
    try:
        from personalclipboard.audio.loopback import default_wasapi_name

        return default_wasapi_name(flow)
    except Exception:
        return ""
