"""Frameless HUD overlay: voice, type, and collapsible meeting notes."""

from __future__ import annotations

import sys

from PyQt6.QtCore import QByteArray, QEvent, QPoint, QRect, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QAction,
    QColor,
    QFont,
    QFontMetrics,
    QMouseEvent,
    QMoveEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QResizeEvent,
    QShowEvent,
    QTextCursor,
)
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from personalclipboard.config import OPACITY_MAX, OPACITY_MIN, shell_alpha
from personalclipboard.ui.i18n import LANG_CODES, flash_key, t, ui_lang
from personalclipboard.ui.predict_edit import PredictLineEdit
from personalclipboard.ui.settings_panel import SettingsPanel
from personalclipboard.ui.theme import control_chrome, pointing
from personalclipboard.ui.win11_resize import (
    enable_thick_frame,
    resize_hit,
    unpack_nchittest_point,
)

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


# Status hues match the Mic light: red = off, grey = waiting, green = live.
_STATUS_STYLE = {
    "off": _pill("#f0c8c4", "rgba(72,28,28,150)", "rgba(200,80,80,120)"),
    "loading": _pill("#efe0b8", "rgba(58,48,22,140)", "rgba(180,150,70,90)"),
    "listening": _pill("#d8f5e4", "rgba(24,56,38,150)", "rgba(80,180,110,110)"),
    "uncertain": _pill("#ece4cc", "rgba(52,44,24,140)", "rgba(170,140,70,95)"),
    "locked": _pill("#d8f5e4", "rgba(24,56,38,150)", "rgba(80,180,110,110)"),
    "recording": _pill("#d8f5e4", "rgba(24,56,38,155)", "rgba(80,190,120,130)"),
    "quiet": _pill("#d0d0d4", "rgba(36,36,40,120)", "rgba(140,140,144,80)"),
    "error": _pill("#f0d4d0", "rgba(62,32,32,150)", "rgba(180,90,90,110)"),
}

# Phrase/live field backgrounds: empty, in-progress, ready, warning, error.
_TEXT_TONE = {
    "empty": ("#9c9ca4", "rgba(12,12,14,70)", "rgba(80,80,84,50)"),
    "live": ("#d4e4f4", "rgba(28,48,72,130)", "rgba(80,130,180,95)"),
    "correcting": ("#eee4c8", "rgba(56,46,24,135)", "rgba(180,150,70,100)"),
    "ready": ("#d8eedc", "rgba(28,52,36,130)", "rgba(80,150,100,95)"),
    "uncertain": ("#ece6d4", "rgba(48,42,28,125)", "rgba(160,130,70,90)"),
    "error": ("#f0d4d0", "rgba(56,30,30,135)", "rgba(170,90,90,100)"),
}


