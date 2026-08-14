# pylint: disable=protected-access
from PyQt6.QtWidgets import QFrame, QLabel, QPushButton

from personalclipboard.ui.history_dialog import HistoryDialog
from personalclipboard.ui.i18n import t


def test_history_dialog_sections_newest_first_and_copy(qapp) -> None:
    assert qapp is not None
    dialog = HistoryDialog(
        [
            ("2026-08-14 12:00:00", "Older clip."),
            ("2026-08-14 12:01:00", "Newest clip."),
        ],
        "en",
    )
    copied: list[str] = []
    dialog.copy_requested.connect(copied.append)
    bodies = [
        label.text()
        for label in dialog.findChildren(QLabel)
        if label.objectName() == "historyBody"
    ]
    assert bodies == ["Newest clip.", "Older clip."]
    copies: list[QPushButton] = []
    for frame in dialog.findChildren(QFrame):
        if frame.objectName() != "historySection":
            continue
        button = frame.findChild(QPushButton)
        if isinstance(button, QPushButton):
            copies.append(button)
    assert copies
    copies[0].click()
    assert copied == ["Newest clip."]
    dialog.close()


def test_history_dialog_empty_state(qapp) -> None:
    assert qapp is not None
    dialog = HistoryDialog([], "fr")
    empty = dialog.findChild(QLabel, "historyEmpty")
    assert empty is not None
    assert empty.text() == t("fr", "history_empty")
    bodies = [
        label
        for label in dialog.findChildren(QLabel)
        if label.objectName() == "historyBody"
    ]
    assert not bodies
    dialog.close()
