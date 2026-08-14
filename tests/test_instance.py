import os
import time
from pathlib import Path

from personalclipboard.instance import (
    _REPLACE,
    clear_pid,
    install_single_instance,
    pid_is_running,
    read_pid,
    release_owned,
    terminate_pid,
    write_pid,
)


def test_pid_file_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "instance.pid"
    write_pid(path, 4242)
    assert read_pid(path) == 4242
    clear_pid(path)
    assert read_pid(path) is None


def test_pid_file_rejects_garbage(tmp_path: Path) -> None:
    path = tmp_path / "instance.pid"
    path.write_text("not-a-pid", encoding="utf-8")
    assert read_pid(path) is None


def test_this_process_counts_as_running() -> None:
    assert pid_is_running(os.getpid())
    assert not pid_is_running(0)
    assert not pid_is_running(-1)


def test_terminate_never_kills_self() -> None:
    assert terminate_pid(os.getpid()) is False
    assert terminate_pid(0) is False


def test_empty_socket_does_not_quit(qapp, monkeypatch, tmp_path) -> None:
    import personalclipboard.instance as inst
    from PyQt6.QtNetwork import QLocalServer, QLocalSocket

    monkeypatch.setattr(inst, "SERVER_NAME", "PCTestEmptySocket")
    monkeypatch.setattr(inst, "runtime_dir", lambda: tmp_path)
    QLocalServer.removeServer(inst.SERVER_NAME)
    quits: list[str] = []
    monkeypatch.setattr(qapp, "quit", lambda: quits.append("quit"))
    install_single_instance(qapp, wait_s=1)
    sock = QLocalSocket()
    sock.connectToServer(inst.SERVER_NAME)
    assert sock.waitForConnected(800)
    qapp.processEvents()
    time.sleep(0.15)
    qapp.processEvents()
    assert not quits
    sock.abort()
    release_owned()
    QLocalServer.removeServer(inst.SERVER_NAME)


def test_replace_payload_requests_quit(qapp, monkeypatch, tmp_path) -> None:
    import personalclipboard.instance as inst
    from PyQt6.QtNetwork import QLocalServer, QLocalSocket

    monkeypatch.setattr(inst, "SERVER_NAME", "PCTestReplaceSocket")
    monkeypatch.setattr(inst, "runtime_dir", lambda: tmp_path)
    QLocalServer.removeServer(inst.SERVER_NAME)
    quits: list[str] = []
    monkeypatch.setattr(qapp, "quit", lambda: quits.append("quit"))
    install_single_instance(qapp, wait_s=1)
    sock = QLocalSocket()
    sock.connectToServer(inst.SERVER_NAME)
    assert sock.waitForConnected(800)
    sock.write(_REPLACE)
    sock.waitForBytesWritten(400)
    qapp.processEvents()
    time.sleep(0.15)
    qapp.processEvents()
    assert quits == ["quit"]
    sock.abort()
    release_owned()
    QLocalServer.removeServer(inst.SERVER_NAME)