class Overlay(QWidget):
    enable_toggled = pyqtSignal(bool)
    hide_requested = pyqtSignal()
    copy_requested = pyqtSignal()
    history_requested = pyqtSignal()
    records_requested = pyqtSignal()
    phrase_completed = pyqtSignal(str)
    record_start_requested = pyqtSignal(str)
    record_stop_requested = pyqtSignal()
    meeting_toggled = pyqtSignal(bool)
    prediction_requested = pyqtSignal(str)
    retry_requested = pyqtSignal()
    correction_mode_changed = pyqtSignal(str)
    geometry_changed = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self._drag: QPoint | None = None
        self._updating_input = False
        self._typed_prev = ""
        self._elide: dict[QLabel, tuple[str, bool, str]] = {}
        self._meeting_on = False
        self._record_kind = ""
        self._predict_want = True
        self._settings_closed_size: QSize | None = None
        self._status_key = "off"
        self._enable = QCheckBox("Mic", self)
        self._enable.setObjectName("micToggle")
        self._status = QLabel("Mic off", self)
        self._flash_timer = QTimer(self)
        self._flash_timer.setSingleShot(True)
        self._flash_timer.timeout.connect(self._restore_status)
        self._copy_btn = QPushButton("Copy", self)
        self._history_btn = QPushButton("Clips", self)
        self._record_btn = QPushButton("Record", self)
        self._records_btn = QPushButton("Records", self)
        self._settings_btn = QPushButton("Settings", self)
        self._hide_btn = QPushButton("Hide", self)
        self._brand = QLabel("Clipboard", self)
        self._lang = "en"
        self._opacity = 80
        self._empty = t("en", "empty")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFont(QFont("Segoe UI", 10))
        self.setMinimumWidth(500)
        self._build()
        self._root.setSizeConstraint(QVBoxLayout.SizeConstraint.SetDefaultConstraint)
        self.resize(560, max(self.sizeHint().height(), 280))

    def _build(self) -> None:
        top = self._make_top()
        self._voice_role = _role_tag("Dictation", self)
        (
            audio,
            self._audio_live,
            self._audio_body,
            self._voice_title,
            self._hear_tag,
            self._audio_cycle,
        ) = _result_panel(
            "Voice",
            live_tag="Hearing",
            header_extra=self._voice_role,
            role="voice",
            parent=self,
        )
        self._audio_frame = audio
        audio.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self._input = PredictLineEdit(self)
        self._input.setPlaceholderText("Type, then Enter or a period.")
        self._input.textChanged.connect(self._on_typed)
        self._input.returnPressed.connect(self._commit_typed_enter)
        self._input.prediction_requested.connect(self.prediction_requested.emit)
        self._mode_human, self._mode_ai, mode_row = _correction_radios(self)
        self._mode_group = QButtonGroup(self)
        self._mode_group.setExclusive(True)
        self._mode_group.addButton(self._mode_human)
        self._mode_group.addButton(self._mode_ai)
        self._mode_human.toggled.connect(self._on_correction_mode)
        self._mode_ai.toggled.connect(self._on_correction_mode)
        typed, _, self._typed_body, self._type_title, _tag, self._typed_cycle = _result_panel(
            "Type", extra=self._input, header_extra=mode_row, role="type", parent=self
        )
        self._audio_cycle.clicked.connect(self.retry_requested.emit)
        self._typed_cycle.clicked.connect(self.retry_requested.emit)
        _tag.hide()
        self._typed_frame = typed
        typed.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        pack = _meeting_panel(self)
        meeting = pack[0]
        self._meet_btn = pack[1]
        self._meet_live = pack[2]
        self._meet_notes = pack[3]
        self._meet_live_row = pack[4]
        self._meet_title = pack[5]
        self._meet_tag = pack[6]
        self._meet_frame = meeting
        meeting.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self._meet_btn.clicked.connect(self._stop_recording)
        self.settings = SettingsPanel(self)
        self.settings.language_changed.connect(self.apply_language)
        self.settings.opacity_changed.connect(self.set_opacity)
        self.settings.expanded_changed.connect(self._on_settings_expanded)
        self._settings_btn.clicked.connect(self.settings.toggle)
        actions = self._make_actions()
        meeting.setVisible(False)
        root = QVBoxLayout(self)
        self._root = root
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)
        self._section_rule = _section_rule(self)
        root.addLayout(top)
        root.addWidget(audio, 0)
        root.addWidget(self._section_rule, 0)
        root.addWidget(typed, 0)
        root.addWidget(meeting, 0)
        root.addWidget(self.settings, 0)
        self._slack = QWidget(self)
        self._slack.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self._slack.setMinimumHeight(0)
        root.addWidget(self._slack, 1)
        root.addWidget(actions, 0)
        self._apply_chrome()
        self._relabel()
        self.show_partial("")
        self.show_audio_phrase("")
        self.show_typed_phrase("")

    def _make_top(self) -> QHBoxLayout:
        self._enable.setToolTip(t("en", "mic_tip"))
        self._enable.toggled.connect(self._on_mic_toggled)
        self._status.setObjectName("statusPill")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setMinimumWidth(100)
        self._status.setToolTip(t("en", "status_tip"))
        hide = self._hide_btn
        hide.setObjectName("quiet")
        hide.setToolTip(t("en", "hide_tip"))
        hide.clicked.connect(self.hide_requested.emit)
        self._brand.setObjectName("brand")
        self._brand.setToolTip(t("en", "brand_tip"))
        pointing(self._enable, hide)
        top = QHBoxLayout()
        top.setContentsMargins(0, 6, 0, 2)
        top.setSpacing(8)
        top.addWidget(self._brand)
        top.addStretch(1)
        top.addWidget(self._enable)
        top.addWidget(self._status)
        top.addWidget(hide)
        return top

    def _make_actions(self) -> QFrame:
        for button, name in (
            (self._copy_btn, "ghost"),
            (self._history_btn, "ghost"),
            (self._record_btn, "primary"),
            (self._records_btn, "ghost"),
            (self._settings_btn, "ghost"),
        ):
            button.setObjectName(name)
            pointing(button)
        self._copy_btn.clicked.connect(self.copy_requested.emit)
        self._history_btn.clicked.connect(self.history_requested.emit)
        self._records_btn.clicked.connect(self.records_requested.emit)
        self._record_btn.clicked.connect(self._on_record_clicked)
        self._record_menu = QMenu(self)
        self._act_meeting = QAction(t("en", "record_meeting"), self)
        self._act_playback = QAction(t("en", "record_playback"), self)
        self._record_menu.addAction(self._act_meeting)
        self._record_menu.addAction(self._act_playback)
        self._act_meeting.triggered.connect(lambda: self.record_start_requested.emit("meeting"))
        self._act_playback.triggered.connect(lambda: self.record_start_requested.emit("playback"))
        bar = QFrame(self)
        bar.setObjectName("actions")
        row = QHBoxLayout(bar)
        row.setContentsMargins(0, 2, 0, 0)
        row.setSpacing(8)
        row.addWidget(self._copy_btn)
        row.addWidget(self._history_btn)
        row.addWidget(self._record_btn)
        row.addWidget(self._records_btn)
        row.addStretch(1)
        row.addWidget(self._settings_btn)
        return bar

    def _apply_chrome(self) -> None:
        self._status.setStyleSheet(_status_chrome("off"))
        self.setStyleSheet(
            control_chrome()
            + """
            QLabel#statusPill {
                font-size: 12px; font-weight: 600;
            }
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
        painter.setBrush(QColor(220, 220, 224, 130))
        handle = QRect(self.width() // 2 - 20, 8, 40, 5)
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
        if self.minimumWidth() > avail.width():
            self.setMinimumWidth(min(400, avail.width()))
        if self.minimumHeight() > avail.height():
            self.setMinimumHeight(avail.height())
        width = min(max(self.width(), self.minimumWidth()), avail.width())
        height = min(max(self.height(), self.minimumHeight()), avail.height())
        height = min(height, self.maximumHeight())
        width = min(width, self.maximumWidth())
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

    def compact_geometry(self) -> QRect:
        """Collapsed HUD box. Settings-open height is not a session size."""
        closed = self._settings_closed_size
        if self.settings.is_expanded() and closed is not None:
            return QRect(self.x(), self.y(), closed.width(), closed.height())
        return QRect(self.x(), self.y(), self.width(), self.height())

    def moveEvent(self, a0: QMoveEvent | None) -> None:
        super().moveEvent(a0)
        self.geometry_changed.emit()

    def resizeEvent(self, a0: QResizeEvent | None) -> None:
        super().resizeEvent(a0)
        self._refresh_elides()
        self.geometry_changed.emit()

    def show_partial(self, text: str) -> None:
        preview = live_preview(text)
        tone = "live" if preview not in ("", "…") else "empty"
        if self._status_key == "uncertain" and tone == "live":
            tone = "uncertain"
        self._set_elided(self._audio_live, preview, live=True, state=tone)
        if self._meeting_on:
            self._set_elided(self._meet_live, preview, live=True, state=tone)

    def show_audio_phrase(self, text: str, *, state: str | None = None) -> None:
        stripped = text.strip()
        tone = state or ("ready" if stripped else "empty")
        _set_body(self._audio_body, stripped, self._empty, state=tone)
        self._sync_output_cycle("audio", bool(stripped), busy=tone == "correcting")
        if not self._meeting_on:
            _set_active(self._audio_frame, bool(stripped) and tone != "empty")

    def show_typed_phrase(self, text: str, *, state: str | None = None) -> None:
        stripped = text.strip()
        tone = state or ("ready" if stripped else "empty")
        _set_body(self._typed_body, stripped, self._empty, state=tone)
        self._sync_output_cycle("typed", bool(stripped), busy=tone == "correcting")
        if not self._meeting_on:
            _set_active(self._typed_frame, bool(stripped) and tone != "empty")

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

    def apply_typed_correction(
        self,
        original: str,
        corrected: str,
        *,
        previous: str = "",
    ) -> None:
        current = self._input.text().strip()
        allowed = {original.strip(), previous.strip(), ""}
        if current in allowed:
            self.set_typed(corrected)

    def _sync_output_cycle(self, source: str, filled: bool, *, busy: bool) -> None:
        for name, button in (("audio", self._audio_cycle), ("typed", self._typed_cycle)):
            visible = filled and name == source and not self._meeting_on
            button.setVisible(visible)
            button.setEnabled(visible and not busy)

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

    def correction_mode(self) -> str:
        return "ai" if self._mode_ai.isChecked() else "human"

    def set_correction_mode(self, mode: str) -> None:
        ai = mode == "ai"
        self._mode_human.blockSignals(True)
        self._mode_ai.blockSignals(True)
        self._mode_ai.setChecked(ai)
        self._mode_human.setChecked(not ai)
        self._mode_human.blockSignals(False)
        self._mode_ai.blockSignals(False)

    def _on_correction_mode(self, checked: bool) -> None:
        if not checked:
            return
        self.correction_mode_changed.emit(self.correction_mode())

    def set_listen_enabled(self, enabled: bool) -> None:
        self._enable.setEnabled(enabled)
        self._meet_btn.setEnabled(enabled)
        self._record_btn.setEnabled(enabled)

    def apply_language(self, lang: str) -> None:
        self._lang = ui_lang(lang)
        self._empty = t(self._lang, "empty")
        self._relabel()
        self.settings.retranslate(self._lang)
        blanks = {t(code, "empty") for code in LANG_CODES}
        if self._audio_body.text() in blanks:
            _set_body(self._audio_body, "", self._empty, state="empty")
        if self._typed_body.text() in blanks:
            _set_body(self._typed_body, "", self._empty, state="empty")
        if not self._flash_timer.isActive():
            self._paint_status(self._status_key)

    def _relabel(self) -> None:
        lang = self._lang
        self._brand.setText(t(lang, "app_title"))
        self._brand.setToolTip(t(lang, "brand_tip"))
        self._history_btn.setText(t(lang, "clips"))
        self._history_btn.setToolTip(t(lang, "clips_tip"))
        self._records_btn.setText(t(lang, "records"))
        self._records_btn.setToolTip(t(lang, "records_tip"))
        self._settings_btn.setText(t(lang, "hide" if self.settings.is_expanded() else "settings"))
        self._settings_btn.setToolTip(t(lang, "hide_tip" if self.settings.is_expanded() else "settings_tip"))
        self._enable.setText(t(lang, "mic"))
        self._enable.setToolTip(t(lang, "mic_tip"))
        self._status.setToolTip(t(lang, "status_tip"))
        self._copy_btn.setText(t(lang, "copy"))
        copy_key = "copy_meet_tip" if self._meeting_on else "copy_tip"
        self._copy_btn.setToolTip(t(lang, copy_key))
        self._hide_btn.setText(t(lang, "hide"))
        self._hide_btn.setToolTip(t(lang, "hide_tip"))
        self._voice_title.setText(t(lang, "voice"))
        self._voice_title.setToolTip(t(lang, "voice_tip"))
        self._voice_role.setText(t(lang, "voice_role"))
        self._voice_role.setToolTip(t(lang, "voice_tip"))
        self._hear_tag.setText(t(lang, "hearing"))
        self._hear_tag.setToolTip(t(lang, "hearing_tip"))
        self._audio_live.setToolTip(t(lang, "hearing_tip"))
        self._audio_body.setToolTip(t(lang, "voice_phrase_tip"))
        self._type_title.setText(t(lang, "type"))
        self._type_title.setToolTip(t(lang, "type_tip"))
        self._mode_human.setToolTip(t(lang, "correct_human_tip"))
        self._mode_ai.setToolTip(t(lang, "correct_ai_tip"))
        self._typed_body.setToolTip(t(lang, "type_phrase_tip"))
        self._input.setPlaceholderText(t(lang, "type_hint"))
        self._input.setToolTip(t(lang, "type_tip"))
        self._input.set_clear_labels(t(lang, "clear"), t(lang, "clear_tip"))
        self._audio_cycle.setToolTip(t(lang, "retry_tip"))
        self._typed_cycle.setToolTip(t(lang, "retry_tip"))
        kind_key = "kind_playback" if self._record_kind == "playback" else "kind_meeting"
        self._meet_title.setText(t(lang, kind_key if self._meeting_on else "meeting"))
        self._meet_title.setToolTip(t(lang, "playback_tip" if self._record_kind == "playback" else "meet_tip"))
        self._meet_tag.setText(t(lang, "live"))
        self._meet_tag.setToolTip(t(lang, "hearing_tip"))
        self._meet_live.setToolTip(t(lang, "hearing_tip"))
        recording = self._meeting_on
        self._record_btn.setText(t(lang, "stop_save" if recording else "record"))
        self._record_btn.setToolTip(t(lang, "meet_tip" if recording else "record_menu_tip"))
        self._meet_btn.setText(t(lang, "stop_save" if recording else "record"))
        self._meet_btn.setToolTip(t(lang, "meet_tip" if self._record_kind != "playback" else "playback_tip"))
        self._meet_notes.setPlaceholderText(t(lang, "meet_hint"))
        self._meet_notes.setToolTip(t(lang, "meet_hint"))
        self._act_meeting.setText(t(lang, "record_meeting"))
        self._act_meeting.setToolTip(t(lang, "meet_tip"))
        self._act_playback.setText(t(lang, "record_playback"))
        self._act_playback.setToolTip(t(lang, "playback_tip"))

    def set_opacity(self, percent: int) -> None:
        self._opacity = max(OPACITY_MIN, min(OPACITY_MAX, percent))
        self.update()

    def _on_mic_toggled(self, checked: bool) -> None:
        self.enable_toggled.emit(checked)

    def _on_settings_expanded(self, opened: bool) -> None:
        self._settings_btn.setText(t(self._lang, "hide" if opened else "settings"))
        self._settings_btn.setToolTip(t(self._lang, "hide_tip" if opened else "settings_tip"))
        self._fit_settings(opened)
        QTimer.singleShot(0, self._refit_settings)

    def _refit_settings(self) -> None:
        opened = self.settings.is_expanded()
        self._fit_settings(opened)
        if not opened:
            QTimer.singleShot(0, self._release_settings_max)

    def _fit_settings(self, opened: bool) -> None:
        # Grow downward for Settings. Never pin min-height to the open size, or Hide cannot shrink.
        if opened:
            if self._settings_closed_size is None:
                self._settings_closed_size = QSize(self.width(), self.height())
            extra = self.settings.extra_open_height()
            need_w = max(self.width(), self._settings_closed_size.width())
            need_h = self._settings_closed_size.height() + extra
            self.setMaximumHeight(16777215)
            self.setMinimumHeight(self._settings_closed_size.height())
            self.resize(need_w, need_h)
            self.clamp_to_screen()
            gained = self.height() - self._settings_closed_size.height()
            self.settings.adopt_open_space(max(gained, 64))
            return
        closed = self._settings_closed_size
        self.setMinimumHeight(0)
        self._root.invalidate()
        self._root.activate()
        if closed is not None:
            self.setMaximumHeight(max(closed.height(), 220))
            self.resize(closed)
        else:
            hint_h = max(self.sizeHint().height(), 220)
            self.setMaximumHeight(hint_h)
            self.resize(max(self.width(), 400), hint_h)
        self.clamp_to_screen()

    def _release_settings_max(self) -> None:
        if self.settings.is_expanded():
            return
        self.setMaximumHeight(16777215)
        closed = self._settings_closed_size
        self._settings_closed_size = None
        if closed is not None:
            drifted = (
                abs(self.height() - closed.height()) > 8
                or abs(self.width() - closed.width()) > 8
            )
            if drifted:
                self.resize(closed)
        self.clamp_to_screen()

    def _on_record_clicked(self) -> None:
        if self._meeting_on:
            self._stop_recording()
            return
        point = self._record_btn.mapToGlobal(self._record_btn.rect().bottomLeft())
        self._record_menu.exec(point)

    def _stop_recording(self) -> None:
        self.record_stop_requested.emit()

    def _toggle_meeting(self) -> None:
        if self._meeting_on:
            self._stop_recording()
            return
        self.record_start_requested.emit("meeting")
        self.meeting_toggled.emit(True)

    def set_meeting_recording(self, active: bool, _path: str = "", kind: str = "meeting") -> None:
        self._meeting_on = active
        self._record_kind = kind if active else ""
        self._record_btn.setText(t(self._lang, "stop_save" if active else "record"))
        self._record_btn.setObjectName("danger" if active else "primary")
        _polish_widget(self._record_btn)
        self._meet_btn.setText(t(self._lang, "stop_save" if active else "record"))
        self._meet_btn.setObjectName("danger" if active else "primary")
        _polish_widget(self._meet_btn)
        self._meet_frame.setVisible(active)
        self._meet_live_row.setVisible(active)
        self._meet_notes.setVisible(active)
        policy = QSizePolicy.Policy.Expanding if active else QSizePolicy.Policy.Minimum
        self._meet_frame.setSizePolicy(QSizePolicy.Policy.Preferred, policy)
        meet_i = self._root.indexOf(self._meet_frame)
        slack_i = self._root.indexOf(self._slack)
        self._root.setStretch(meet_i, 1 if active else 0)
        self._root.setStretch(slack_i, 0 if active else 1)
        self._slack.setVisible(not active)
        _set_active(self._meet_frame, active)
        self._audio_frame.setEnabled(not active)
        self._typed_frame.setEnabled(not active)
        self._copy_btn.setEnabled(not active)
        self._history_btn.setEnabled(not active)
        self._audio_cycle.setVisible(False)
        self._typed_cycle.setVisible(False)
        self._input.set_predict_enabled(self._predict_want and not active)
        if active:
            self._copy_btn.setToolTip(t(self._lang, "copy_meet_tip"))
            self._set_elided(self._meet_live, "…", live=True, state="live")
            self._meet_notes.setPlainText("")
            kind_key = "kind_playback" if kind == "playback" else "kind_meeting"
            self._meet_title.setText(t(self._lang, kind_key))
            self._meet_title.setToolTip(
                t(self._lang, "playback_tip" if kind == "playback" else "meet_tip")
            )
        else:
            self._copy_btn.setToolTip(t(self._lang, "copy_tip"))
            self._meet_title.setText(t(self._lang, "meeting"))
        self._record_btn.setToolTip(
            t(self._lang, "meet_tip" if active else "record_menu_tip")
        )

    def show_meeting_partial(self, text: str) -> None:
        preview = live_preview(text)
        tone = "live" if preview not in ("", "…") else "empty"
        self._set_elided(self._meet_live, preview, live=True, state=tone)

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

    def _set_elided(self, label: QLabel, text: str, *, live: bool, state: str = "empty") -> None:
        self._elide[label] = (text, live, state)
        _paint_elided(label, text, live=live, state=state)

    def _refresh_elides(self) -> None:
        for label, (text, live, state) in self._elide.items():
            _paint_elided(label, text, live=live, state=state)

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


def _paint_elided(label: QLabel, text: str, *, live: bool, state: str = "empty") -> None:
    width = max(label.width() - 16, 40)
    metrics = QFontMetrics(label.font())
    source = text.strip() if text else ""
    if live:
        source = source if source.endswith("…") else f"{source}…" if source else "…"
    elif not source:
        source = "…"
    label.setText(metrics.elidedText(source, Qt.TextElideMode.ElideRight, width))
    label.setStyleSheet(_field_chrome(state, size=13, pad="4px 10px", radius=6))
    label.setToolTip(text.strip() if text.strip() else "")


def _status_chrome(status: str) -> str:
    fill = _STATUS_STYLE.get(status, _STATUS_STYLE["off"])
    return (
        "padding: 5px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; "
        + fill
    )


def _flash_chrome(text: str) -> str:
    label = flash_label(text)
    tones = {
        "Error": "error",
        "Correcting": "correcting",
        "Loading": "correcting",
        "Copied": "ready",
        "Saved": "ready",
        "Empty": "empty",
    }
    return (
        "padding: 5px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; "
        + _tone_pill(tones.get(label, "ready"))
    )


def _tone_pill(state: str) -> str:
    fg, bg, bd = _TEXT_TONE.get(state, _TEXT_TONE["empty"])
    return _pill(fg, bg, bd)


def _field_chrome(state: str, *, size: int, pad: str, radius: int) -> str:
    fg, bg, bd = _TEXT_TONE.get(state, _TEXT_TONE["empty"])
    return (
        f"color:{fg}; font-size:{size}px; padding:{pad}; background:{bg};"
        f"border:1px solid {bd}; border-radius:{radius}px;"
    )


def _set_active(frame: QFrame, active: bool) -> None:
    frame.setProperty("active", "true" if active else "false")
    _polish_widget(frame)


def _polish_widget(widget: QWidget) -> None:
    style = widget.style()
    if style is not None:
        style.unpolish(widget)
        style.polish(widget)
    widget.update()


def _set_body(label: QLabel, text: str, empty: str = _EMPTY, *, state: str = "empty") -> None:
    filled = bool(text.strip())
    label.setText(text.strip() if filled else empty)
    tone = state if state in _TEXT_TONE else ("ready" if filled else "empty")
    label.setStyleSheet(_field_chrome(tone, size=15, pad="10px 12px", radius=8))
    label.setToolTip(text.strip() if filled else empty)


def _role_tag(text: str, parent: QWidget | None = None) -> QLabel:
    tag = QLabel(text, parent)
    tag.setObjectName("roleTag")
    return tag


def _section_rule(parent: QWidget | None = None) -> QFrame:
    line = QFrame(parent)
    line.setObjectName("sectionRule")
    line.setFixedHeight(8)
    return line


def _correction_radios(parent: QWidget | None = None) -> tuple[QRadioButton, QRadioButton, QWidget]:
    row = QWidget(parent)
    row.setObjectName("modeRow")
    human = QRadioButton("☺", row)
    ai = QRadioButton("✦", row)
    icon_font = QFont("Segoe UI Symbol", 11)
    if not icon_font.exactMatch():
        icon_font = QFont("Segoe UI", 11)
    for button, name in ((human, "Human"), (ai, "AI")):
        button.setObjectName("modeRadio")
        button.setAccessibleName(name)
        button.setAutoExclusive(False)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setFont(icon_font)
        button.setFixedHeight(22)
        pointing(button)
    human.setChecked(True)
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)
    layout.addWidget(human)
    layout.addWidget(ai)
    return human, ai, row


def _icon_button(mark: str, parent: QWidget | None = None) -> QToolButton:
    button = QToolButton(parent)
    button.setObjectName("iconBtn")
    button.setText(mark)
    button.setAutoRaise(True)
    button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    button.setFixedSize(28, 28)
    button.setVisible(False)
    pointing(button)
    return button


def _result_panel(
    title: str,
    *,
    live_tag: str | None = None,
    extra: QWidget | None = None,
    header_extra: QWidget | None = None,
    role: str = "",
    parent: QWidget | None = None,
) -> tuple[QFrame, QLabel, QLabel, QLabel, QLabel, QToolButton]:
    frame = QFrame(parent)
    if role == "voice":
        frame.setObjectName("voicePanel")
    elif role == "type":
        frame.setObjectName("typePanel")
    else:
        frame.setObjectName("panel")
    frame.setProperty("active", "false")
    header = QLabel(title)
    header.setObjectName("sectionTitle")
    body = QLabel(_EMPTY)
    body.setWordWrap(True)
    body.setMinimumHeight(44)
    body.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
    body.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
    _set_body(body, "")
    cycle = _icon_button("↻", frame)
    cycle.setAccessibleName("Retry")
    row = QWidget(frame)
    row_layout = QHBoxLayout(row)
    row_layout.setContentsMargins(0, 0, 0, 0)
    row_layout.setSpacing(6)
    row_layout.addWidget(body, 1)
    row_layout.addWidget(cycle, 0, Qt.AlignmentFlag.AlignTop)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(12, 10, 12, 12)
    layout.setSpacing(8)
    head = QHBoxLayout()
    head.setContentsMargins(0, 0, 0, 0)
    head.setSpacing(8)
    head.addWidget(header, 0, Qt.AlignmentFlag.AlignVCenter)
    head.addStretch(1)
    if header_extra is not None:
        head.addWidget(header_extra, 0, Qt.AlignmentFlag.AlignVCenter)
    layout.addLayout(head)
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
    layout.addWidget(row)
    return frame, live, body, header, tag, cycle


def _meeting_panel(
    parent: QWidget | None = None,
) -> tuple[QFrame, QPushButton, QLabel, QPlainTextEdit, QWidget, QLabel, QLabel]:
    frame = QFrame(parent)
    frame.setObjectName("panel")
    frame.setProperty("active", "false")
    header = QLabel("Recording")
    header.setObjectName("sectionTitle")
    button = QPushButton("Stop")
    button.setObjectName("danger")
    pointing(button)
    button.setToolTip(
        "Stop recording and save the transcript to the desktop."
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
    tag_lab.setStyleSheet("color:#a8a8ae; font-size:11px; font-weight: 600;")
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
