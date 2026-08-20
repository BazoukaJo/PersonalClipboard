"""WASAPI capture and render endpoints for Settings. IDs persist across launches."""

from __future__ import annotations

import sys
from dataclasses import dataclass

E_RENDER = 0
E_CAPTURE = 1
DEVICE_STATE_ACTIVE = 1


@dataclass(frozen=True)
class AudioEndpoint:
    device_id: str
    name: str


def list_capture_endpoints() -> list[AudioEndpoint]:
    return _list_endpoints(E_CAPTURE)


def list_render_endpoints() -> list[AudioEndpoint]:
    return _list_endpoints(E_RENDER)


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
