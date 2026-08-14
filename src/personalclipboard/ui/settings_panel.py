"""Collapsible HUD settings: language, opacity, models, VAD, type-ahead."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from personalclipboard.config import OLLAMA_CHOICES, WHISPER_CHOICES
from personalclipboard.ui.i18n import LANGS, t


class SettingsPanel(QFrame):
    language_changed = pyqtSignal(str)
    opacity_changed = pyqtSignal(int)
    whisper_changed = pyqtSignal(str)
    ollama_changed = pyqtSignal(str)
    vad_changed = pyqtSignal(bool)
    predict_changed = pyqtSignal(bool)
    expanded_changed = pyqtSignal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("panel")
        self.setProperty("active", "false")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self._open = False
        self._lang = "en"
        self._updating = False
        self._make_fields()
        self._body = QFrame(self)
        self._body.setVisible(False)
        body_layout = QVBoxLayout(self._body)
        body_layout.setContentsMargins(2, 6, 2, 4)
        body_layout.setSpacing(12)
        body_layout.addLayout(_row(self._lang_label, self._lang_box))
        body_layout.addLayout(_row(self._opacity_label, self._opacity))
        body_layout.addLayout(_row(self._whisper_label, self._whisper))
        body_layout.addLayout(_row(self._ollama_label, self._ollama))
        body_layout.addWidget(self._vad)
        body_layout.addWidget(self._predict)
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.addWidget(self._header)
        top.addStretch(1)
        top.addWidget(self._toggle)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(8)
        layout.addLayout(top)
        layout.addWidget(self._body)
        self.retranslate("en")

    def _make_fields(self) -> None:
        self._header = QLabel(self)
        self._header.setStyleSheet("color:#c8c8cc; font-size:11px; font-weight:600;")
        self._toggle = QPushButton(self)
        self._toggle.setObjectName("ghost")
        self._toggle.clicked.connect(self._flip)
        self._lang_label = QLabel(self)
        self._lang_box = QComboBox(self)
        for code, name in LANGS:
            self._lang_box.addItem(name, code)
        self._lang_box.currentIndexChanged.connect(self._emit_language)
        self._opacity_label = QLabel(self)
        self._opacity = QSlider(Qt.Orientation.Horizontal, self)
        self._opacity.setRange(15, 80)
        self._opacity.setValue(35)
        self._opacity.valueChanged.connect(self._emit_opacity)
        self._whisper_label = QLabel(self)
        self._whisper = QComboBox(self)
        for name in WHISPER_CHOICES:
            self._whisper.addItem(name)
        self._whisper.currentTextChanged.connect(self._emit_whisper)
        self._ollama_label = QLabel(self)
        self._ollama = QComboBox(self)
        self._ollama.setEditable(True)
        for name in OLLAMA_CHOICES:
            self._ollama.addItem(name)
        self._ollama.currentTextChanged.connect(self._emit_ollama)
        self._vad = QCheckBox(self)
        self._vad.toggled.connect(self._emit_vad)
        self._predict = QCheckBox(self)
        self._predict.toggled.connect(self._emit_predict)

    def retranslate(self, lang: str) -> None:
        self._lang = lang
        self._header.setText(t(lang, "settings"))
        self._toggle.setText(t(lang, "hide") if self._open else t(lang, "settings"))
        self._lang_label.setText(t(lang, "language"))
        self._opacity_label.setText(t(lang, "opacity"))
        self._whisper_label.setText(t(lang, "whisper"))
        self._ollama_label.setText(t(lang, "corrector"))
        self._vad.setText(t(lang, "vad"))
        self._vad.setToolTip(t(lang, "vad_tip"))
        self._predict.setText(t(lang, "predict"))
        self._predict.setToolTip(t(lang, "predict_tip"))

    def set_values(
        self,
        *,
        language: str,
        opacity: int,
        whisper: str,
        ollama: str,
        ollama_models: list[str],
        vad: bool,
        predict: bool,
    ) -> None:
        self._updating = True
        index = self._lang_box.findData(language)
        self._lang_box.setCurrentIndex(index if index >= 0 else 0)
        self._opacity.setValue(opacity)
        self._fill_combo(self._whisper, list(WHISPER_CHOICES), whisper)
        models = list(dict.fromkeys(list(OLLAMA_CHOICES) + ollama_models + [ollama]))
        self._fill_combo(self._ollama, models, ollama)
        self._vad.setChecked(vad)
        self._predict.setChecked(predict)
        self._updating = False

    def _fill_combo(self, box: QComboBox, names: list[str], current: str) -> None:
        box.blockSignals(True)
        box.clear()
        for name in names:
            if name:
                box.addItem(name)
        found = box.findText(current)
        if found >= 0:
            box.setCurrentIndex(found)
        elif current:
            box.addItem(current)
            box.setCurrentText(current)
        box.blockSignals(False)

    def _flip(self) -> None:
        self._open = not self._open
        self._body.setVisible(self._open)
        self._toggle.setText(t(self._lang, "hide") if self._open else t(self._lang, "settings"))
        self.setProperty("active", "true" if self._open else "false")
        self._scale_body(self._open)
        style = self.style()
        if style is not None:
            style.unpolish(self)
            style.polish(self)
        self.updateGeometry()
        self.expanded_changed.emit(self._open)

    def _scale_body(self, opened: bool) -> None:
        # Closed chrome stays compact. Opened controls need more type size or they look shrunk.
        if not opened:
            self._body.setStyleSheet("")
            return
        self._body.setStyleSheet(
            """
            QLabel { color:#e4e4e8; font-size:14px; }
            QComboBox {
                font-size:14px; min-height:30px; padding:6px 12px;
            }
            QCheckBox { font-size:14px; min-height:26px; padding:8px 12px; }
            QCheckBox::indicator { width:14px; height:14px; border-radius:7px; }
            QSlider { min-height:20px; }
            QSlider::groove:horizontal { height:6px; }
            QSlider::handle:horizontal { width:14px; height:14px; margin:-4px 0; }
            """
        )

    def _emit_language(self) -> None:
        if not self._updating:
            code = self._lang_box.currentData()
            if isinstance(code, str):
                self.language_changed.emit(code)

    def _emit_opacity(self, value: int) -> None:
        if not self._updating:
            self.opacity_changed.emit(value)

    def _emit_whisper(self, value: str) -> None:
        if not self._updating and value.strip():
            self.whisper_changed.emit(value.strip())

    def _emit_ollama(self, value: str) -> None:
        if not self._updating and value.strip():
            self.ollama_changed.emit(value.strip())

    def _emit_vad(self, checked: bool) -> None:
        if not self._updating:
            self.vad_changed.emit(checked)

    def _emit_predict(self, checked: bool) -> None:
        if not self._updating:
            self.predict_changed.emit(checked)


def _row(label: QLabel, widget) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(8)
    label.setMinimumWidth(96)
    row.addWidget(label)
    row.addWidget(widget, 1)
    return row
