"""Modal clipboard history: one section per complete clip, Copy on the top right."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from personalclipboard.ui.i18n import t
from personalclipboard.ui.theme import control_chrome, pointing


class HistoryDialog(QDialog):
    copy_requested = pyqtSignal(str)

    def __init__(
        self,
        entries: list[tuple[str, str]],
        lang: str = "en",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._lang = lang if lang in ("en", "fr", "es", "de") else "en"
        self.setWindowTitle(t(self._lang, "history"))
        self.setModal(True)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setMinimumSize(440, 360)
        self.resize(560, 580)
        self._apply_chrome()
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)
        root.addLayout(self._make_header())
        root.addWidget(self._make_body(entries), 1)

    def _make_header(self) -> QHBoxLayout:
        title = QLabel(t(self._lang, "history"))
        title.setObjectName("brand")
        close_btn = QPushButton(t(self._lang, "close"))
        close_btn.setObjectName("quiet")
        pointing(close_btn)
        close_btn.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(title)
        row.addStretch(1)
        row.addWidget(close_btn)
        return row

    def _make_body(self, entries: list[tuple[str, str]]) -> QWidget:
        scroll = QScrollArea()
        scroll.setObjectName("historyScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(10)
        if not entries:
            empty = QLabel(t(self._lang, "history_empty"))
            empty.setObjectName("historyEmpty")
            empty.setWordWrap(True)
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(empty)
        else:
            for stamp, text in reversed(entries):
                layout.addWidget(_HistorySection(stamp, text, self._lang, self))
        layout.addStretch(1)
        scroll.setWidget(inner)
        return scroll

    def _apply_chrome(self) -> None:
        self.setStyleSheet(
            "QDialog { background: #1a1a1c; color: #f0f0f2; }"
            + control_chrome()
        )

    def copy_section(self, button: QPushButton, text: str) -> None:
        self.copy_requested.emit(text)
        button.setText(t(self._lang, "flash_copied"))
        QTimer.singleShot(1200, lambda btn=button: self._restore_copy(btn))

    def _restore_copy(self, button: QPushButton) -> None:
        try:
            button.setText(t(self._lang, "copy"))
        except RuntimeError:
            pass


class _HistorySection(QFrame):
    def __init__(self, stamp: str, text: str, lang: str, dialog: HistoryDialog) -> None:
        super().__init__(dialog)
        self.setObjectName("historySection")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        stamp_label = QLabel(stamp)
        stamp_label.setObjectName("historyStamp")
        copy_btn = QPushButton(t(lang, "copy"))
        copy_btn.setObjectName("primary")
        pointing(copy_btn)
        copy_btn.setToolTip(t(lang, "history_copy_tip"))
        copy_btn.clicked.connect(self._on_copy)
        self._copy_btn = copy_btn
        self._text = text
        self._dialog = dialog
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.addWidget(stamp_label, 1)
        header.addWidget(copy_btn, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        body = QLabel(text)
        body.setObjectName("historyBody")
        body.setTextFormat(Qt.TextFormat.PlainText)
        body.setWordWrap(True)
        body.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(10)
        layout.addLayout(header)
        layout.addWidget(body)

    def _on_copy(self) -> None:
        self._dialog.copy_section(self._copy_btn, self._text)
