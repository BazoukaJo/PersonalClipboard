"""WASAPI loopback of the Windows render mix (headphones/speakers). Meeting only."""

from __future__ import annotations

import ctypes
import sys
import threading
import time
from ctypes import POINTER, byref, c_uint32, c_uint64, c_void_p, wintypes
from typing import Protocol

import numpy as np

CLSCTX_ALL = 23
COINIT_MULTITHREADED = 0
E_RENDER = 0
E_CONSOLE = 0
E_COMMUNICATIONS = 2
DEVICE_STATE_ACTIVE = 1
DEVICE_STATE_DISABLED = 2
DEVICE_STATE_NOTPRESENT = 4
DEVICE_STATE_UNPLUGGED = 8
DEVICE_STATEMASK_ALL = 0xF
AUDCLNT_SHAREMODE_SHARED = 0
AUDCLNT_STREAMFLAGS_LOOPBACK = 0x00020000
AUDCLNT_STREAMFLAGS_AUTOCONVERTPCM = 0x80000000
AUDCLNT_STREAMFLAGS_SRC_DEFAULT_QUALITY = 0x08000000
AUDCLNT_BUFFERFLAGS_SILENT = 0x2
STGM_READ = 0
VT_LPWSTR = 31
RPC_E_CHANGED_MODE = 0x80010106


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]

    @classmethod
    def from_text(cls, text: str) -> GUID:
        import uuid

        value = uuid.UUID(text)
        return cls(
            value.time_low,
            value.time_mid,
            value.time_hi_version,
            (ctypes.c_ubyte * 8).from_buffer_copy(value.bytes[8:]),
        )


class WAVEFORMATEX(ctypes.Structure):
    _fields_ = [
        ("wFormatTag", wintypes.WORD),
        ("nChannels", wintypes.WORD),
        ("nSamplesPerSec", wintypes.DWORD),
        ("nAvgBytesPerSec", wintypes.DWORD),
        ("nBlockAlign", wintypes.WORD),
        ("wBitsPerSample", wintypes.WORD),
        ("cbSize", wintypes.WORD),
    ]


class PROPERTYKEY(ctypes.Structure):
    _fields_ = [("fmtid", GUID), ("pid", wintypes.DWORD)]


class _PropUnion(ctypes.Union):
    _fields_ = [("pwszVal", wintypes.LPWSTR), ("ullVal", c_uint64)]


class PROPVARIANT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [
        ("vt", wintypes.USHORT),
        ("wReserved1", wintypes.USHORT),
        ("wReserved2", wintypes.USHORT),
        ("wReserved3", wintypes.USHORT),
        ("u", _PropUnion),
    ]


_CLSID_ENUM = GUID.from_text("BCDE0395-E52F-467C-8E3D-C4579291692E")
_IID_ENUM = GUID.from_text("A95664D2-9614-4F35-A746-DE8DB63617E6")
_IID_CLIENT = GUID.from_text("1CB9AD4C-DBFA-4c32-B178-C2F568A703B2")
_IID_CAPTURE = GUID.from_text("C8ADBD64-E71E-48a0-A4DE-185C395CD317")
_IID_PROPS = GUID.from_text("886d8eeb-8cf2-4446-8d02-cdba1dbdcf99")
_PKEY_NAME = PROPERTYKEY(GUID.from_text("a45c254e-df1c-4efd-8020-67d146a850e0"), 14)


def _ole32():
    ole = ctypes.oledll.ole32
    ole.CoInitializeEx.argtypes = [c_void_p, wintypes.DWORD]
    ole.CoCreateInstance.argtypes = [
        c_void_p,
        c_void_p,
        wintypes.DWORD,
        c_void_p,
        POINTER(c_void_p),
    ]
    ole.CoTaskMemFree.argtypes = [c_void_p]
    ole.PropVariantClear.argtypes = [POINTER(PROPVARIANT)]
    return ole


def _vtbl(obj: c_void_p):
    addr = ctypes.cast(obj, POINTER(c_void_p)).contents.value
    if not addr:
        raise OSError("Invalid COM object.")
    return ctypes.cast(addr, POINTER(c_void_p))


