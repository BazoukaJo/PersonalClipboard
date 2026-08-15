"""Modal library of desktop meeting and playback transcripts."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QUrl, Qt, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QFont, QMouseEvent, QTextCursor
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from personalclipboard.notes.library import RecordInfo
from personalclipboard.ui.i18n import LANG_CODES, t
from personalclipboard.ui.theme import control_chrome, pointing


class RecordsDialog(QDialog):
    """List of saved transcripts. Click a row to read the full note."""

    def __init__(
        self,
        records: list[RecordInfo],
        lang: str = "en",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._lang = lang if lang in LANG_CODES else "en"
        self._records = records
        self.setWindowTitle(t(self._lang, "records"))
        self.setModal(True)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setMinimumSize(480, 400)
        self.resize(600, 620)
        self.setStyleSheet("QDialog { background: #1a1a1c; color: #f0f0f2; }" + control_chrome())
        self._stack = QStackedWidget(self)
        self._list_page = self._make_list()
        self._detail_page = _RecordDetail(self._lang, self)
        self._stack.addWidget(self._list_page)
        self._stack.addWidget(self._detail_page)
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)
        root.addWidget(self._stack, 1)
        self._stack.setCurrentIndex(0)

    def _make_list(self) -> QWidget:
        page = QWidget(self)
        title = QLabel(t(self._lang, "records"))
        title.setObjectName("brand")
        title.setToolTip(t(self._lang, "records_tip"))
        close_btn = QPushButton(t(self._lang, "close"))
        close_btn.setObjectName("ghost")
        close_btn.setToolTip(t(self._lang, "close_tip"))
        pointing(close_btn)
        close_btn.clicked.connect(self.accept)
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(close_btn)
        scroll = QScrollArea()
        scroll.setObjectName("historyScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(10)
        if not self._records:
            empty = QLabel(t(self._lang, "records_empty"))
            empty.setObjectName("historyEmpty")
            empty.setWordWrap(True)
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setToolTip(t(self._lang, "records_tip"))
            layout.addWidget(empty)
        else:
            for item in self._records:
                card = _RecordCard(item, self._lang, self)
                card.clicked.connect(self._open_record)
                layout.addWidget(card)
        layout.addStretch(1)
        scroll.setWidget(inner)
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(10)
        page_layout.addLayout(header)
        page_layout.addWidget(scroll, 1)
        return page

    def _open_record(self, info: RecordInfo) -> None:
        self._detail_page.show_record(info)
        self._stack.setCurrentWidget(self._detail_page)

    def show_list(self) -> None:
        self._stack.setCurrentIndex(0)


class _RecordCard(QFrame):
    clicked = pyqtSignal(object)

    def __init__(self, info: RecordInfo, lang: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._info = info
        self.setObjectName("historySection")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self.setToolTip(t(lang, "records_open_tip"))
        kind_key = "kind_playback" if info.kind == "playback" else "kind_meeting"
        badge = QLabel(t(lang, kind_key))
        badge.setObjectName("kindBadge")
        badge.setProperty("kind", info.kind)
        badge.setToolTip(t(lang, "playback_tip" if info.kind == "playback" else "meet_tip"))
        stamp = QLabel(info.started or info.title)
        stamp.setObjectName("historyStamp")
        stamp.setToolTip(info.filename)
        title = QLabel(info.title)
        title.setObjectName("historyBody")
        title.setWordWrap(True)
        preview = QLabel(info.preview or t(lang, "records_empty_preview"))
        preview.setObjectName("historyStamp")
        preview.setWordWrap(True)
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        header.addWidget(badge, 0)
        header.addWidget(stamp, 1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(8)
        layout.addLayout(header)
        layout.addWidget(title)
        layout.addWidget(preview)

    def mouseReleaseEvent(self, a0: QMouseEvent | None) -> None:
        if a0 is not None and a0.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._info)
            a0.accept()
            return
        super().mouseReleaseEvent(a0)


class _RecordDetail(QWidget):
    def __init__(self, lang: str, dialog: RecordsDialog) -> None:
        super().__init__(dialog)
        self._lang = lang
        self._dialog = dialog
        self._path: Path | None = None
        back = QPushButton(t(lang, "back"))
        back.setObjectName("ghost")
        back.setToolTip(t(lang, "back_tip"))
        pointing(back)
        back.clicked.connect(dialog.show_list)
        self._title = QLabel("")
        self._title.setObjectName("brand")
        self._title.setWordWrap(True)
        self._open_btn = QPushButton(t(lang, "open_file"))
        self._open_btn.setObjectName("ghost")
        self._open_btn.setToolTip(t(lang, "open_file_tip"))
        pointing(self._open_btn)
        self._open_btn.clicked.connect(self._open_file)
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        header.addWidget(back, 0)
        header.addWidget(self._title, 1)
        header.addWidget(self._open_btn, 0)
        self._kind = QLabel("")
        self._kind.setObjectName("kindBadge")
        self._kind.setToolTip(t(lang, "records_tip"))
        self._body = QPlainTextEdit()
        self._body.setReadOnly(True)
        self._body.setObjectName("recordBody")
        font = QFont("Segoe UI", 11)
        self._body.setFont(font)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addLayout(header)
        layout.addWidget(self._kind, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self._body, 1)

    def show_record(self, info: RecordInfo) -> None:
        self._path = info.path
        self._title.setText(info.title)
        self._title.setToolTip(str(info.path))
        kind_key = "kind_playback" if info.kind == "playback" else "kind_meeting"
        self._kind.setText(t(self._lang, kind_key))
        self._kind.setProperty("kind", info.kind)
        self._kind.setToolTip(t(self._lang, "playback_tip" if info.kind == "playback" else "meet_tip"))
        style = self._kind.style()
        if style is not None:
            style.unpolish(self._kind)
            style.polish(self._kind)
        self._body.setPlainText(info.body)
        self._body.moveCursor(QTextCursor.MoveOperation.Start)

    def _open_file(self) -> None:
        if self._path is None or not self._path.is_file():
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._path)))
