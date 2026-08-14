"""Type field with grey ghost completion. Tab accepts. Only while focused."""

from __future__ import annotations

from PyQt6.QtCore import QEvent, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QKeyEvent, QPaintEvent, QPainter
from PyQt6.QtWidgets import QLineEdit, QStyle, QStyleOptionFrame

from personalclipboard.llm.complete import should_predict


class PredictLineEdit(QLineEdit):
    prediction_requested = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._ghost = ""
        self._enabled = True
        self._blocked = False
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(380)
        self._debounce.timeout.connect(self._emit_request)
        self.textChanged.connect(self._on_text)

    def set_predict_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        if not enabled:
            self.clear_ghost()
            self._debounce.stop()

    def set_blocked(self, blocked: bool) -> None:
        self._blocked = blocked
        if blocked:
            self.clear_ghost()
            self._debounce.stop()

    def set_debounce_ms(self, milliseconds: int) -> None:
        self._debounce.setInterval(max(150, min(2000, milliseconds)))

    def ghost(self) -> str:
        return self._ghost

    def set_ghost(self, prefix: str, suffix: str) -> None:
        if not self.hasFocus() or not self._enabled or self._blocked:
            return
        if self.text() != prefix or not suffix:
            return
        self._ghost = suffix
        self.update()

    def clear_ghost(self) -> None:
        if not self._ghost:
            return
        self._ghost = ""
        self.update()

    def accept_ghost(self) -> bool:
        suffix = self._ghost
        if not suffix:
            return False
        self._blocked = True
        self.clear_ghost()
        self.insert(suffix)
        self._blocked = False
        return True

    def event(self, a0: QEvent | None) -> bool:  # type: ignore[override]
        if a0 is not None and a0.type() == QEvent.Type.KeyPress:
            if isinstance(a0, QKeyEvent) and self._handle_predict_key(a0):
                return True
        return super().event(a0)

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0 is not None and self._handle_predict_key(a0):
            return
        super().keyPressEvent(a0)

    def _handle_predict_key(self, event: QKeyEvent) -> bool:
        tab = event.key() == Qt.Key.Key_Tab
        shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        if tab and not shift:
            self.accept_ghost()
            event.accept()
            return True
        if event.key() == Qt.Key.Key_Escape and self._ghost:
            self.clear_ghost()
            event.accept()
            return True
        return False

    def focusOutEvent(self, a0) -> None:  # type: ignore[override]
        self._debounce.stop()
        self.clear_ghost()
        super().focusOutEvent(a0)

    def paintEvent(self, a0: QPaintEvent | None) -> None:
        super().paintEvent(a0)
        if not self._ghost or not self.hasFocus() or self.cursorPosition() != len(self.text()):
            return
        option = QStyleOptionFrame()
        self.initStyleOption(option)
        style = self.style()
        if style is None:
            return
        rect = style.subElementRect(QStyle.SubElement.SE_LineEditContents, option, self)
        left = rect.x() + 2 + self.fontMetrics().horizontalAdvance(self.text())
        painter = QPainter(self)
        painter.setPen(QColor(138, 138, 142))
        shown = self._ghost
        if shown and self.text() and not self.text()[-1].isspace() and not shown.startswith(" "):
            shown = " " + shown
        painter.drawText(
            left,
            rect.y(),
            max(rect.right() - left, 0),
            rect.height(),
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            shown,
        )
        painter.end()

    def _on_text(self, _text: str) -> None:
        self.clear_ghost()
        self._debounce.stop()
        if should_predict(
            self.text(),
            focused=self.hasFocus(),
            enabled=self._enabled,
            blocked=self._blocked,
        ):
            self._debounce.start()

    def _emit_request(self) -> None:
        if should_predict(
            self.text(),
            focused=self.hasFocus(),
            enabled=self._enabled,
            blocked=self._blocked,
        ):
            self.prediction_requested.emit(self.text())
