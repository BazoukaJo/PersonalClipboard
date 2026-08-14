"""Frameless HUD overlay: voice, type, and collapsible meeting notes."""

from __future__ import annotations

import sys

from PyQt6.QtCore import QByteArray, QEvent, QPoint, QRect, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QResizeEvent,
    QShowEvent,
    QTextCursor,
)
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from personalclipboard.config import shell_alpha
from personalclipboard.ui.i18n import flash_key, t
from personalclipboard.ui.predict_edit import PredictLineEdit
from personalclipboard.ui.settings_panel import SettingsPanel
from personalclipboard.ui.win11_resize import (
    enable_thick_frame,
    resize_hit,
    unpack_nchittest_point,
)

_ACCENT = "#c8c8cc"
_EMPTY = "Ready to paste"
_SENTENCE_END = ".?!。？！"
_STATUS_LABEL = {
    "off": "Mic off",
    "loading": "Loading",
    "listening": "Listening",
    "uncertain": "Other voice",
    "locked": "Your voice",
    "recording": "Recording",
    "quiet": "Quiet",
    "error": "Error",
}


def _pill(fg: str, bg: str, bd: str) -> str:
    return f"color:{fg}; background:{bg}; border:1px solid {bd};"


_STATUS_STYLE = {
    "off": _pill("#8e8e90", "rgba(28,28,30,95)", "rgba(90,90,94,60)"),
    "loading": _pill("#d0d0d4", "rgba(42,42,46,105)", "rgba(120,120,124,75)"),
    "listening": _pill("#f0f0f2", "rgba(46,46,50,110)", "rgba(140,140,144,85)"),
    "uncertain": _pill("#b4b4b8", "rgba(36,36,38,100)", "rgba(100,100,104,70)"),
    "locked": _pill("#f4f4f6", "rgba(52,52,56,115)", "rgba(160,160,164,90)"),
    "recording": _pill("#f4f4f6", "rgba(58,58,62,120)", "rgba(170,170,174,95)"),
    "quiet": _pill("#b4b4b8", "rgba(28,28,30,95)", "rgba(90,90,94,60)"),
    "error": _pill("#c8c8cc", "rgba(26,26,28,105)", "rgba(100,100,104,75)"),
}


