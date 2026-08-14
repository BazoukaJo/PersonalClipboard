"""One live process. A new launch stops the previous instance and starts fresh."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import QApplication

SERVER_NAME = "PersonalClipboardInstance"
_REPLACE = b"replace\n"


class _Holder:
    server: QLocalServer | None = None


_HOLDER = _Holder()


def runtime_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_RUNTIME_DIR")
    path = Path(base) / "PersonalClipboard" if base else Path.home() / ".personalclipboard"
    path.mkdir(parents=True, exist_ok=True)
    return path


def pid_path() -> Path:
    return runtime_dir() / "instance.pid"


def read_pid(path: Path | None = None) -> int | None:
    target = path or pid_path()
    try:
        text = target.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not text.isdigit():
        return None
    return int(text)


def write_pid(path: Path | None = None, pid: int | None = None) -> None:
    target = path or pid_path()
    target.write_text(str(pid if pid is not None else os.getpid()), encoding="utf-8")


def clear_pid(path: Path | None = None) -> None:
    target = path or pid_path()
    try:
        target.unlink(missing_ok=True)
    except OSError:
        pass


def pid_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    if sys.platform == "win32":
        return _win_pid_running(pid)
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def terminate_pid(pid: int) -> bool:
    """Stop another process. Never signals this process."""
    if pid <= 0 or pid == os.getpid() or not pid_is_running(pid):
        return False
    if sys.platform == "win32":
        return _win_terminate(pid)
    try:
        import signal

        os.kill(pid, signal.SIGTERM)
        return True
    except OSError:
        return False


def install_single_instance(qt: QApplication, *, wait_s: float = 12.0) -> QLocalServer:
    """Stop a running instance, then own the local socket. Last launch wins."""
    server = _try_listen(qt)
    if server is None and not _peer_is_alive():
        QLocalServer.removeServer(SERVER_NAME)
        server = _try_listen(qt)
    if server is not None:
        _own(server, qt)
        return server
    deadline = time.monotonic() + wait_s
    while time.monotonic() < deadline:
        _ask_previous_to_quit()
        time.sleep(0.2)
        server = _try_listen(qt)
        if server is not None:
            _own(server, qt)
            return server
    leftover = read_pid()
    if leftover is not None:
        terminate_pid(leftover)
        clear_pid()
    QLocalServer.removeServer(SERVER_NAME)
    server = _try_listen(qt)
    if server is None:
        raise RuntimeError("Another PersonalClipboard instance could not be replaced")
    _own(server, qt)
    return server


def release_owned() -> None:
    if _HOLDER.server is None:
        return
    release_instance(_HOLDER.server)
    _HOLDER.server = None


def release_instance(server: QLocalServer) -> None:
    server.close()
    QLocalServer.removeServer(SERVER_NAME)
    if read_pid() == os.getpid():
        clear_pid()


def _own(server: QLocalServer, qt: QApplication) -> None:
    _HOLDER.server = server
    write_pid()

    def on_conn() -> None:
        _accept_replace(server, qt)

    server.newConnection.connect(on_conn)


def _try_listen(qt: QApplication) -> QLocalServer | None:
    server = QLocalServer(qt)
    if server.listen(SERVER_NAME):
        return server
    server.close()
    server.deleteLater()
    return None


def _peer_is_alive() -> bool:
    sock = QLocalSocket()
    sock.connectToServer(SERVER_NAME)
    alive = sock.waitForConnected(300)
    if alive:
        sock.disconnectFromServer()
        if sock.state() != QLocalSocket.LocalSocketState.UnconnectedState:
            sock.waitForDisconnected(400)
    else:
        sock.abort()
    sock.deleteLater()
    return alive


def _ask_previous_to_quit() -> None:
    sock = QLocalSocket()
    sock.connectToServer(SERVER_NAME)
    if not sock.waitForConnected(400):
        sock.abort()
        sock.deleteLater()
        return
    sock.write(_REPLACE)
    sock.waitForBytesWritten(400)
    sock.disconnectFromServer()
    if sock.state() != QLocalSocket.LocalSocketState.UnconnectedState:
        sock.waitForDisconnected(2500)
    sock.abort()
    sock.deleteLater()


def _accept_replace(server: QLocalServer, qt: QApplication) -> None:
    conn = server.nextPendingConnection()
    if conn is None:
        return
    if conn.bytesAvailable() == 0:
        conn.waitForReadyRead(400)
    raw = conn.readAll()
    payload = raw.data().replace(b"\r", b"")
    conn.close()
    conn.deleteLater()
    # Empty connects are listen probes. Only an explicit replace payload may quit.
    if _REPLACE.strip() in payload:
        qt.quit()


def _win_pid_running(pid: int) -> bool:
    import ctypes

    handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
    if not handle:
        return False
    ctypes.windll.kernel32.CloseHandle(handle)
    return True


def _win_terminate(pid: int) -> bool:
    import ctypes

    handle = ctypes.windll.kernel32.OpenProcess(0x0001, False, pid)
    if not handle:
        return False
    ok = bool(ctypes.windll.kernel32.TerminateProcess(handle, 1))
    ctypes.windll.kernel32.CloseHandle(handle)
    return ok
