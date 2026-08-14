from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QKeyEvent

from personalclipboard.ui.predict_edit import PredictLineEdit


def test_tab_accepts_ghost_suffix(qapp, monkeypatch) -> None:
    assert qapp is not None
    edit = PredictLineEdit()
    monkeypatch.setattr(edit, "hasFocus", lambda: True)
    edit.set_blocked(True)
    edit.setText("The meeting is")
    edit.set_blocked(False)
    edit.set_ghost("The meeting is", " scheduled")
    assert edit.ghost() == " scheduled"
    tab = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Tab, Qt.KeyboardModifier.NoModifier)
    assert edit.event(tab) is True
    qapp.processEvents()
    assert edit.text() == "The meeting is scheduled"
    assert edit.ghost() == ""
    edit.deleteLater()


def test_no_ghost_when_unfocused(qapp) -> None:
    assert qapp is not None
    edit = PredictLineEdit()
    edit.setText("The meeting is")
    edit.clearFocus()
    qapp.processEvents()
    edit.set_ghost("The meeting is", " tomorrow")
    assert edit.ghost() == ""
    edit.deleteLater()