class Overlay(QWidget):
    enable_toggled = pyqtSignal(bool)
    hide_requested = pyqtSignal()
    copy_requested = pyqtSignal()
    phrase_completed = pyqtSignal(str)
    meeting_toggled = pyqtSignal(bool)
    prediction_requested = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self._drag: QPoint | None = None
        self._updating_input = False
        self._typed_prev = ""
        self._elide: dict[QLabel, tuple[str, bool]] = {}
        self._meeting_on = False
        self._predict_want = True
        self._status_key = "off"
        self._enable = QCheckBox("Mic", self)
        self._status = QLabel("Mic off", self)
        self._flash_timer = QTimer(self)
        self._flash_timer.setSingleShot(True)
        self._flash_timer.timeout.connect(self._restore_status)
        self._copy_btn = QPushButton("Copy", self)
        self._hide_btn = QPushButton("Hide", self)
        self._lang = "en"
        self._opacity = 35
        self._empty = t("en", "empty")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFont(QFont("Segoe UI", 10))
        self.setMinimumSize(400, 220)
        self._build()
        self.resize(520, max(self.sizeHint().height(), 260))

    def _build(self) -> None:
        top = self._make_top()
        audio, self._audio_live, self._audio_body, self._voice_title, self._hear_tag = (
            _result_panel("Voice", live_tag="Hearing", parent=self)
        )
        self._audio_frame = audio
        audio.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self._input = PredictLineEdit(self)
        self._input.setPlaceholderText("Type, then Enter or a period.")
        self._input.textChanged.connect(self._on_typed)
        self._input.returnPressed.connect(self._commit_typed_enter)
        self._input.prediction_requested.connect(self.prediction_requested.emit)
        typed, _, self._typed_body, self._type_title, _tag = _result_panel(
            "Type", extra=self._input, parent=self
        )
        _tag.hide()
        self._typed_frame = typed
        typed.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        pack = _meeting_panel(self)
        meeting = pack[0]
        self._meet_btn = pack[1]
        self._meet_live = pack[2]
        self._meet_notes = pack[3]
        self._meet_live_row = pack[4]
        self._meet_title = pack[5]
        self._meet_tag = pack[6]
        self._meet_frame = meeting
        meeting.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self._meet_btn.clicked.connect(self._toggle_meeting)
        self.settings = SettingsPanel(self)
        self.settings.language_changed.connect(self.apply_language)
        self.settings.opacity_changed.connect(self.set_opacity)
        root = QVBoxLayout(self)
        self._root = root
        root.setContentsMargins(16, 16, 16, 14)
        root.setSpacing(10)
        root.addLayout(top)
        root.addWidget(audio)
        root.addWidget(typed)
        root.addWidget(meeting, 0)
        root.addWidget(self.settings, 0)
        self._apply_chrome()
        self.show_partial("")
        self.show_audio_phrase("")
        self.show_typed_phrase("")

    def _make_top(self) -> QHBoxLayout:
        self._enable.setToolTip("Off stops the microphone.")
        self._enable.toggled.connect(self.enable_toggled.emit)
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setMinimumWidth(96)
        self._copy_btn.setObjectName("ghost")
        self._copy_btn.setToolTip("Copy the last finished sentence again")
        self._copy_btn.clicked.connect(self.copy_requested.emit)
        hide = self._hide_btn
        hide.setObjectName("ghost")
        hide.setToolTip("Hide this window. Click the tray icon to show it.")
        hide.clicked.connect(self.hide_requested.emit)
        brand = QLabel("PersonalClipboard")
        brand.setStyleSheet("color:#e8e8ea; font-size:13px; font-weight:600;")
        top = QHBoxLayout()
        top.setContentsMargins(0, 4, 0, 0)
        top.setSpacing(8)
        top.addWidget(brand)
        top.addStretch(1)
        top.addWidget(self._enable)
        top.addWidget(self._status)
        top.addSpacing(10)
        top.addWidget(self._copy_btn)
        top.addWidget(hide)
        return top

    def _apply_chrome(self) -> None:
        self._status.setStyleSheet(_status_chrome("off"))
        self.setStyleSheet(
            f"""
            QLabel {{ background: transparent; color: #d0d0d4; font-size: 13px; }}
            QFrame#panel {{
                background: rgba(18, 18, 20, 72);
                border: 1px solid rgba(90, 90, 94, 55);
                border-left: 3px solid rgba(80, 80, 84, 70);
                border-radius: 10px;
            }}
            QFrame#panel[active="true"] {{
                border: 1px solid rgba(160, 160, 164, 90);
                border-left: 3px solid {_ACCENT};
            }}
            QCheckBox, QPushButton#ghost, QLineEdit, QPlainTextEdit, QComboBox {{
                background: rgba(14, 14, 16, 88);
                color: #ececee;
                border: 1px solid rgba(90, 90, 94, 70);
                padding: 6px 12px;
                border-radius: 8px;
                min-height: 18px;
            }}
            QCheckBox {{ font-size: 12px; }}
            QCheckBox::indicator {{
                width: 12px; height: 12px; border-radius: 6px;
                border: 1px solid {_ACCENT}; background: rgba(18, 18, 20, 160);
            }}
            QCheckBox::indicator:checked {{ background: {_ACCENT}; }}
            QPushButton#ghost {{ font-size: 12px; min-width: 56px; }}
            QPushButton#ghost:hover, QCheckBox:hover, QLineEdit:focus,
            QPlainTextEdit:focus, QComboBox:hover {{
                border-color: {_ACCENT};
                background: rgba(36, 36, 40, 110);
            }}
            QComboBox {{ font-size: 12px; min-height: 24px; padding: 4px 8px; }}
            QSlider::groove:horizontal {{
                height: 4px; background: rgba(80,80,84,90); border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                width: 12px; height: 12px; margin: -4px 0; border-radius: 6px;
                background: {_ACCENT};
            }}
            QLineEdit, QPlainTextEdit {{
                font-size: 14px; min-height: 28px; padding: 8px 12px;
                selection-background-color: #4a4a50;
            }}
            QPlainTextEdit {{
                font-size: 13px; min-height: 72px;
            }}
            """
        )

    def paintEvent(self, a0: QPaintEvent | None) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        shell = self.rect().adjusted(1, 1, -1, -1)
        painter.setBrush(QColor(14, 14, 16, shell_alpha(self._opacity)))
        painter.setPen(QPen(QColor(70, 70, 74, 80), 1))
        painter.drawRoundedRect(shell, 16, 16)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(200, 200, 204, 70))
        handle = QRect(self.width() // 2 - 18, 8, 36, 4)
        painter.drawRoundedRect(handle, 2, 2)
        painter.end()
        super().paintEvent(a0)

    def showEvent(self, a0: QShowEvent | None) -> None:
        super().showEvent(a0)
        if sys.platform == "win32":
            try:
                enable_thick_frame(int(self.winId()))
            except Exception:
                pass

    def changeEvent(self, a0: QEvent | None) -> None:
        super().changeEvent(a0)
        if a0 is not None and a0.type() == QEvent.Type.DevicePixelRatioChange:
            self._refresh_elides()
            self.clamp_to_screen()

    def nativeEvent(self, eventType, message):  # type: ignore[override]
        """Resize hit-test. Must return (bool, int); super().nativeEvent aborts Qt on Win11."""
        try:
            if sys.platform == "win32" and _is_win_generic_msg(eventType):
                addr = int(message)
                # MSG.from_address on a small integer is not a real pointer.
                if addr > 0xFFFF:
                    hit = self._nchittest_from_message(addr)
                    if hit is not None:
                        return True, hit
        except Exception:
            pass
        return False, 0

    def clamp_to_screen(self) -> None:
        screen = self.screen()
        if screen is None:
            return
        avail = screen.availableGeometry()
        width = min(max(self.width(), self.minimumWidth()), avail.width())
        height = min(max(self.height(), self.minimumHeight()), avail.height())
        if width != self.width() or height != self.height():
            self.resize(width, height)
        x = min(max(self.x(), avail.x()), avail.x() + avail.width() - self.width())
        y = min(max(self.y(), avail.y()), avail.y() + avail.height() - self.height())
        if x != self.x() or y != self.y():
            self.move(x, y)

    def _nchittest_from_message(self, message: int) -> int | None:
        from ctypes import wintypes

        msg = wintypes.MSG.from_address(message)
        if int(msg.message) != 0x0084:  # WM_NCHITTEST
            return None
        global_x, global_y = unpack_nchittest_point(int(msg.lParam))
        local = self.mapFromGlobal(QPoint(global_x, global_y))
        return resize_hit(local.x(), local.y(), self.width(), self.height())

    def resizeEvent(self, a0: QResizeEvent | None) -> None:
        super().resizeEvent(a0)
        self._refresh_elides()

    def show_partial(self, text: str) -> None:
        preview = live_preview(text)
        self._set_elided(self._audio_live, preview, live=True)
        if self._meeting_on:
            self._set_elided(self._meet_live, preview, live=True)

    def show_audio_phrase(self, text: str) -> None:
        stripped = text.strip()
        _set_body(self._audio_body, stripped, self._empty)
        if stripped and not self._meeting_on:
            _set_active(self._audio_frame, True)
            _set_active(self._typed_frame, False)

    def show_typed_phrase(self, text: str) -> None:
        stripped = text.strip()
        _set_body(self._typed_body, stripped, self._empty)
        if stripped and not self._meeting_on:
            _set_active(self._typed_frame, True)
            _set_active(self._audio_frame, False)

    def set_typed(self, text: str) -> None:
        self._updating_input = True
        self._input.set_blocked(True)  # setText must not start type-ahead
        self._input.setText(text)
        self._typed_prev = text
        self._input.set_blocked(False)
        self._updating_input = False

    def typed_text(self) -> str:
        return self._input.text()

    def type_field_active(self) -> bool:
        return self._input.hasFocus() and self._input.isEnabled() and not self._meeting_on

    def focus_type_field(self) -> None:
        if not self.isVisible():
            self.show()
        self.raise_()
        self.activateWindow()
        self._input.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self._input.setCursorPosition(len(self._input.text()))

    def release_type_field(self) -> None:
        self._input.clearFocus()

    def focusNextPrevChild(self, next: bool) -> bool:  # pylint: disable=redefined-builtin
        # Tab in Type stays there (ghost accept). Shift+Tab can leave the field.
        if next and self._input.hasFocus() and self._input.isEnabled():
            return False
        return super().focusNextPrevChild(next)

    def show_prediction(self, prefix: str, suffix: str) -> None:
        if self.type_field_active():
            self._input.set_ghost(prefix, suffix)

    def set_predict_enabled(self, enabled: bool) -> None:
        self._predict_want = enabled
        # Meeting Record keeps the setting but turns the ghost off until Stop.
        self._input.set_predict_enabled(enabled and not self._meeting_on)

    def apply_typed_correction(self, original: str, corrected: str) -> None:
        current = self._input.text().strip()
        if current in ("", original.strip()):
            self.set_typed(corrected)

    def set_status(self, status: str) -> None:
        self._status_key = status
        if not self._flash_timer.isActive():
            self._paint_status(status)

    def set_message(self, text: str) -> None:
        if not text.strip():
            return
        label = flash_label(text)
        key = flash_key(label)
        self._status.setText(t(self._lang, key) if key else label)
        self._status.setStyleSheet(_flash_chrome(text))
        self._flash_timer.start(2200)

    def set_enable_checked(self, checked: bool) -> None:
        self._enable.blockSignals(True)
        self._enable.setChecked(checked)
        self._enable.blockSignals(False)

    def set_listen_enabled(self, enabled: bool) -> None:
        self._enable.setEnabled(enabled)
        self._meet_btn.setEnabled(enabled)

    def apply_language(self, lang: str) -> None:
        self._lang = lang if lang in ("en", "fr", "es", "de") else "en"
        self._empty = t(self._lang, "empty")
        self._relabel()
        self.settings.retranslate(self._lang)
        blanks = {t(code, "empty") for code in ("en", "fr", "es", "de")}
        if self._audio_body.text() in blanks:
            _set_body(self._audio_body, "", self._empty)
        if self._typed_body.text() in blanks:
            _set_body(self._typed_body, "", self._empty)
        if not self._flash_timer.isActive():
            self._paint_status(self._status_key)

    def _relabel(self) -> None:
        lang = self._lang
        self._enable.setText(t(lang, "mic"))
        self._enable.setToolTip(t(lang, "mic_tip"))
        self._copy_btn.setText(t(lang, "copy"))
        copy_key = "copy_meet_tip" if self._meeting_on else "copy_tip"
        self._copy_btn.setToolTip(t(lang, copy_key))
        self._hide_btn.setText(t(lang, "hide"))
        self._hide_btn.setToolTip(t(lang, "hide_tip"))
        self._voice_title.setText(t(lang, "voice"))
        self._hear_tag.setText(t(lang, "hearing"))
        self._type_title.setText(t(lang, "type"))
        self._input.setPlaceholderText(t(lang, "type_hint"))
        self._input.setToolTip(t(lang, "predict_tip"))
        self._meet_title.setText(t(lang, "meeting"))
        self._meet_tag.setText(t(lang, "live"))
        self._meet_btn.setText(t(lang, "stop_save" if self._meeting_on else "record"))
        self._meet_btn.setToolTip(t(lang, "meet_tip"))
        self._meet_notes.setPlaceholderText(t(lang, "meet_hint"))

    def set_opacity(self, percent: int) -> None:
        self._opacity = max(15, min(80, percent))
        self.update()

    def _toggle_meeting(self) -> None:
        self.meeting_toggled.emit(not self._meeting_on)

    def set_meeting_recording(self, active: bool, _path: str = "") -> None:
        self._meeting_on = active
        self._meet_btn.setText(t(self._lang, "stop_save" if active else "record"))
        self._meet_live_row.setVisible(active)
        self._meet_notes.setVisible(active)
        policy = QSizePolicy.Policy.Expanding if active else QSizePolicy.Policy.Maximum
        self._meet_frame.setSizePolicy(QSizePolicy.Policy.Preferred, policy)
        self._root.setStretch(self._root.indexOf(self._meet_frame), 1 if active else 0)
        _set_active(self._meet_frame, active)
        self._audio_frame.setEnabled(not active)
        self._copy_btn.setEnabled(not active)
        self._input.set_predict_enabled(self._predict_want and not active)
        if active:
            self._copy_btn.setToolTip(t(self._lang, "copy_meet_tip"))
            self._set_elided(self._meet_live, "…", live=True)
            self._meet_notes.setPlainText("")
        else:
            self._copy_btn.setToolTip(t(self._lang, "copy_tip"))

    def show_meeting_partial(self, text: str) -> None:
        self._set_elided(self._meet_live, live_preview(text), live=True)

    def show_meeting_notes(self, text: str) -> None:
        self._meet_notes.setPlainText(text)
        self._meet_notes.moveCursor(QTextCursor.MoveOperation.End)

    def _paint_status(self, status: str) -> None:
        self._status.setText(t(self._lang, f"status_{status}"))
        if self._status.text() == f"status_{status}":
            self._status.setText(_STATUS_LABEL.get(status, status))
        self._status.setStyleSheet(_status_chrome(status))

    def _restore_status(self) -> None:
        self._paint_status(self._status_key)

    def _commit_typed_enter(self) -> None:
        phrase = self._input.text().strip()
        if not _has_words(phrase):
            return
        if phrase[-1] in _SENTENCE_END:
            return
        self.phrase_completed.emit(phrase + ".")

    def _on_typed(self, text: str) -> None:
        just_ended = _sentence_just_ended(text, self._typed_prev)
        self._typed_prev = text
        if self._updating_input:
            return
        if just_ended:
            self._input.clear_ghost()
            phrase = text.strip()
            if _has_words(phrase):
                self.phrase_completed.emit(phrase)

    def _set_elided(self, label: QLabel, text: str, *, live: bool) -> None:
        self._elide[label] = (text, live)
        _paint_elided(label, text, live=live)

    def _refresh_elides(self) -> None:
        for label, (text, live) in self._elide.items():
            _paint_elided(label, text, live=live)

    def mousePressEvent(self, a0: QMouseEvent | None) -> None:
        if a0 is not None:
            local = a0.position().toPoint()
            if resize_hit(local.x(), local.y(), self.width(), self.height()) is not None:
                win = self.windowHandle()
                edges = _qt_edges(local, self.width(), self.height())
                if win is not None and edges and win.startSystemResize(edges):
                    self._drag = None
                    a0.accept()
                    return
            child = self.childAt(local)
            if child is not None and not isinstance(child, QLabel):
                self._drag = None
            else:
                win = self.windowHandle()
                if win is not None and win.startSystemMove():
                    self._drag = None
                    a0.accept()
                    return
                self._drag = a0.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(a0)

    def mouseMoveEvent(self, a0: QMouseEvent | None) -> None:
        if a0 is not None and self._drag is not None and a0.buttons() & Qt.MouseButton.LeftButton:
            self.move(a0.globalPosition().toPoint() - self._drag)
        super().mouseMoveEvent(a0)

    def mouseReleaseEvent(self, a0: QMouseEvent | None) -> None:
        self._drag = None
        super().mouseReleaseEvent(a0)


def flash_label(text: str) -> str:
    lowered = text.lower()
    checks = (
        ("empty" in lowered or "nothing" in lowered, "Empty"),
        ("saved" in lowered, "Saved"),
        (lowered.startswith("correcting"), "Correcting"),
        (
            "clipboard" in lowered
            or lowered.startswith("copied")
            or lowered.startswith("pasted"),
            "Copied",
        ),
        ("waiting" in lowered or "loading" in lowered, "Loading"),
        (
            "fail" in lowered or lowered.startswith("error") or "unavailable" in lowered,
            "Error",
        ),
    )
    for matched, label in checks:
        if matched:
            return label
    if len(text) <= 22:
        return text
    return text[:19] + "…"


def live_preview(text: str) -> str:
    clean = _display_partial(text)
    return f"{clean}…" if clean else "…"


def _qt_edges(pos: QPoint, width: int, height: int, margin: int = 8) -> Qt.Edge:
    edges = Qt.Edge(0)
    if pos.x() <= margin:
        edges |= Qt.Edge.LeftEdge
    if pos.x() >= width - margin:
        edges |= Qt.Edge.RightEdge
    if pos.y() <= margin:
        edges |= Qt.Edge.TopEdge
    if pos.y() >= height - margin:
        edges |= Qt.Edge.BottomEdge
    return edges


def _is_win_generic_msg(event_type: object) -> bool:
    marker = b"windows_generic_MSG"
    if event_type == marker:
        return True
    return isinstance(event_type, QByteArray) and event_type == QByteArray(marker)


def _has_words(text: str) -> bool:
    return any(char.isalnum() for char in text)


def _sentence_just_ended(text: str, prev: str) -> bool:
    if not text or text[-1] not in _SENTENCE_END:
        return False
    return not prev or prev[-1] not in _SENTENCE_END


def _display_partial(text: str) -> str:
    clean = " ".join(text.split())
    letters = "".join(char for char in clean if char.isalnum())
    if len(letters) < 2:
        return ""
    return clean


def _paint_elided(label: QLabel, text: str, *, live: bool) -> None:
    width = max(label.width() - 16, 40)
    metrics = QFontMetrics(label.font())
    source = text.strip() if text else ""
    if live:
        source = source if source.endswith("…") else f"{source}…" if source else "…"
    elif not source:
        source = "…"
    label.setText(metrics.elidedText(source, Qt.TextElideMode.ElideRight, width))


def _status_chrome(status: str) -> str:
    fill = _STATUS_STYLE.get(status, _STATUS_STYLE["off"])
    return "padding: 6px 12px; border-radius: 8px; font-size: 12px; " + fill


def _flash_chrome(text: str) -> str:
    lowered = text.lower()
    bad = "fail" in lowered or lowered.startswith("error") or "unavailable" in lowered
    fill = (
        _pill("#c8c8cc", "rgba(28,28,30,140)", "rgba(110,110,114,90)")
        if bad
        else _pill("#f4f4f6", "rgba(56,56,60,145)", "rgba(180,180,184,100)")
    )
    return "padding: 6px 12px; border-radius: 8px; font-size: 12px; " + fill


def _set_active(frame: QFrame, active: bool) -> None:
    frame.setProperty("active", "true" if active else "false")
    style = frame.style()
    if style is not None:
        style.unpolish(frame)
        style.polish(frame)


def _set_body(label: QLabel, text: str, empty: str = _EMPTY) -> None:
    filled = bool(text.strip())
    label.setText(text.strip() if filled else empty)
    color = "#f2f2f4" if filled else "#7a7a80"
    label.setStyleSheet(
        f"color:{color}; font-size:15px; padding:10px 12px; background:rgba(12,12,14,70);"
        "border:1px solid rgba(80,80,84,50); border-radius:8px;"
    )


def _result_panel(
    title: str,
    *,
    live_tag: str | None = None,
    extra: QWidget | None = None,
    parent: QWidget | None = None,
) -> tuple[QFrame, QLabel, QLabel, QLabel, QLabel]:
    frame = QFrame(parent)
    frame.setObjectName("panel")
    frame.setProperty("active", "false")
    header = QLabel(title)
    header.setStyleSheet("color:#c8c8cc; font-size:11px; font-weight:600;")
    body = QLabel(_EMPTY)
    body.setWordWrap(True)
    body.setMinimumHeight(44)
    body.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
    body.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
    _set_body(body, "")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(12, 10, 12, 12)
    layout.setSpacing(8)
    layout.addWidget(header)
    live: QLabel
    if live_tag is not None:
        live_row, live, tag = _tagged_line(live_tag, "#b8b8bc")
        layout.addWidget(live_row)
    else:
        live = QLabel("…")
        live.hide()
        live.setParent(frame)
        tag = QLabel("")
        tag.hide()
        tag.setParent(frame)
    if extra is not None:
        layout.addWidget(extra)
    layout.addWidget(body)
    return frame, live, body, header, tag


def _meeting_panel(
    parent: QWidget | None = None,
) -> tuple[QFrame, QPushButton, QLabel, QPlainTextEdit, QWidget, QLabel, QLabel]:
    frame = QFrame(parent)
    frame.setObjectName("panel")
    frame.setProperty("active", "false")
    header = QLabel("Meeting")
    header.setStyleSheet("color:#c8c8cc; font-size:11px; font-weight:600;")
    button = QPushButton("Record")
    button.setObjectName("ghost")
    button.setToolTip(
        "Transcribe this room and save notes to the desktop. "
        "Speech goes to the file, not the clipboard. Use speakers for other voices."
    )
    top = QHBoxLayout()
    top.setContentsMargins(0, 0, 0, 0)
    top.setSpacing(8)
    top.addWidget(header)
    top.addStretch(1)
    top.addWidget(button)
    live_row, live, tag = _tagged_line("Live", "#b8b8bc")
    live_row.setVisible(False)
    notes = QPlainTextEdit()
    notes.setReadOnly(True)
    notes.setPlaceholderText("Meeting transcript appears here.")
    notes.setMinimumHeight(72)
    notes.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    notes.setTabChangesFocus(True)
    notes.setVisible(False)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(12, 10, 12, 12)
    layout.setSpacing(8)
    layout.addLayout(top)
    layout.addWidget(live_row)
    layout.addWidget(notes)
    return frame, button, live, notes, live_row, header, tag


def _tagged_line(tag: str, color: str) -> tuple[QWidget, QLabel, QLabel]:
    row = QWidget()
    tag_lab = QLabel(tag)
    tag_lab.setFixedWidth(62)
    tag_lab.setStyleSheet("color:#8a8a90; font-size:11px;")
    line = QLabel("…")
    line.setWordWrap(False)
    line.setFixedHeight(26)
    line.setTextFormat(Qt.TextFormat.PlainText)
    font = QFont("Cascadia Mono", 10)
    if not font.exactMatch():
        font = QFont("Consolas", 10)
    line.setFont(font)
    line.setStyleSheet(
        f"color:{color}; font-size:13px; padding:4px 10px; background:rgba(12,12,14,70);"
        "border:1px solid rgba(80,80,84,50); border-radius:6px;"
    )
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)
    layout.addWidget(tag_lab)
    layout.addWidget(line, 1)
    return row, line, tag_lab