def _fn(obj: c_void_p, index: int, restype, *argtypes):
    proto = ctypes.WINFUNCTYPE(restype, c_void_p, *argtypes)
    return proto(_vtbl(obj)[index])


def _release(obj: c_void_p | None) -> None:
    if not obj:
        return
    _fn(obj, 2, wintypes.ULONG)(obj)


def _hr(value: int) -> int:
    return int(value) & 0xFFFFFFFF


class PcmSink(Protocol):
    def write(self, pcm: bytes) -> None: ...
    def clear(self) -> None: ...


class LoopbackCapture:
    """Copies a render mix into a ring. Start only while Meeting/Playback Record is on."""

    def __init__(self, ring: PcmSink, sample_rate: int, device_id: str = "") -> None:
        self.ring = ring
        self.sample_rate = sample_rate
        self.device_id = device_id.strip()
        self.device_name = ""
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._error = ""
        self._thread: threading.Thread | None = None

    @property
    def active(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if sys.platform != "win32":
            raise OSError("Speaker capture needs Windows WASAPI.")
        if self.active:
            return
        self._stop.clear()
        self._ready.clear()
        self._error = ""
        self.device_name = ""
        self._thread = threading.Thread(target=self._run, name="wasapi-loopback", daemon=True)
        self._thread.start()
        if not self._ready.wait(2.5):
            self.stop()
            raise OSError("Speaker capture timed out.")
        if self._error:
            raise OSError(self._error)

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        self._thread = None
        if thread is not None:
            thread.join(timeout=1.5)
        self.ring.clear()

    def _run(self) -> None:
        ole = _ole32()
        init_hr = _hr(ole.CoInitializeEx(None, COINIT_MULTITHREADED))
        if init_hr not in (0, 1, RPC_E_CHANGED_MODE):
            self._error = f"COM init failed ({hex(init_hr)})"
            self._ready.set()
            return
        owned_com = init_hr == 0
        enumerator = c_void_p()
        device = c_void_p()
        client = c_void_p()
        capture = c_void_p()
        started = False
        try:
            hr = ole.CoCreateInstance(
                byref(_CLSID_ENUM), None, CLSCTX_ALL, byref(_IID_ENUM), byref(enumerator)
            )
            if hr != 0 or not enumerator:
                raise OSError("Could not open the audio enumerator.")
            device = _open_render(enumerator, self.device_id)
            self.device_name = _device_name(device) or "speakers"
            client = _activate_client(device)
            _initialize_loopback(client, self.sample_rate)
            capture = _capture_client(client)
            start = _fn(client, 10, ctypes.HRESULT)
            if start(client) != 0:
                raise OSError("Could not start speaker capture.")
            started = True
            self._ready.set()
            _pump(capture, self.ring, self._stop)
        except Exception as exc:
            if not self._ready.is_set():
                self._error = str(exc)
                self._ready.set()
        finally:
            if started and client:
                try:
                    _fn(client, 11, ctypes.HRESULT)(client)
                except Exception:
                    pass
            _release(capture)
            _release(client)
            _release(device)
            _release(enumerator)
            try:
                if owned_com:
                    ole.CoUninitialize()
            except Exception:
                pass


def render_device_roles() -> tuple[int, int]:
    """YouTube and other apps play on eConsole; VoIP is eCommunications."""
    return (E_CONSOLE, E_COMMUNICATIONS)


def list_wasapi_endpoints(flow: int, state_mask: int = DEVICE_STATEMASK_ALL) -> list:
    """Capture (1) or render (0) endpoints. Includes unplugged/disabled hardware."""
    from personalclipboard.audio.devices import AudioEndpoint

    if sys.platform != "win32":
        return []
    ole = _ole32()
    init_hr = _hr(ole.CoInitializeEx(None, COINIT_MULTITHREADED))
    if init_hr not in (0, 1, RPC_E_CHANGED_MODE):
        return []
    owned_com = init_hr == 0
    enumerator = c_void_p()
    collection = c_void_p()
    found: list[AudioEndpoint] = []
    try:
        hr = ole.CoCreateInstance(
            byref(_CLSID_ENUM), None, CLSCTX_ALL, byref(_IID_ENUM), byref(enumerator)
        )
        if hr != 0 or not enumerator:
            return []
        enum_ep = _fn(
            enumerator, 3, ctypes.HRESULT, wintypes.DWORD, wintypes.DWORD, POINTER(c_void_p)
        )
        if enum_ep(enumerator, int(flow), int(state_mask), byref(collection)) != 0 or not collection:
            return []
        count = c_uint32(0)
        get_count = _fn(collection, 3, ctypes.HRESULT, POINTER(c_uint32))
        if get_count(collection, byref(count)) != 0:
            return []
        item = _fn(collection, 4, ctypes.HRESULT, c_uint32, POINTER(c_void_p))
        for index in range(int(count.value)):
            device = c_void_p()
            if item(collection, index, byref(device)) != 0 or not device:
                continue
            try:
                state = _device_state(device)
                if state == DEVICE_STATE_NOTPRESENT:
                    continue
                ident = _device_id(device)
                name = _device_name(device) or ident
                if ident:
                    found.append(
                        AudioEndpoint(ident, name, active=state == DEVICE_STATE_ACTIVE)
                    )
            finally:
                _release(device)
        found.sort(key=lambda item: (not item.active, item.name.casefold(), item.device_id))
        return found
    except Exception:
        return []
    finally:
        _release(collection)
        _release(enumerator)
        try:
            if owned_com:
                ole.CoUninitialize()
        except Exception:
            pass


def default_wasapi_name(flow: int) -> str:
    """Friendly name of the Windows default capture (1) or render (0) endpoint."""
    if sys.platform != "win32":
        return ""
    ole = _ole32()
    init_hr = _hr(ole.CoInitializeEx(None, COINIT_MULTITHREADED))
    if init_hr not in (0, 1, RPC_E_CHANGED_MODE):
        return ""
    owned_com = init_hr == 0
    enumerator = c_void_p()
    device = c_void_p()
    try:
        hr = ole.CoCreateInstance(
            byref(_CLSID_ENUM), None, CLSCTX_ALL, byref(_IID_ENUM), byref(enumerator)
        )
        if hr != 0 or not enumerator:
            return ""
        get_default = _fn(
            enumerator, 4, ctypes.HRESULT, wintypes.DWORD, wintypes.DWORD, POINTER(c_void_p)
        )
        roles = render_device_roles() if int(flow) == E_RENDER else (E_CONSOLE, E_COMMUNICATIONS)
        for role in roles:
            device = c_void_p()
            if get_default(enumerator, int(flow), role, byref(device)) == 0 and device:
                return _device_name(device) or ""
        return ""
    except Exception:
        return ""
    finally:
        _release(device)
        _release(enumerator)
        try:
            if owned_com:
                ole.CoUninitialize()
        except Exception:
            pass


def _open_render(enumerator: c_void_p, device_id: str) -> c_void_p:
    if device_id:
        device = _get_device(enumerator, device_id)
        if device:
            return device
    return _default_render(enumerator)


def _get_device(enumerator: c_void_p, device_id: str) -> c_void_p | None:
    get_device = _fn(enumerator, 5, ctypes.HRESULT, wintypes.LPCWSTR, POINTER(c_void_p))
    device = c_void_p()
    if get_device(enumerator, device_id, byref(device)) == 0 and device:
        return device
    return None


def _device_state(device: c_void_p) -> int:
    get_state = _fn(device, 6, ctypes.HRESULT, POINTER(c_uint32))
    state = c_uint32(0)
    if get_state(device, byref(state)) != 0:
        return DEVICE_STATE_ACTIVE
    return int(state.value)


def _device_id(device: c_void_p) -> str:
    get_id = _fn(device, 5, ctypes.HRESULT, POINTER(c_void_p))
    ptr = c_void_p()
    if get_id(device, byref(ptr)) != 0 or not ptr.value:
        return ""
    try:
        return ctypes.wstring_at(ptr.value)
    finally:
        try:
            _ole32().CoTaskMemFree(ptr)
        except Exception:
            pass


def _default_render(enumerator: c_void_p) -> c_void_p:
    get_default = _fn(
        enumerator, 4, ctypes.HRESULT, wintypes.DWORD, wintypes.DWORD, POINTER(c_void_p)
    )
    for role in render_device_roles():
        device = c_void_p()
        if get_default(enumerator, E_RENDER, role, byref(device)) == 0 and device:
            return device
    raise OSError("No playback device for speaker capture.")


def _activate_client(device: c_void_p) -> c_void_p:
    activate = _fn(
        device, 3, ctypes.HRESULT, POINTER(GUID), wintypes.DWORD, c_void_p, POINTER(c_void_p)
    )
    client = c_void_p()
    hr = activate(device, byref(_IID_CLIENT), CLSCTX_ALL, None, byref(client))
    if hr != 0 or not client:
        raise OSError("Could not activate speaker capture.")
    return client


def _initialize_loopback(client: c_void_p, sample_rate: int) -> None:
    initialize = _fn(
        client,
        3,
        ctypes.HRESULT,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_int64,
        ctypes.c_int64,
        POINTER(WAVEFORMATEX),
        c_void_p,
    )
    fmt = WAVEFORMATEX(1, 1, sample_rate, sample_rate * 2, 2, 16, 0)
    flags = (
        AUDCLNT_STREAMFLAGS_LOOPBACK
        | AUDCLNT_STREAMFLAGS_AUTOCONVERTPCM
        | AUDCLNT_STREAMFLAGS_SRC_DEFAULT_QUALITY
    )
    hr = initialize(client, AUDCLNT_SHAREMODE_SHARED, flags, 10_000_000, 0, byref(fmt), None)
    if hr == 0:
        return
    raise OSError(f"Speaker capture format failed ({hex(_hr(hr))}).")


def _capture_client(client: c_void_p) -> c_void_p:
    get_service = _fn(client, 14, ctypes.HRESULT, POINTER(GUID), POINTER(c_void_p))
    capture = c_void_p()
    hr = get_service(client, byref(_IID_CAPTURE), byref(capture))
    if hr != 0 or not capture:
        raise OSError("Could not open the speaker capture client.")
    return capture


def _device_name(device: c_void_p) -> str:
    try:
        open_store = _fn(device, 4, ctypes.HRESULT, wintypes.DWORD, POINTER(c_void_p))
        store = c_void_p()
        if open_store(device, STGM_READ, byref(store)) != 0 or not store:
            return ""
        try:
            get_value = _fn(store, 5, ctypes.HRESULT, POINTER(PROPERTYKEY), POINTER(PROPVARIANT))
            value = PROPVARIANT()
            if get_value(store, byref(_PKEY_NAME), byref(value)) != 0:
                return ""
            if value.vt == VT_LPWSTR and value.pwszVal:
                name = str(value.pwszVal)
            else:
                name = ""
            try:
                _ole32().PropVariantClear(byref(value))
            except Exception:
                pass
            return name
        finally:
            _release(store)
    except Exception:
        return ""


def _pump(capture: c_void_p, ring: PcmSink, stop: threading.Event) -> None:
    get_packet = _fn(capture, 5, ctypes.HRESULT, POINTER(c_uint32))
    get_buffer = _fn(
        capture,
        3,
        ctypes.HRESULT,
        POINTER(POINTER(ctypes.c_byte)),
        POINTER(c_uint32),
        POINTER(wintypes.DWORD),
        POINTER(c_uint64),
        POINTER(c_uint64),
    )
    release = _fn(capture, 4, ctypes.HRESULT, c_uint32)
    while not stop.is_set():
        packet = c_uint32(0)
        if get_packet(capture, byref(packet)) != 0 or packet.value == 0:
            time.sleep(0.01)
            continue
        data = POINTER(ctypes.c_byte)()
        frames = c_uint32(0)
        flags = wintypes.DWORD(0)
        if get_buffer(capture, byref(data), byref(frames), byref(flags), None, None) != 0:
            time.sleep(0.01)
            continue
        count = int(frames.value)
        if count > 0:
            if flags.value & AUDCLNT_BUFFERFLAGS_SILENT:
                ring.write(np.zeros(count, dtype=np.int16).tobytes())
            elif data:
                ring.write(ctypes.string_at(data, count * 2))
        release(capture, frames.value)
