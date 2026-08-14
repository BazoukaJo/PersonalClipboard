from personalclipboard.windows import input as win_input
from personalclipboard.windows.input import WindowInput


def test_poll_ignores_this_process(monkeypatch) -> None:
    tracker = WindowInput()
    monkeypatch.setattr(win_input.user32, "GetForegroundWindow", lambda: 11)
    monkeypatch.setattr(win_input, "_pid_of", lambda _hwnd: tracker._pid)
    tracker.poll()
    assert tracker._last_foreign is None
    assert tracker._last_focus is None


def test_poll_records_foreign_control(monkeypatch) -> None:
    tracker = WindowInput()
    monkeypatch.setattr(win_input.user32, "GetForegroundWindow", lambda: 42)
    monkeypatch.setattr(win_input, "_pid_of", lambda _hwnd: tracker._pid + 7)
    monkeypatch.setattr(win_input, "_focused_control", lambda _hwnd: 99)
    tracker.poll()
    assert tracker._last_foreign == 42
    assert tracker._last_focus == 99


def test_focus_last_foreign_requires_a_window(monkeypatch) -> None:
    tracker = WindowInput()
    monkeypatch.setattr(win_input.user32, "IsWindow", lambda _hwnd: False)
    assert tracker.focus_last_foreign() is False
    tracker._last_foreign = 42
    assert tracker.focus_last_foreign() is False
